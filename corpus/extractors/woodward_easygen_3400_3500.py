"""Woodward easYgen-3400/3500-P1/P2 manual 37528J: Modbus data protocol 5010 (chapter 9.2.3.1).

The manual gives Modicon references and a second "Start addr." column, multipliers and units, but no data
types, signedness or register order. 32-bit (Long) values are therefore not mapped. Non-negative 16-bit
quantities are read as unsigned; a value is read as signed only when a range stated in the manual includes
negative numbers (the voltage and current exponents, J1939 temperatures). J1939 "not available" sentinels
come from the J1939 table of standard visualization messages (chapter 7.5.1), matched by parameter index.
"""
import re
from decimal import Decimal

from sourcelib import modicon_reference, pdf_page_count, pdf_pages, require

DOCUMENT = "37528J"
PAGES = 846
FOOTER = re.compile(
    r"^\s*(?:37528J\s+easYgen-3400/3500-P1/P2 \| Genset Control\s+(\d+)"
    r"|(\d+)\s+easYgen-3400/3500-P1/P2 \| Genset Control\s+37528J)\s*$")
ROW = re.compile(r"^(4\d{5})\s+(4\d{5})(?:\s+(\d+|-)(?=\s{2}))?\s+(\S.*?)\s*$")
UNITS = {"Hz": "Hz", "V": "V", "A": "A", "rpm": "/min", "°C": "Cel", "kPa": "kPa", "": None}

# Exponent registers: parameter index -> (point id, row label, unit the exponent applies to).
EXPONENTS = {
    "3182": ("voltage_exponent", "Skaling Volts (16 bits) Exponent 10x V", "voltage"),
    "3183": ("current_exponent", "Skaling Amps (16 bits) Exponent 10x A", "current"),
}
# Values: parameter index -> (point id, row label, expected unit text). The multiplier is parsed.
VALUES = {
    "144": ("generator_frequency", "Generator frequency", "Hz"),
    "248": ("generator_voltage_l1_l2", "Generator voltage L1-L2", "V"),
    "249": ("generator_voltage_l2_l3", "Generator voltage L2-L3", "V"),
    "250": ("generator_voltage_l3_l1", "Generator voltage L3-L1", "V"),
    "255": ("generator_current_l1", "Generator current 1", "A"),
    "256": ("generator_current_l2", "Generator current 2", "A"),
    "257": ("generator_current_l3", "Generator current 3", "A"),
    "10100": ("engine_speed", "Engine Pickup speed", "rpm"),
    "10110": ("battery_voltage", "Battery voltage", "V"),
    "2540": ("start_requests", "Engine, number of start requests", ""),
}
# J1939 values with sentinels from the standard visualization table, matched by index.
J1939 = {
    "15308": ("j1939_engine_speed", "Engine Speed (SPN 190)", "rpm", "Engine speed"),
    "15202": ("j1939_coolant_temperature", "Engine Coolant Temperature (SPN 110)", "°C",
              "Engine coolant temperature"),
    "15205": ("j1939_oil_pressure", "Engine Oil Pressure (SPN 100)", "kPa", "Engine oil pressure"),
}
CONTROL_MODE = ("1735", "Control mode (STOP/AUTO/MANUAL)", {1: "AUTO", 2: "STOP", 4: "MANUAL"})
STOP_INFORMATION = ("15304", "J1939 Engine Stop Information (e.g.,")
ALARMS = ("10133", "Alarms 1 latched (unacknowledged)")
ALARM_FLAGS = {
    "Overspeed 1": "overspeed_1",
    "Overspeed 2": "overspeed_2",
    "Underspeed 1": "underspeed_1",
    "Underspeed 2": "underspeed_2",
    "Unintended stop": "unintended_stop",
    "Speed det. Alarm": "speed_detection_alarm",
    "Shutdown malfunct.": "shutdown_malfunction",
    "GCB fail to close": "gcb_fail_to_close",
    "GCB fail to open": "gcb_fail_to_open",
    "MCB fail to close": "mcb_fail_to_close",
    "MCB fail to open": "mcb_fail_to_open",
    "CAN-Fault J1939": "can_fault_j1939",
    "Start fail": "start_fail",
    "Mainten. days exceeded": "maintenance_days_exceeded",
    "Mainten. hours exceeded": "maintenance_hours_exceeded",
    "CANopen error at CAN Interface 1": "canopen_error_can_interface_1",
}
REFERENCE = "Protocol 5010 (Basic Visualization)"


