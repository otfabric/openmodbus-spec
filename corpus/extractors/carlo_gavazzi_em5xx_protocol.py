"""Carlo Gavazzi EM511 and EM530/EM540 Modbus communication protocols (PDF).

The selector is the model: "em511", "em530" or "em540". EM530 and EM540 share
one document. Rows are selected by section title and VARIABLE label; the
Modicom address and the physical (frame) address must agree.
"""
import re
import unicodedata

from sourcelib import modicon_reference, pdf_page_count, pdf_pages, require

BY_TYPE = "Instantaneous variables and meters (grouped by variable type)"
BY_PHASE = "Instantaneous variables and meters (grouped by phase)"
FIRMWARE = "Firmware version and revision code"
IDENTIFICATION = "Carlo Gavazzi Controls identification code"
PART_NUMBERS = "Part number available"
DEVICE_STATE = "Device state"
DOCUMENTS = {
    "em511": ("EM511 COMMUNICATION PROTOCOL Internal version rev. 1.8", "EM511-IS"),
    "em530": ("EM530/EM540 Modbus MODBUS COMMUNICATION PROTOCOL Public version Version 1.3", "EM530-IS"),
    "em540": ("EM530/EM540 Modbus MODBUS COMMUNICATION PROTOCOL Public version Version 1.3", "EM540-IS"),
}
# label -> (point id, data format, weight unit or None, overflow sentinel applies)
EM511 = (BY_TYPE, {
    "V L-N": ("voltage", "INT32", "Volt", True),
    "A": ("current", "INT32", "Ampere", True),
    "W": ("active_power", "INT32", "Watt", True),
    "VA": ("apparent_power", "INT32", "VA", True),
    "Var": ("reactive_power", "INT32", "var", True),
    "PF (IEC convention – see Note)": ("power_factor", "INT16", "PF", True),
    "Hz": ("frequency", "INT16", "Hz", True),
    "kWh (+) TOT": ("import_active_energy", "INT32", "kWh", False),
    "kWh (-) TOT": ("export_active_energy", "INT32", "kWh", False),
})
EM5X0 = (BY_PHASE, {
    "V L1-N": ("voltage_l1_n", "INT32", "Volt", False),
    "V L2-N": ("voltage_l2_n", "INT32", "Volt", False),
    "V L3-N": ("voltage_l3_n", "INT32", "Volt", False),
    "V L1-L2": ("voltage_l1_l2", "INT32", "Volt", False),
    "A L1": ("current_l1", "INT32", "Ampere", False),
    "A L2": ("current_l2", "INT32", "Ampere", False),
    "A L3": ("current_l3", "INT32", "Ampere", False),
    "W sys": ("active_power_total", "INT32", "Watt", False),
    "VA sys": ("apparent_power_total", "INT32", "VA", False),
    "var sys": ("reactive_power_total", "INT32", "var", False),
    "PF sys": ("power_factor_total", "INT32", "PF", False),
    "Hz": ("frequency", "INT32", "Hz", False),
    "kWh (+) TOT": ("import_active_energy", "INT32", "kWh", False),
    "kWh (-) TOT": ("export_active_energy", "INT32", "kWh", False),
})
UNITS = {"Volt": "V", "Ampere": "A", "Watt": "W", "VA": "V.A", "var": None, "PF": None, "Hz": "Hz", "kWh": "kW.h"}
TYPES = {"INT16": "i16", "UINT16": "u16", "INT32": "i32"}
HEADING = re.compile(r"^\s{0,3}\d+(?:\.\d+)*\.?\s+([A-Z][^.]*?)\s*$")
ROW = re.compile(r"^\s*(3\d{5})\s+([0-9A-F]{4})h\s+(\d+)\s+(.+?)\s+(U?INT ?(?:16|32|64)|IEEE754 SP)(?:\s+(.*))?$")
PART = re.compile(r"^\s*(EM5\d0DINAV\w+|EM511DINAV\w+)\s+(EM5\d\d-IS)\s+(\w+)\s+(\d{4})\s+([0-9A-F]{4})\s+(\S+)\s")


def flat(text):
    text = unicodedata.normalize("NFKC", text).replace("“", '"').replace("”", '"')
    return " ".join(text.split())


