"""Apogee Instruments SP-422 / SP-522 / SP-722 owner's manuals (PDF): Modbus RTU register tables.

The selector is the model, e.g. "SP-722". Every register is a holding register with a
zero-based address; measurement values are IEEE 754 floats in two registers, with a
duplicate set of decimal-shifted 16-bit signed integers.
"""
import re
import struct

from sourcelib import pdf_page_count, pdf_pages, require

READ_ONLY = "Read only registers (function code 0x3)."
READ_WRITE = "Read/Write registers (function codes 0x3 and 0x10)."
END = "*Registers marked with an asterisk (*)"
ADDRESS = re.compile(r"^([ \t]{1,40})(\d+)(?:[ \t]+(\S.*?))?[ \t]*$")
STATUS = "device status (1 means device is busy, 0 otherwise)"

# (section, kind, label): (point id, unit, description)
COMMON = {
    ("ro", "float", "firmware version"): ("firmware_version", None, "Firmware version."),
    ("rw", "float", "model number*"): ("model_number", None, "Model number."),
    ("rw", "float", "serial number*"): ("serial_number", None, "Serial number."),
    ("ro", "integer", STATUS): ("device_status", None, "Device status."),
}
SINGLE = {
    ("ro", "float", "calibrated output watts"): (
        "irradiance", "W/m2", "Calibrated output: shortwave irradiance."),
    ("ro", "float", "detector millivolts"): ("detector_voltage", "mV", "Detector output voltage."),
    ("ro", "integer", "calibrated output watts (multiplied by 10)"): (
        "irradiance_int", "W/m2", "Calibrated output as a decimal-shifted integer (x10)."),
    ("ro", "integer", "detector millivolts (multiplied by 100)"): (
        "detector_voltage_int", "mV", "Detector output voltage as a decimal-shifted integer (x100)."),
}
ALBEDO = {
    ("ro", "float", "Incident calibrated output watts"): (
        "irradiance_incident", "W/m2", "Calibrated output of the upward-looking pyranometer (incident)."),
    ("ro", "float", "Reflected calibrated output watts"): (
        "irradiance_reflected", "W/m2", "Calibrated output of the downward-looking pyranometer (reflected)."),
    ("ro", "float", "Incident detector millivolts"): (
        "detector_voltage_incident", "mV", "Detector voltage of the upward-looking pyranometer."),
    ("ro", "float", "Reflected detector millivolts"): (
        "detector_voltage_reflected", "mV", "Detector voltage of the downward-looking pyranometer."),
    ("ro", "float", "Albedo (reflected/incident)"): ("albedo", None, "Albedo, the ratio reflected/incident."),
}
MODELS = {
    "SP-422": {**COMMON, **SINGLE},
    "SP-522": {**COMMON, **SINGLE, ("rw", "integer", "heater status"): (
        "heater_status", None, "Heater status; the manual does not list its values.")},
    "SP-722": {**COMMON, **ALBEDO, ("rw", "integer", "Heater on/off"): (
        "heater_on_off", None, "Heater on/off; the manual does not list its values.")},
}


def normal(text):
    return " ".join(text.split())


def sections(lines):
    """Split the register tables into (section, kind) -> [(page, line)]."""
    marks = {READ_ONLY: "ro", READ_WRITE: "rw"}
    found = {}
    section = kind = None
    for page, line in lines:
        text = line.strip()
        if text in marks:
            section, kind = marks[text], None
            continue
        if text.startswith(END):
            break
        if text in ("Float Registers", "Integer Registers"):
            require(section is not None, "Apogee: register kind outside a section")
            kind = text.split()[0].lower()
            require((section, kind) not in found, f"Apogee: duplicate {section} {kind} table")
            found[(section, kind)] = []
            continue
        if kind is not None:
            found[(section, kind)].append((page, line))
    require(set(found) == {("ro", "float"), ("ro", "integer"), ("rw", "float"), ("rw", "integer")},
            f"Apogee: register tables missing: {sorted(found)}")
    return found


def classify(lines):
    entries = []
    for page, line in lines:
        if not line.strip():
            continue
        match = ADDRESS.match(line)
        if match:
            entries.append({"page": page, "address": int(match.group(2)), "text": match.group(3) or ""})
        elif len(line) - len(line.lstrip()) < 100:
            entries.append({"page": page, "address": None, "text": line.strip()})
        # Lines indented 100 or more columns are page numbers.
    return entries


def float_rows(lines):
    """Floats span two address lines; their label sits on or between those lines."""
    entries = classify(lines)
    rows = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        require(entry["address"] is not None, f"Apogee: float label outside a register pair: {entry['text']!r}")
        end = index + 1
        while end < len(entries) and entries[end]["address"] is None:
            end += 1
        require(end < len(entries) and entries[end]["address"] == entry["address"] + 1,
                f"Apogee: float register {entry['address']} has no second register")
        text = normal(" ".join(item["text"] for item in entries[index:end + 1]))
        rows.append({"address": entry["address"], "label": text, "page": entry["page"]})
        index = end + 1
    return rows


