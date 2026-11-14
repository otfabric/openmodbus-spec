"""IMT Technology Modbus specification for Si-RS485...-MB irradiance sensors (PDF).

The selector is the sensor type as the sheet's "Identifying the sensor type" table
names it, e.g. "Si-RS485TC-2T-MB". That table lists the active registers per type;
the compatibility cell-temperature registers apply to every type.
"""
from decimal import Decimal
import re

from sourcelib import pdf_pages, require

ROW = re.compile(
    r"^[ \t]*(\d+)(?:[ \t]+(\d)\))?[ \t]+(\S.*?\S)[ \t]{2,}(\d+(?:\.\d+)?)[ \t]+(-?\d+)[ \t]+"
    r"([-+]?\d+)…([-+]?\d+)[ \t]*(W/m²|°C|m/s)(?:[ \t]+(\d)\))?[ \t]+"
    r"(-?\d+)…(-?\d+)(?:[ \t]+(\d)\))?[ \t]+(U?INT16)[ \t]*$")
FOOTNOTE = re.compile(r"^[ \t]*(\d)\)[ \t]+(\S.*?)[ \t]*$")
FUNCTION = re.compile(r"^[ \t]*→ (0x[0-9A-F]{2}): (\S.*?)[ \t]*$")
TABLE_HEADER = re.compile(r"^[ \t]*Register[ \t]+Value[ \t]+Gain[ \t]+Offset[ \t]+Phys\. Range[ \t]+Data Range[ \t]+"
                          r"Data Type[ \t]*$")
ACTIVE = re.compile(r"^[ \t]*(485-\d)[ \t]+(Si-RS485\S+)[ \t]+(\d+(?:, \d+)*)[ \t]*$")
UNITS = {"W/m²": "W/m2", "°C": "Cel", "m/s": "m/s"}

# (table page, label): (point id, physical unit, active-register gated)
SELECTED = {
    (1, "Irradiance in W/m²"): ("irradiance", "W/m²", True),
    (1, "Cell Temperature in °C"): ("cell_temperature", "°C", True),
    (1, "External Temp. no. 1 in °C"): ("external_temperature_1", "°C", True),
    (2, "Cell Temperature in °C"): (None, "°C", False),
}
COMPAT_IDS = {"-25": "cell_temperature_offset_25", "-100": "cell_temperature_offset_100"}


def exponent(gain):
    value = Decimal(gain)
    power = -value.normalize().as_tuple().exponent
    require(value * Decimal(10) ** power == 1, f"IMT: gain {gain} is not a power of ten")
    return -power