def parse(pages):
    """Return {section: {"intro": text, "rows": [row...]}, "parts": [...]} from the document text."""
    sections = {}
    parts = []
    section = None
    for number, page in pages:
        lines = page.splitlines()
        for index, line in enumerate(lines):
            heading = HEADING.match(line)
            if heading and "...." not in line:
                section = heading.group(1)
                sections.setdefault(section, {"intro": [], "rows": []})
                continue
            if section is None:
                continue
            part = PART.match(line)
            if part:
                parts.append((section, part.groups(), number))
                continue
            match = ROW.match(line)
            if not match:
                if not sections[section]["rows"]:
                    sections[section]["intro"].append(line)
                continue
            notes_column = match.start(6) if match.group(6) else None
            block = [match.group(6) or ""]
            for following in lines[index + 1:index + 8]:
                if notes_column is None or not following.strip() or ROW.match(following) or HEADING.match(following):
                    break
                # Continuation lines of the Notes cell start at (or just right of) the row's Notes column.
                chunks = [(cell.start(), cell.group()) for cell in re.finditer(r"\S+(?: \S+)*", following)]
                block.extend([text for start, text in chunks if notes_column <= start < notes_column + 12][:1])
            modicom, physical, length, label, data_format, _ = match.groups()
            sections[section]["rows"].append({
                "modicom": modicom, "physical": physical, "length": int(length), "label": label.strip(),
                "format": data_format.replace(" ", ""), "notes": block, "page": number,
            })
    return sections, parts


def row(sections, section, label):
    require(section in sections, f"Carlo Gavazzi section {section!r} missing")
    found = [entry for entry in sections[section]["rows"] if entry["label"] == label]
    require(len(found) == 1, f"Carlo Gavazzi {section} / {label}: {len(found)} rows")
    entry = found[0]
    address = int(entry["physical"], 16)
    require(modicon_reference(entry["modicom"], "input_register") == address,
            f"Carlo Gavazzi {label}: Modicom and physical addresses disagree")
    return entry, address


def source(entry, section):
    return {"address": f"{entry['physical']}h", "page": entry["page"], "reference": f"{section}; {entry['modicom']}"}


def notes_text(entry):
    return flat(" ".join(re.split(r"\s{2,}", part.strip())[0] for part in entry["notes"]))


