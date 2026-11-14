"""Woodward easYgen-3000XT Series manual B37574 (3100XT-P1/3200XT-P1): Modbus data protocol 5010 (9.2.4).

The table lists bus addresses (Modicon reference 450001 = bus address 50000, chapter 7.6) with a size,
parameter index, unit, scale and model column. Only rows whose model column reads "All" are mapped. The
manual states that registers are big-endian and that the high word of a 32-bit value goes to the lower
address; int32 rows are mapped with that word order. "Scale *N" is read as raw = value x N (the manual
does not define the column). BITLIST registers are declared int16 and read as u16 for masks and flags.
"""
import re
from decimal import Decimal

from sourcelib import modicon_reference, pdf_page_count, pdf_pages, require

DOCUMENT = "B37574"
PAGES = 1297
FOOTER = re.compile(r"^\s*(?:B37574\s+easYgen-3000XT Series\s+(\d+)|(\d+)\s+easYgen-3000XT Series\s+B37574)\s*$")
HEADER = re.compile(r"^\s*Modbus-\s+Size\s+Index\s+Description\s+Unit\s+Scale\s+Model\s*$")
ROW = re.compile(r"^\s{0,2}(5\d{4})\s{2,}(\S.*?)\s*$")
TYPES = {"int16": "i16", "uint16": "u16", "int32": "i32", "uint32": "u32"}
UNITS = {"Hz": "Hz", "W": "W", "V": "V", "A": "A", "rpm": "/min", "°C": "Cel", "kPa": "kPa", "h": "h",
         "MWh": "MW.h", "": None}
REFERENCE = "Protocol 5010 (Basic Visualization)"

EXPONENTS = {
    "3181": ("power_exponent", "Power", "W", "power"),
    "3182": ("voltage_exponent", "Volts", "V", "voltage"),
    "3183": ("current_exponent", "Amps", "A", "current"),
}
# Index -> (point id, row label, size, unit text). Scales are parsed.
VALUES = {
    "144": ("generator_frequency", "Generator frequency", "int16", "Hz"),
    "246": ("generator_active_power", "Total generator power", "int16", "W"),
    "248": ("generator_voltage_l1_l2", "Generator voltage L1-L2", "int16", "V"),
    "255": ("generator_current_l1", "Generator current 1", "int16", "A"),
    "10100": ("engine_speed", "Engine Pickup speed", "int16", "rpm"),
    "10110": ("battery_voltage", "Battery voltage", "int16", "V"),
    "2540": ("start_requests", "Engine, number of startrequests", "int16", ""),
    "15202": ("j1939_coolant_temperature", "Engine Coolant Temperature (SPN 110)", "int16", "°C"),
    "15205": ("j1939_oil_pressure", "Engine Oil Pressure (SPN 100)", "int16", "kPa"),
    "135": ("generator_active_power_long", "Total gen. power", "int32", "W"),
    "108": ("generator_voltage_l1_l2_long", "Gen. voltage L1-L2", "int32", "V"),
    "111": ("generator_current_l1_long", "Gen. current 1", "int32", "A"),
    "2520": ("generator_active_energy", "Gen. real energy", "int32", "MWh"),
    "2568": ("generator_operating_hours", "Gen. hours of operation", "int32", "h"),
}
ALARM_FLAGS = {
    "05.01 Engine Over speed 1 latched": "overspeed_1",
    "05.02 Engine Over speed 2 latched": "overspeed_2",
    "05.03 Engine under speed 1 latched": "underspeed_1",
    "05.04 Engine under speed 2 latched": "underspeed_2",
    "05.05 Unintended stop detected latched": "unintended_stop",
    "05.07 Speed detection alarm latched": "speed_detection_alarm",
    "05.06 Shutdown malfunction detected latched": "shutdown_malfunction",
    "08.05 GCB fail to close latched": "gcb_fail_to_close",
    "08.06 GCB fail to open latched": "gcb_fail_to_open",
    "08.07 MCB fail to close latched": "mcb_fail_to_close",
    "08.08 MCB fail to open latched": "mcb_fail_to_open",
    "08.10 General CAN-J1939 fault latched": "can_fault_j1939",
    "05.08 Start fail detected latched": "start_fail",
    "05.09 Maintenance days exceeded latched": "maintenance_days_exceeded",
    "05.10 Maintenance hours exceeded latched": "maintenance_hours_exceeded",
    "08.18 CANopen error at CAN Interface 1": "canopen_error_can_interface_1",
}
CONTROL_MODES = {1: "AUTO", 2: "STOP", 4: "MANUAL", 8: "TEST"}