def flat(text):
    return " ".join(re.sub(r"‐[ \t]*\n\s*", "", text).split())


def find_page(pages, first, pattern, what):
    found = [first + index for index, text in enumerate(pages) if re.search(pattern, text, re.MULTILINE)]
    require(len(found) == 1, f"{DOCUMENT}: expected one page with {what}, found {found}")
    return found[0]


def check_footer(lines, page):
    footers = [index for index, line in enumerate(lines) if FOOTER.match(line)]
    require(len(footers) == 1, f"{DOCUMENT} page {page}: page footer missing")
    match = FOOTER.match(lines[footers[0]])
    require(int(match.group(1) or match.group(2)) == page, f"{DOCUMENT} page {page}: printed page number differs")
    return footers[0]


def address_offset(data):
    """Chapter 7.6: Modicon references, read with Read Holding Registers, 450001 may become bus address 50000."""
    first = 600
    pages = pdf_pages(data, first, first + 10)
    start = find_page(pages, first, r"^7\.6\s+Modbus Protocol\s*$", "the chapter 7.6 heading")
    end = find_page(pages, first, r"^7\.7\s+Load Sharing\s*$", "the chapter 7.7 heading")
    text = flat("\n".join(pages[start - first:end - first + 1]))
    require('can be read via the "Read Holding Register" function' in text,
            f"{DOCUMENT} 7.6: Read Holding Register statement missing")
    require("All addresses in this document comply with the Modicon address convention" in text,
            f"{DOCUMENT} 7.6: Modicon convention statement missing")
    match = re.search(r"The Modbus starting address (4\d{5}) of the visualization data may become bus address "
                      r"(\d+) for example", text)
    require(match, f"{DOCUMENT} 7.6: bus address example missing")
    reference, bus = match.groups()
    require(modicon_reference(reference, "holding_register") == int(bus),
            f"{DOCUMENT} 7.6: bus address example is not reference minus 400001")
    return int(reference) - int(bus)


def exponent_semantics(data):
    """Chapter 4.6.7: parameter ranges and worked examples (Tables 58-60): value = transfer x 10^setting."""
    first = 400
    pages = pdf_pages(data, first, first + 10)
    page = find_page(pages, first, r"^Power measurement example\s*$", "the power measurement example")
    text = flat("\n".join(pages[page - first:page - first + 2]))
    ranges = {}
    for index, low, high in re.findall(r"\b(318[123]) (?:Power|Voltage|Current) \[[WVA]\] 2 (-?\d) to (-?\d)\b", text):
        ranges[index] = set(range(int(low), int(high) + 1))
    require(set(ranges) == {"3181", "3182", "3183"}, f"{DOCUMENT} 4.6.7: exponent parameter ranges missing")
    require(text.count("Transfer value") == 3 and text.count("(16 Bit, max. 32767)") == 3,
            f"{DOCUMENT} 4.6.7: transfer value headers missing")
    examples = re.findall(r"(-?\d) 10-?\d ([\d.]+) ([WVA]) / 10-?\d [WVA] (\d+) ", text)
    require(len(examples) >= 8, f"{DOCUMENT} 4.6.7: worked examples missing")
    for setting, measured, _, transfer in examples:
        expected = int(Decimal(measured) / Decimal(10) ** int(setting))
        require(expected == int(transfer), f"{DOCUMENT} 4.6.7: example {measured} at 10^{setting} is not {transfer}")
    return ranges, page