def extract(data, selector):
    require(selector in DOCUMENTS, f"Unknown Carlo Gavazzi selector {selector!r}")
    title, family = DOCUMENTS[selector]
    pages = list(enumerate(pdf_pages(data, 1, pdf_page_count(data)), start=1))
    text = flat("\n".join(page for _, page in pages))
    require(title in flat(pages[0][1]), f"Carlo Gavazzi document is not the {title}")
    require('"Physical address": it is the "word address" value to be included in the communication frame' in text,
            "Carlo Gavazzi physical address statement missing")
    require("For all the formats the byte order (inside the single word) is MSB->LSB. In INT32, UINT32 and "
            "UINT64 formats, the word order is LSW-> MSW." in text, "Carlo Gavazzi word order statement missing")
    overflow = ('When in "EEE" the relevant modbus variable is represented as 0x7FFF for 16-bit registers, '
                '0x7FFFFFFF for 32-bit registers.') in text
    require(overflow == (selector == "em511"), "Carlo Gavazzi overflow statement differs from expectation")
    sections, parts = parse(pages)
    section, selected = EM511 if selector == "em511" else EM5X0

    points = []
    for label, (point_id, data_format, weight_unit, sentinel) in selected.items():
        entry, address = row(sections, section, label)
        kind = TYPES[data_format]
        require(entry["format"] == data_format and entry["length"] == {"i16": 1, "i32": 2}[kind],
                f"Carlo Gavazzi {label}: unexpected format {entry['format']} / {entry['length']}")
        # The weight sits in the Notes cell of the row line itself.
        row_notes = flat(re.split(r"\s{2,}", entry["notes"][0].strip())[0])
        weight = re.search(r"Value weight: (\S+?)\s*\*\s*(\d+)$", row_notes)
        require(weight and weight.group(1) == weight_unit, f"Carlo Gavazzi {label}: unexpected value weight")
        factor = weight.group(2)
        require(re.fullmatch(r"10+", factor), f"Carlo Gavazzi {label}: weight {factor} is not a power of ten")
        point = {"id": point_id, "address": address, "type": kind}
        if kind == "i32":
            point["wordOrder"] = "little"
        point["conversion"] = {"exponent10": -(len(factor) - 1)}
        if UNITS[weight_unit]:
            point["unit"] = UNITS[weight_unit]
        elif weight_unit == "var":
            point["description"] = "Vendor unit: var"
        if sentinel:
            point["invalid"] = [0x7FFF if kind == "i16" else 0x7FFFFFFF]
        point["aliases"] = [label]
        point["source"] = source(entry, section)
        points.append(point)

    if selector == "em511":
        entry, address = row(sections, BY_TYPE, "Inductive/Capacitive Load")
        match = re.fullmatch(r"L\s*=\s*\+?(\d+), C\s*=\s*(-\d+)", notes_text(entry))
        require(entry["format"] == "INT16" and entry["length"] == 1 and match,
                "Carlo Gavazzi Inductive/Capacitive Load row changed")
        points.append({
            "id": "load_type", "address": address, "type": "i16",
            "enum": {"values": [{"value": int(match.group(1)), "name": "inductive", "label": "L"},
                                {"value": int(match.group(2)), "name": "capacitive", "label": "C"}]},
            "aliases": [entry["label"]], "source": source(entry, BY_TYPE),
        })

    ranges = []
    require("limited to a word at a time" in flat(" ".join(sections[FIRMWARE]["intro"])),
            "Carlo Gavazzi firmware register read restriction missing")
    entry, address = row(sections, FIRMWARE, "Major, Minor and Revision" if selector == "em511" else "Major, Minor and")
    notes = notes_text(entry)
    minor = re.search(r"MSB: Bit (\d)\.\.(\d) = Minor", notes)
    major = re.search(r"Bit (\d)\.\.(\d) = Major", notes)
    require(entry["format"] == "UINT16" and entry["length"] == 1 and minor and major and "LSB: Revision" in notes,
            "Carlo Gavazzi firmware version layout changed")
    for point_id, bits in (("firmware_major", major), ("firmware_minor", minor), ("firmware_revision", None)):
        if bits:
            low, high = int(bits.group(1)), int(bits.group(2))
            mask = ((1 << (high - low + 1)) - 1) << (8 + low)
        else:
            mask = 0x00FF
        points.append({"id": point_id, "address": address, "type": "u16", "mask": mask, "stability": "constant",
                       "aliases": ["Major, Minor and Revision"], "source": source(entry, FIRMWARE)})
    ranges.append({"table": "input_register", "start": address, "count": 1, "policy": "isolated",
                   "reason": "Vendor: read only with function 03 or 04, limited to a word at a time."})

    require("limited to a word at a time" in flat(" ".join(sections[IDENTIFICATION]["intro"])),
            "Carlo Gavazzi identification code read restriction missing")
    entry, address = row(sections, IDENTIFICATION,
                         IDENTIFICATION if selector == "em511" else "Carlo Gavazzi Controls")
    require(entry["format"] == "UINT16" and entry["length"] == 1 and
            notes_text(entry).startswith("See Part number available"), "Carlo Gavazzi identification row changed")
    values = []
    require({part_section for part_section, _, _ in parts} == {PART_NUMBERS}, "Carlo Gavazzi part rows misplaced")
    for _, (part, part_family, _, decimal, hex16, _), _ in parts:
        if part_family != family:
            continue
        if int(decimal) != int(hex16, 16):
            # Known erratum: the EM511 SFA row repeats the PFB hex code next to decimal 1795.
            require(part == "EM511DINAV81XS1SFA", f"Carlo Gavazzi {part}: decimal and hex codes disagree")
            continue
        values.append({"value": int(decimal), "name": part.lower(), "label": part})
    require(values, f"Carlo Gavazzi {family}: no part numbers")
    points.append({"id": "identification_code", "address": address, "type": "u16", "enum": {"values": values},
                   "stability": "constant", "aliases": [IDENTIFICATION], "source": source(entry, IDENTIFICATION)})
    ranges.append({"table": "input_register", "start": address, "count": 1, "policy": "isolated",
                   "reason": "Vendor: read only with function 03 or 04, limited to a word at a time."})

    entry, address = row(sections, DEVICE_STATE, "Device state")
    states = re.findall(r"Value (\d+) = ([A-Z][A-Z ]*[A-Z])\b", notes_text(entry))
    require(entry["format"] == "UINT16" and entry["length"] == 1 and states and states[0] == ("0", "RUN"),
            "Carlo Gavazzi device state row changed")
    points.append({
        "id": "device_state", "address": address, "type": "u16",
        "enum": {"values": [{"value": int(value), "name": name.lower().replace(" ", "_"), "label": name}
                            for value, name in states]},
        "aliases": ["Device state"], "source": source(entry, DEVICE_STATE),
    })

    points.sort(key=lambda point: (point["address"], -point.get("mask", 0)))
    return {"points": points, "constraints": {"ranges": sorted(ranges, key=lambda item: item["start"])}}