def flat(text):
    return " ".join(text.split())


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


def interface_rules(data):
    """Chapter 7.6: transports, Modicon convention, bus address example, block-read excerpt, data format."""
    first = 910
    pages = pdf_pages(data, first, first + 15)
    start = find_page(pages, first, r"^7\.6\s{2,}Modbus Protocol\s*$", "the chapter 7.6 heading")
    end = find_page(pages, first, r"^7\.7\s{2,}Load Sharing\s*$", "the chapter 7.7 heading")
    text = flat("\n".join(pages[start - first:end - first + 1]))
    for statement in ("Modbus RTU Slave module for RS-485 connections", "Modbus/TCP Slave",
                      'can be read via the "Read Holding Register" function',
                      "All addresses in this document comply with the Modicon address convention",
                      "Modbus registers are read and written according to the Modbus standard as Big-endian.",
                      "INTEGER 32 2",
                      "LOGMAN 7 Little-endian is used for LogicsManager to be compatible with (non-XT) easYgen series"):
        require(statement in text, f"{DOCUMENT} 7.6: statement missing: {statement}")
    match = re.search(r"The Modbus starting address (4\d{5}) of the visualization data may become bus address "
                      r"(\d+) for example", text)
    require(match, f"{DOCUMENT} 7.6: bus address example missing")
    require(modicon_reference(match.group(1), "holding_register") == int(match.group(2)),
            f"{DOCUMENT} 7.6: bus address example is not reference minus 400001")
    excerpt = {label: reference for reference, label in re.findall(
        r"\b(4\d{5}) (Protocol-ID, always 5010|Total engine hours \(j1939-HOURS\))", text)}
    require(len(excerpt) == 2, f"{DOCUMENT} 7.6: block read excerpt missing")
    return excerpt


def high_word_first(data):
    """Chapter 6.5.1.2 setpoint examples: an INTEGER 32 value is written high word first."""
    first = 840
    pages = pdf_pages(data, first, first + 15)
    statement = ("Modbus length = 2 (INTEGER 32) The high word must be written to the lower address and the low "
                 "word must be written to the higher address.")
    found = [first + index for index, text in enumerate(pages) if statement in flat(text)]
    require(found, f"{DOCUMENT}: 32-bit word order statement missing")
    return found[0]