def j1939_sentinels(data):
    """Chapter 7.5.1, table "Standard visualization messages": display values for defective and missing sensors."""
    first = 590
    pages = pdf_pages(data, first, first + 10)
    page = find_page(pages, first, r"^Standard visualization messages\s*$", "the J1939 visualization table")
    header = r"Display with\s+Display with"
    rows = {}
    for offset in range(3):
        text = pages[page - first + offset]
        if not re.search(header, text):
            require(offset > 0, f"{DOCUMENT} page {page}: J1939 table header missing")
            break
        for match in re.finditer(
                r"^(\d+)\s+(\d{5})\s+(\S.*?)\s{2,}(\d+(?:\.\d+)?) ?(\S+)\s{2,}(\S.*?)\s{2,}(15\d{3})\s+"
                r"(\d+(?:\.\d+)?) (\S+)\s+(\d+(?:\.\d+)?) (\S+)\s*$", text, re.MULTILINE):
            fields = list(match.groups())
            if fields[5].endswith(" to"):
                wrapped = re.match(r"\n\s+(\d+(?:\.\d+)? \S+)\s*\n", text[match.end():])
                require(wrapped, f"{DOCUMENT} page {page + offset}: wrapped J1939 data range {fields[0]}")
                fields[5] += " " + wrapped.group(1)
            rows.setdefault(fields[6], []).append((page + offset, fields))
    return rows


def table_lines(data):
    first = 695
    pages = pdf_pages(data, first, first + 50)
    start = find_page(pages, first, r"^9\.2\.3\.1\s+Protocol 5010 \(Basic Visualization\)\s*$", "the 5010 heading")
    end = find_page(pages, first, r"^9\.2\.4\s+Additional Data Identifier\s*$", "the chapter 9.2.4 heading")
    lines = []
    for page in range(start, end + 1):
        page_lines = pages[page - first].split("\n")
        footer = check_footer(page_lines, page)
        headers = [index for index, line in enumerate(page_lines) if re.match(r"^start addr\.\s+\(\*1\)\s*$", line)]
        require(len(headers) == 1, f"{DOCUMENT} page {page}: 5010 table header missing")
        top = flat("\n".join(page_lines[headers[0] - 3:headers[0] + 1]))
        require(re.fullmatch(r"Modbus Parameter Description Multiplier Units ID Modicon Start addr\. start addr\. "
                             r"\(\*1\)", top), f"{DOCUMENT} page {page}: unexpected 5010 table columns")
        if page == start:
            heading = [index for index, line in enumerate(page_lines) if line.startswith("9.2.3.1")]
            require(heading[0] < headers[0], f"{DOCUMENT} page {page}: 5010 header before its heading")
        for line in page_lines[headers[0] + 1:footer]:
            if page == end and re.match(r"^9\.2\.4\s", line):
                return lines
            lines.append((page, line))
    require(False, f"{DOCUMENT}: chapter 9.2.4 heading not reached")


def table_rows(data, offset):
    rows = []
    current = None
    for page, line in table_lines(data):
        if not line.strip():
            continue
        match = ROW.match(line)
        if match:
            reference, start, index, rest = match.groups()
            require(int(start) == int(reference) - 1,
                    f"{DOCUMENT} {reference}: start address column is not reference - 1")
            address = int(reference) - offset
            require(modicon_reference(reference, "holding_register") == address,
                    f"{DOCUMENT} {reference}: address does not follow the Modicon convention")
            current = {"reference": reference, "address": address, "index": index, "page": page,
                       "fields": re.split(r"\s{2,}", rest), "more": []}
            rows.append(current)
        elif not line.startswith(" "):
            current = None
        else:
            require(current is not None, f"{DOCUMENT} page {page}: continuation line without a row: {line.strip()!r}")
            current["more"].append(line.strip())
    by_index = {}
    for row in rows:
        if row["index"] not in (None, "-"):
            by_index.setdefault(row["index"], []).append(row)
    return rows, by_index


def one_row(by_index, index, label):
    found = [row for row in by_index.get(index, []) if row["fields"][0] == label]
    require(len(found) == 1, f"{DOCUMENT}: expected one 5010 row {index} {label!r}, found {len(found)}")
    row = found[0]
    require(not any("only:" in text for text in [*row["fields"], *row["more"]]),
            f"{DOCUMENT} {row['reference']}: row is limited to some models")
    return row