def extract(data, selector):
    pages = pdf_pages(data, 1, 5)
    text = " ".join(" ".join(pages).split())
    require("Modbus Specification for Irradiance Sensors Si-RS485…-MB" in text, "IMT: document title missing")
    require("Transmission mode: Modbus RTU" in text, "IMT: transmission mode missing")
    require("→ 0x03: Read Holding Register → 0x04: Read Input Register" in text, "IMT: read function codes missing")
    match = re.search(r"with the firmware version (\d+\.\d+)", text)
    require(match is not None, "IMT: firmware validity missing")
    firmware = match.group(1)

    footnotes = {}
    rows = []
    marks = {}
    lines = [(page_number, line) for page_number, page in enumerate(pages[:2], start=1) for line in page.split("\n")]
    for index, (page_number, line) in enumerate(lines):
        code = FUNCTION.match(line)
        if code:
            require(code.group(1) not in marks, f"IMT: function code {code.group(1)} listed twice")
            marks[code.group(1)] = (index, code.group(2))
            continue
        if TABLE_HEADER.match(line):
            marks.setdefault("tables", []).append(index)
            continue
        row = ROW.match(line)
        if row:
            rows.append((page_number, row.groups()))
            marks.setdefault("rows", []).append(index)
            continue
        note = FOOTNOTE.match(line)
        if note:
            require(note.group(1) not in footnotes, f"IMT: duplicate footnote {note.group(1)}")
            footnotes[note.group(1)] = note.group(2)
    # The register tables are part of the "Supported function codes" list: they follow the entries for
    # 0x03 (Read Holding Register) and 0x04 (Read Input Register) and precede the next entry, 0x08.
    require([key for key in marks if key.startswith("0x")] == ["0x03", "0x04", "0x08", "0x46"] and
            marks["0x03"][1] == "Read Holding Register" and marks["0x04"][1] == "Read Input Register" and
            marks["0x08"][1] == "Diagnostics", f"IMT: unexpected function code list {marks}")
    require(all(not line.strip() for _, line in lines[marks["0x04"][0] + 1:marks["tables"][0]]),
            "IMT: register table does not follow the 0x04 entry")
    require(len(marks["tables"]) == 2 and marks["0x04"][0] < min(marks["rows"]) and
            max(marks["rows"]) < marks["0x08"][0], "IMT: register tables are not under the 0x03/0x04 entries")
    # Register 0 exists, so the register numbers cannot be one-based: they are PDU addresses.
    require(min(int(groups[0]) for _, groups in rows) == 0, "IMT: register list does not start at 0")

    active = {}
    for line in pages[4].split("\n"):
        match = ACTIVE.match(line)
        if match:
            prefix, sensor, registers = match.groups()
            require(sensor not in active, f"IMT: duplicate sensor type {sensor}")
            active[sensor] = {int(value) for value in registers.split(", ")}
    require(selector in active, f"IMT: sensor type {selector} not in the identification table")

    points = []
    seen = set()
    for page_number, groups in rows:
        (address, note, label, gain, offset, phys_low, phys_high, phys_unit, phys_note,
         data_low, data_high, data_note, kind) = groups
        key = (page_number, label)
        if key not in SELECTED:
            continue
        point_id, unit, gated = SELECTED[key]
        address = int(address)
        if gated and address not in active[selector]:
            continue
        require(phys_unit == unit, f"IMT register {address}: unit {phys_unit}")
        # The data range, gain and offset must reproduce the physical range.
        for raw, physical in ((data_low, phys_low), (data_high, phys_high)):
            require(Decimal(raw) * Decimal(gain) + Decimal(offset) == Decimal(physical),
                    f"IMT register {address}: data and physical ranges disagree")
        require((kind == "INT16") == (int(data_low) < 0), f"IMT register {address}: signedness")
        if point_id is None:
            point_id = COMPAT_IDS.get(offset)
            require(point_id is not None, f"IMT register {address}: unexpected compatibility offset {offset}")
        require(point_id not in seen, f"IMT: duplicate point {point_id}")
        seen.add(point_id)
        conversion = {"exponent10": exponent(gain)}
        if offset != "0":
            conversion["offset"] = int(offset)
        notes = [footnotes[mark] for mark in (note, phys_note, data_note) if mark]
        require(all(notes), f"IMT register {address}: footnote text missing")
        description = f"{label}, raw {data_low}…{data_high} for {phys_low}…{phys_high} {phys_unit}."
        if not gated:
            description = "Compatibility register for older firmware: " + description
        if notes:
            description += " " + " ".join(f"Note: {text}." for text in notes)
        points.append({
            "id": point_id,
            "address": address,
            "type": {"UINT16": "u16", "INT16": "i16"}[kind],
            "aliases": [label],
            "conversion": conversion,
            "unit": UNITS[phys_unit],
            "description": description,
            "source": {"address": str(address), "page": page_number,
                       "reference": f"Register table (firmware {firmware}): {label}"},
        })
    require(set(COMPAT_IDS.values()) <= seen, f"IMT {selector}: compatibility registers missing")
    require(not active[selector] - {point["address"] for point in points},
            f"IMT {selector}: active register without a selected row")
    return sorted(points, key=lambda point: point["address"])