def exponent_semantics(data):
    """Chapter 4.7.3: exponent parameter ranges and Tables 83-85: value = transfer x 10^setting."""
    first = 630
    pages = pdf_pages(data, first, first + 10)
    start = find_page(pages, first, r"^4\.7\.3\s{2,}Modbus Protocol\s*$", "the chapter 4.7.3 heading")
    end = find_page(pages, first, r"^4\.7\.4\s{2,}CAN Interfaces\s*$", "the chapter 4.7.4 heading")
    text = flat("\n".join(pages[start - first:end - first + 1]))
    ranges = {}
    for index, low, high in re.findall(r"\b(318[123]) (?:Power|Voltage|Current) \[[WVA]\] exponent 2 (-?\d) to "
                                       r"(-?\d)\b", text):
        ranges[index] = set(range(int(low), int(high) + 1))
    require(set(ranges) == {"3181", "3182", "3183"}, f"{DOCUMENT} 4.7.3: exponent parameter ranges missing")
    require(text.count("(16 Bit, max. 32767)") == 3, f"{DOCUMENT} 4.7.3: transfer value headers missing")
    examples = re.findall(r"(-?\d) 10-?\d ([\d.]+) ([WVA]) / 10-?\d [WVA] (\d+) ", text)
    require(len(examples) == 10, f"{DOCUMENT} 4.7.3: worked examples missing")
    for setting, measured, _, transfer in examples:
        expected = int(Decimal(measured) / Decimal(10) ** int(setting))
        require(expected == int(transfer), f"{DOCUMENT} 4.7.3: example {measured} at 10^{setting} is not {transfer}")
    tables = [first + index for index, page in enumerate(pages) if "Table 83: Power measurement example" in page]
    require(len(tables) == 1, f"{DOCUMENT} 4.7.3: Table 83 missing")
    return ranges, tables[0]


def table_lines(data):
    first = 980
    pages = pdf_pages(data, first, first + 50)
    start = find_page(pages, first, r"^9\.2\.4\s{2,}Protocol 5010 \(Basic Visualization\)\s*$", "the 5010 heading")
    end = find_page(pages, first, r"^9\.2\.5\s{2,}Protocol 5011", "the chapter 9.2.5 heading")
    lines = []
    for page in range(start, end):
        page_lines = pages[page - first].split("\n")
        footer = check_footer(page_lines, page)
        headers = [index for index, line in enumerate(page_lines) if HEADER.match(line)]
        require(len(headers) == 1 and re.fullmatch(r"\s*Address\s*", page_lines[headers[0] + 1]),
                f"{DOCUMENT} page {page}: 5010 table header missing")
        if page == start:
            heading = [index for index, line in enumerate(page_lines) if line.startswith("9.2.4")]
            require(heading[0] < headers[0], f"{DOCUMENT} page {page}: 5010 header before its heading")
        lines.extend((page, line) for line in page_lines[headers[0] + 2:footer])
    return lines


def table_rows(data):
    rows = []
    current = None
    for page, line in table_lines(data):
        if not line.strip():
            continue
        match = ROW.match(line)
        if match:
            fields = re.split(r"\s{2,}", match.group(2))
            size = fields.pop(0) if fields[0] in TYPES else None
            index = fields.pop(0) if fields and re.fullmatch(r"\d+", fields[0]) else None
            current = {"address": int(match.group(1)), "size": size, "index": index, "fields": fields,
                       "page": page, "more": []}
            rows.append(current)
        elif re.match(r"^\s{0,2}\S", line):
            current = None
        else:
            require(current is not None, f"{DOCUMENT} page {page}: continuation line without a row: {line.strip()!r}")
            current["more"].append(line.strip())
    return rows


def one_row(rows, index, label, size):
    found = [row for row in rows if row["index"] == index and row["fields"] and row["fields"][0] == label]
    require(len(found) == 1, f"{DOCUMENT}: expected one 5010 row {index} {label!r}, found {len(found)}")
    row = found[0]
    require(row["size"] == size, f"{DOCUMENT} {row['address']}: size {row['size']}, expected {size}")
    require(not any(re.search(r"\bEG\d{4}", text) for text in [*row["fields"], *row["more"]]),
            f"{DOCUMENT} {row['address']}: row is limited to some models")
    return row


def source(row, label):
    return {"address": str(row["address"]), "page": row["page"], "reference": f"{REFERENCE}: {label}"}


def scale_exponent(text, address):
    match = re.fullmatch(r"\*(1(0*))", text)
    require(match, f"{DOCUMENT} {address}: scale {text} is not a power of ten")
    return -len(match.group(2))