def integer_rows(lines):
    """Integers use one address line; wrapped label lines join the nearest address line."""
    entries = classify(lines)
    positions = [index for index, entry in enumerate(entries) if entry["address"] is not None]
    require(positions, "Apogee: integer table without addresses")
    parts = {index: [(index, entries[index]["text"])] for index in positions}
    for index, entry in enumerate(entries):
        if entry["address"] is not None:
            continue
        before = [position for position in positions if position < index][-1:]
        after = [position for position in positions if position > index][:1]
        candidates = sorted((abs(position - index), position) for position in before + after)
        if len(candidates) == 2 and candidates[0][0] == candidates[1][0]:
            # A tie goes to the address line that has no text of its own.
            bare = [position for _, position in candidates if not entries[position]["text"]]
            require(len(bare) == 1, f"Apogee: cannot place integer label {entry['text']!r}")
            target = bare[0]
        else:
            target = candidates[0][1]
        parts[target].append((index, entry["text"]))
    return [{"address": entries[index]["address"], "page": entries[index]["page"],
             "label": normal(" ".join(text for _, text in sorted(parts[index])))} for index in positions]


def check_protocol(text, selector):
    require(re.search(rf"This manual covers the Modbus RTU (?:communication )?protocol,? (?:albedometer )?"
                      rf"model {selector}\b", text), f"Apogee: manual does not cover {selector}")
    require("Apogee Sensors use zero-based numbering." in text, "Apogee: address base statement missing")
    require("Modbus RTU packets use the zero-based address when addressing registers." in text,
            "Apogee: packet address statement missing")
    require("Holding Registers (the type registers Apogee sensors contain)" in text, "Apogee: register table")
    require("to provide measurement values as 32-bit IEEE 754 floating point numbers" in text, "Apogee: floats")
    require("16-bit signed integers to represent values as decimal-shifted numbers" in text, "Apogee: integers")
    require("Byte order: ABCD (Big-Endian/Most Significant Byte First)" in text, "Apogee: byte order missing")
    require("reading register address 0" in text and "0x01 0x03 0x00 0x00 0x00 0x02 0xC4 0x0B" in text,
            "Apogee: read example missing")
    # The write example puts the float 1.0 into two registers, most significant word first.
    match = re.search(r"writing a 1 to register (\d+)\..*?0x01 0x10 0x([0-9A-Fa-f]{2}) 0x([0-9A-Fa-f]{2}) "
                      r"0x00 0x02 0x04 0x([0-9a-f]{2}) 0x([0-9a-f]{2}) 0x([0-9a-f]{2}) 0x([0-9a-f]{2})", text)
    require(match is not None, "Apogee: write example missing")
    require(int(match.group(2) + match.group(3), 16) == int(match.group(1)), "Apogee: example address is not zero-based")
    require(struct.unpack(">f", bytes.fromhex("".join(match.group(4, 5, 6, 7))))[0] == 1.0,
            "Apogee: example float is not most significant word first")
    require("W m-2" in text, "Apogee: irradiance unit missing")


def extract(data, selector):
    require(selector in MODELS, f"Apogee: unknown model {selector}")
    pages = pdf_pages(data, 1, pdf_page_count(data))
    text = normal(" ".join(pages))
    check_protocol(text, selector)
    lines = [(number, line) for number, page in enumerate(pages, start=1) for line in page.split("\n")]
    tables = sections(lines)
    rows = {}
    for (section, kind), table in tables.items():
        for row in (float_rows if kind == "float" else integer_rows)(table):
            key = (section, kind, row["label"])
            require(key not in rows, f"Apogee: duplicate row {key}")
            rows[key] = row
    points = []
    for key, (point_id, unit, description) in MODELS[selector].items():
        section, kind, label = key
        row = rows.get(key)
        require(row is not None, f"Apogee {selector}: row {label!r} missing")
        point = {"id": point_id, "address": row["address"], "type": "f32" if kind == "float" else "i16",
                 "aliases": [label]}
        scale = re.search(r"\(multiplied by (10+)\)$", label)
        if scale:
            point["conversion"] = {"exponent10": -(len(scale.group(1)) - 1)}
        if label == STATUS:
            point["enum"] = {"values": [{"value": 1, "name": "busy"}, {"value": 0, "name": "not_busy"}]}
        if unit is not None:
            point["unit"] = unit
        if point_id in ("model_number", "serial_number"):
            point["stability"] = "constant"
        point["description"] = description
        reference = f"{'Read only' if section == 'ro' else 'Read/Write'} {kind} registers: {label}"
        address = f"{row['address']}-{row['address'] + 1}" if kind == "float" else str(row["address"])
        point["source"] = {"address": address, "page": row["page"], "reference": reference}
        points.append(point)
    return sorted(points, key=lambda point: point["address"])