def source(row, label):
    return {"address": row["reference"], "page": row["page"], "reference": f"{REFERENCE}: {label}"}


def multiplier(text, reference):
    value = Decimal(text.replace(",", "."))
    exponent = value.adjusted()
    require(value == Decimal(1).scaleb(exponent), f"{DOCUMENT} {reference}: multiplier {text} is not a power of ten")
    return exponent


def extract(data, selector=None):
    require(pdf_page_count(data) == PAGES, f"{DOCUMENT}: unexpected page count")
    offset = address_offset(data)
    ranges, example_page = exponent_semantics(data)
    sentinels = j1939_sentinels(data)
    _, by_index = table_rows(data, offset)
    points = {}

    def add(point):
        require(point["id"] not in points, f"{DOCUMENT}: duplicate point {point['id']}")
        points[point["id"]] = point

    exponent_ids = {}
    for index, (point_id, label, unit) in EXPONENTS.items():
        row = one_row(by_index, index, label)
        require(len(row["fields"]) == 1 and len(row["more"]) == 1, f"{DOCUMENT} {row['reference']}: unexpected row")
        stated = {int(value) for value in re.fullmatch(r"\(([-\d;]+)\)", row["more"][0]).group(1).split(";")}
        require(stated == ranges[index],
                f"{DOCUMENT} {row['reference']}: exponent range differs from parameter {index}")
        add({"id": point_id, "address": row["address"], "type": "i16" if min(stated) < 0 else "u16",
             "description": f"Power-of-ten exponent of the 16-bit {unit} values (parameter {index}, "
                            f"values {sorted(stated)}); see the examples on page {example_page}.",
             "aliases": [label], "source": source(row, label)})
        exponent_ids[row["reference"]] = (index, point_id)

    for index, (point_id, label, unit_text) in VALUES.items():
        row = one_row(by_index, index, label)
        fields = row["fields"]
        unit = fields[2] if len(fields) == 3 else ""
        require(len(fields) in (2, 3) and unit == unit_text, f"{DOCUMENT} {row['reference']}: unexpected unit")
        point = {"id": point_id, "address": row["address"], "type": "u16"}
        scale = " ".join([fields[1], *row["more"]])
        scaled = re.fullmatch(r"scaled defined by index (\d+) \(modicon Address (4\d{5})\)", scale)
        if scaled:
            require(exponent_ids.get(scaled.group(2), (None,))[0] == scaled.group(1),
                    f"{DOCUMENT} {row['reference']}: exponent reference does not match its register")
            point["conversion"] = {"exponent10": {"point": exponent_ids[scaled.group(2)][1]}}
        else:
            require(not row["more"], f"{DOCUMENT} {row['reference']}: unexpected continuation")
            exponent = multiplier(fields[1], row["reference"])
            if exponent:
                point["conversion"] = {"exponent10": exponent}
        if UNITS[unit]:
            point["unit"] = UNITS[unit]
        point.update(aliases=[label], source=source(row, label))
        add(point)

    for index, (point_id, label, unit_text, j1939_label) in J1939.items():
        row = one_row(by_index, index, label)
        require(len(row["fields"]) == 3 and row["fields"][2] == unit_text and not row["more"],
                f"{DOCUMENT} {row['reference']}: unexpected J1939 row")
        exponent = multiplier(row["fields"][1], row["reference"])
        require(len(sentinels.get(index, [])) == 1, f"{DOCUMENT}: J1939 table row for index {index} missing")
        page, (spn, _, name, resolution, resolution_unit, value_range, _, defective, defective_unit, missing,
               missing_unit) = sentinels[index][0]
        require(name == j1939_label and f"(SPN {spn})" in label, f"{DOCUMENT}: J1939 index {index} is {name!r}")
        require(Decimal(resolution) == Decimal(row["fields"][1].replace(",", ".")) and
                resolution_unit == defective_unit == missing_unit == unit_text,
                f"{DOCUMENT}: J1939 index {index} resolution or unit differs from the 5010 row")
        low = Decimal(re.fullmatch(r"(-?\d+(?:\.\d+)?) to \d+(?:\.\d+)? \S+", value_range).group(1))
        kind = "i16" if low < 0 else "u16"
        raws = [Decimal(value).scaleb(-exponent) for value in (defective, missing)]
        require(all(raw == raw.to_integral_value() and 0 <= raw <= 32767 for raw in raws),
                f"{DOCUMENT}: J1939 index {index} sentinels are not 16-bit raw values")
        point = {"id": point_id, "address": row["address"], "type": kind}
        if exponent:
            point["conversion"] = {"exponent10": exponent}
        point.update({
            "unit": UNITS[unit_text], "invalid": [int(raw) for raw in raws],
            "description": f"Value from the engine control unit over J1939 (SPN {spn}, data range {value_range}). "
                           f"Raw {int(raws[0])} is shown for a defective sensor and {int(raws[1])} for a missing "
                           f"sensor (J1939 standard visualization messages, page {page}).",
            "aliases": [label], "source": source(row, label)})
        add(point)

    index, label, expected = CONTROL_MODE
    row = one_row(by_index, index, label)
    require(row["fields"][1:] == ["Mask: 000Fh", "(enum.)"], f"{DOCUMENT} {row['reference']}: unexpected control mode")
    values = {int(value): name
              for value, name in (re.fullmatch(r"(\d+) = (\w+)", text).groups() for text in row["more"])}
    require(values == expected, f"{DOCUMENT} {row['reference']}: control mode values differ")
    add({"id": "control_mode", "address": row["address"], "type": "u16", "mask": 0x000F,
         "enum": {"values": [{"value": value, "name": name.lower(), "label": name}
                             for value, name in sorted(values.items())]},
         "aliases": [label], "source": source(row, label)})

    index, label = ALARMS
    row = one_row(by_index, index, label)
    require(len(row["fields"]) == 1, f"{DOCUMENT} {row['reference']}: unexpected alarm row")
    flags = {}
    for text in row["more"]:
        parameter, name, mask = re.fullmatch(r"(\d+)\s{2,}(.+?)\s{2,}Mask: ([0-9A-F]{4})h\s+Bit", text).groups()
        mask = int(mask, 16)
        require(mask & (mask - 1) == 0 and name in ALARM_FLAGS,
                f"{DOCUMENT} {row['reference']}: unexpected flag {name}")
        flags[mask.bit_length() - 1] = {"bit": mask.bit_length() - 1, "name": ALARM_FLAGS[name],
                                        "label": name, "description": f"Alarm parameter {parameter}."}
    require(sorted(flags) == list(range(16)) and len({flag["name"] for flag in flags.values()}) == 16,
            f"{DOCUMENT} {row['reference']}: alarm bits incomplete")
    add({"id": "engine_alarms_latched", "address": row["address"], "type": "u16",
         "flags": {"flags": [flags[bit] for bit in sorted(flags)]},
         "description": "Engine alarms 1, latched and not yet acknowledged.",
         "aliases": [label], "source": source(row, label)})

    index, label = STOP_INFORMATION
    row = one_row(by_index, index, label)
    text = flat("\n".join([" ".join(row["fields"]), *row["more"]]))
    missing = re.search(r'"Missing" Value="(\d+)"', text)
    error = re.search(r'"Error" Value="(\d+)"', text)
    require(missing and error and "Engine stop information value is 0 to 250" in text,
            f"{DOCUMENT} {row['reference']}: stop information values missing")
    raws = sorted({int(error.group(1)), int(missing.group(1))})
    require(all(32767 < raw <= 65535 for raw in raws), f"{DOCUMENT} {row['reference']}: unexpected sentinels")
    add({"id": "j1939_engine_stop_information", "address": row["address"], "type": "u16", "invalid": raws,
         "description": f"Engine stop information from the engine control unit (DEUTZ EMR2 J1939 message), "
                        f"0 to 250. Raw {error.group(1)} means error and {missing.group(1)} means missing.",
         "aliases": ["J1939 Engine Stop Information"], "source": source(row, "J1939 Engine Stop Information")})

    return sorted(points.values(), key=lambda point: (point["address"], point.get("mask", 0)))