def extract(data, selector=None):
    require(pdf_page_count(data) == PAGES, f"{DOCUMENT}: unexpected page count")
    excerpt = interface_rules(data)
    order_page = high_word_first(data)
    ranges, example_page = exponent_semantics(data)
    rows = table_rows(data)
    points = {}

    def add(point):
        require(point["id"] not in points, f"{DOCUMENT}: duplicate point {point['id']}")
        points[point["id"]] = point

    for label, reference in excerpt.items():
        table_label = {"Protocol-ID, always 5010": "Protocoll-ID, always 5010"}.get(label, label)
        found = [row for row in rows if row["fields"] and row["fields"][0] == table_label]
        require(len(found) == 1 and found[0]["address"] == modicon_reference(reference, "holding_register"),
                f"{DOCUMENT}: {label} is not at reference {reference} minus 400001 in the 5010 table")

    exponent_ids = {}
    for index, (point_id, word, unit, noun) in EXPONENTS.items():
        found = [row for row in rows if row["index"] == index]
        require(len(found) == 1 and found[0]["size"] == "int16", f"{DOCUMENT}: exponent row {index} missing")
        row = found[0]
        require(row["fields"][-1] == "All", f"{DOCUMENT} {row['address']}: exponent row is model-specific")
        text = flat(" ".join([*row["fields"][:-1], *row["more"]]))
        match = re.fullmatch(rf"Skaling {word} \(16 bits\) Exponent 10\* {unit} \(([-\d;]+)\)", text)
        require(match, f"{DOCUMENT} {row['address']}: unexpected exponent row {text!r}")
        values = sorted(int(value) for value in match.group(1).split(";"))
        require(set(values) == ranges[index], f"{DOCUMENT} {row['address']}: exponent range differs from {index}")
        label = text.rsplit(" (", 1)[0]
        add({"id": point_id, "address": row["address"], "type": "i16",
             "description": f"Power-of-ten exponent of the 16-bit {noun} values (parameter {index}, values "
                            f"{values}); see the examples from page {example_page}.",
             "aliases": [label], "source": source(row, label)})
        exponent_ids[row["address"]] = (index, point_id)

    for index, (point_id, label, size, unit_text) in VALUES.items():
        row = one_row(rows, index, label, size)
        fields = row["fields"]
        require(fields[-1] == "All", f"{DOCUMENT} {row['address']}: model column is {fields[-1]!r}")
        unit, scale = (fields[1], fields[2]) if len(fields) == 4 else ("", fields[1])
        require(len(fields) in (3, 4) and unit == unit_text, f"{DOCUMENT} {row['address']}: unexpected unit {fields}")
        point = {"id": point_id, "address": row["address"], "type": TYPES[size]}
        if size.endswith("32"):
            point.update(wordOrder="big", byteOrder="big")
        if scale == "format":
            text = flat(" ".join(row["more"]))
            match = re.fullmatch(r"defined by index (\d+) \(Modbus- Address (5\d{4})\)", text)
            require(match and exponent_ids.get(int(match.group(2)), (None,))[0] == match.group(1),
                    f"{DOCUMENT} {row['address']}: exponent reference {text!r} does not match its register")
            require(size == "int16", f"{DOCUMENT} {row['address']}: exponent format on a 32-bit value")
            point["conversion"] = {"exponent10": {"point": exponent_ids[int(match.group(2))][1]}}
        else:
            require(not row["more"], f"{DOCUMENT} {row['address']}: unexpected continuation {row['more']}")
            exponent = scale_exponent(scale, row["address"])
            if exponent:
                point["conversion"] = {"exponent10": exponent}
        if UNITS[unit]:
            point["unit"] = UNITS[unit]
        if size.endswith("32"):
            point["description"] = (f"Two registers, high word at the lower address (big-endian data format, "
                                    f"chapter 7.6; word order statement on page {order_page}).")
        point.update(aliases=[label], source=source(row, label))
        add(point)

    found = [row for row in rows if row["fields"] == ["BITLIST"] and row["more"]
             and row["more"][0].startswith("Control mode (STOP/AUTO/MANUAL/TEST)")]
    require(len(found) == 1 and found[0]["size"] == "int16", f"{DOCUMENT}: control mode row missing")
    row = found[0]
    label, mask, model = re.split(r"\s{2,}", row["more"][0])
    require((mask, model) == ("Mask: 000Fh", "All"), f"{DOCUMENT} {row['address']}: unexpected control mode mask")
    values = {}
    for text in row["more"][1:]:
        value, name = re.fullmatch(r"(\d+)=(\w+) - \d\d\.\d\d Operation Mode \w+", text).groups()
        values[int(value)] = name
    require(values == CONTROL_MODES, f"{DOCUMENT} {row['address']}: control mode values differ")
    add({"id": "control_mode", "address": row["address"], "type": "u16", "mask": 0x000F,
         "enum": {"values": [{"value": value, "name": name.lower(), "label": name}
                             for value, name in sorted(values.items())]},
         "description": "Declared int16 BITLIST; read as unsigned for the mask.",
         "aliases": [label], "source": source(row, label)})

    label = "BITLIST Alarms 1 latched (unacknowledged)"
    row = one_row(rows, "10133", label, "int16")
    require(len(row["fields"]) == 1, f"{DOCUMENT} {row['address']}: unexpected alarm row")
    flags = {}
    for text in row["more"]:
        name, mask, model = re.fullmatch(r"(.+?)\s{2,}Mask: ([0-9A-F]{4})h\s+(All)", text).groups()
        mask = int(mask, 16)
        require(mask & (mask - 1) == 0 and name in ALARM_FLAGS, f"{DOCUMENT} {row['address']}: unexpected flag {name}")
        flags[mask.bit_length() - 1] = {"bit": mask.bit_length() - 1, "name": ALARM_FLAGS[name], "label": name}
    require(sorted(flags) == list(range(16)) and len({flag["name"] for flag in flags.values()}) == 16,
            f"{DOCUMENT} {row['address']}: alarm bits incomplete")
    add({"id": "engine_alarms_latched", "address": row["address"], "type": "u16",
         "flags": {"flags": [flags[bit] for bit in sorted(flags)]},
         "description": "Engine alarms 1, latched and not yet acknowledged. Declared int16 BITLIST; read as unsigned.",
         "aliases": [label.removeprefix("BITLIST ")], "source": source(row, label.removeprefix("BITLIST "))})

    label = "J1939 EMR Engine Stop Information"
    row = one_row(rows, "15304", label, "uint16")
    require(row["fields"][1:] == ["All"], f"{DOCUMENT} {row['address']}: unexpected stop information row")
    require(row["more"][0] == "(refer to DEUTZ-specific J1939-Message)", f"{DOCUMENT} {row['address']}: unexpected row")
    named = [re.fullmatch(r'"(\w+(?: \d)?)" Value="(\d+)"', text).groups() for text in row["more"][1:]]
    sentinels = {name: int(value) for name, value in named if not name.startswith("Type")}
    types = {int(value): name for name, value in named if name.startswith("Type")}
    require(sentinels == {"Missing": 65535, "Error": 65279}, f"{DOCUMENT} {row['address']}: unexpected sentinels")
    require(types == {value: f"Type {value}" for value in range(10)}, f"{DOCUMENT} {row['address']}: unexpected types")
    add({"id": "j1939_engine_stop_information", "address": row["address"], "type": "u16",
         "enum": {"values": [{"value": value, "name": f"type_{value}", "label": name}
                             for value, name in sorted(types.items())]},
         "invalid": sorted(sentinels.values()),
         "description": "Engine stop information from the engine control unit (DEUTZ-specific J1939 message). "
                        "Raw 65279 means error and 65535 means missing.",
         "aliases": [label], "source": source(row, label)})

    return sorted(points.values(), key=lambda point: point["address"])
