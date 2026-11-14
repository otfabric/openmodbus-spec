"""Siemens SINAMICS Modbus RTU register tables (PDF): G120 Fieldbuses Function Manual and V20
Operating Instructions.

The selector is "g120c" or "v20". Both manuals list 16-bit holding registers as 4xxxx numbers with
access, unit, scaling factor and value range, and name FC 03 (Read Holding Registers) for reading.

Address base. The G120 manual's read example sends 00 6D for register 40110 and its write example
00 63 for register 40100 (tables 5-20 and 5-23), so register 4xxxx is PDU address xxxx - 1; both
frames are parsed and checked. The V20 table prints each register twice, as "Inverter" number and as
"MODBUS" number, starting with 0 and 40001; every row must satisfy MODBUS = Inverter + 40001, and the
Inverter number is the address.

Scaling. The register holds the value multiplied by the scaling factor: the V20 manual says so
("Parameter scaling"), and in both tables the ranges at factor 100 end at 327.67, the 16-bit limit
divided by the factor. Every selected range must fit 16 bits after scaling.

Data type. Neither table states one. A register whose documented range has a negative bound is
decoded as i16, any other as u16; over the documented range both readings give the same value. Rows
without a numeric range (ON/OFF texts, process data setpoint and actual value) are not selected,
except the status word, which is a bit field. The V20 table maps single-bit registers to status word
bits ("ZSW:n"); those rows name the flags of the V20 status word. Which text of an ON/OFF pair
stands for 1 is not stated, so the flags keep both texts in their description.
"""
from decimal import Decimal
import re

from sourcelib import modicon_reference, pdf_page_count, pdf_pages, require

UNITS = {"Hz": "Hz", "RPM": "/min", "A": "A", "Nm": "N.m", "kW": "kW", "kWh": "kW.h", "V": "V", "%": "%"}

# G120: (table 5-n, description, access): (point id, unit in the table, scaling factor, parameter)
G120C = {
    (12, "Status word", "R"): ("status_word", None, 1, "Process data 1"),
    (13, "AO 0", "R"): ("analog_output_0", "%", 100, "r0774.0"),
    (13, "AI 0", "R"): ("analog_input_0", "%", 100, "r0755 [0]"),
    (14, "Rated power", "R"): ("rated_power", "kW", 100, "r0206"),
    (14, "Reference speed", "R/W"): ("reference_speed", "RPM", 1, "p2000"),
    (14, "Speed setpoint", "R"): ("speed_setpoint", "RPM", 1, "r0020"),
    (14, "Actual speed value", "R"): ("speed", "RPM", 1, "r0022"),
    (14, "Output frequency", "R"): ("output_frequency", "Hz", 100, "r0024"),
    (14, "Output voltage", "R"): ("output_voltage", "V", 1, "r0025"),
    (14, "DC link voltage", "R"): ("dc_link_voltage", "V", 1, "r0026"),
    (14, "Current actual value", "R"): ("output_current", "A", 100, "r0027"),
    (14, "Actual torque value", "R"): ("torque", "Nm", 100, "r0031"),
    (14, "Actual active power", "R"): ("active_power", "kW", 100, "r0032"),
    (14, "Energy consumption", "R"): ("energy_consumption", "kWh", 1, "r0039"),
    (15, "Failure number, index 0", "R"): ("fault_number", "--", 1, "r0947 [0]"),
    (15, "Alarm number", "R"): ("alarm_number", "--", 1, "r2110 [0]"),
    (15, "Actual alarm code", "R"): ("alarm_code", "--", 1, "r2132"),
    (15, "PRM ERROR code", "R"): ("parameter_error_code", "--", 1, "--"),
}
G120_CAPTION = re.compile(r"^Table 5- ?(1[2-9]) (?:Assigning the Modbus registers to|Modbus registers for) ")
G120_END = "5.4.5 Acyclic communication via Modbus RTU"
G120_PROCESS = re.compile(r"^(4\d{4}) (.+?) (R/W|R) (\d+) (Process data \d)$")
G120_ROW = re.compile(r"^(4\d{4}) (?:(4\d{4}) )?(.+?) (R/W|R) (--|%|kWh|kW|A|s|RPM|Hz|V|Nm|h) (\d+|--) (.+)$")
G120_ELLIPSIS = re.compile(r"^… … …$")
G120_RANGE = re.compile(r"^(- ?[\d.]+|[\d.]+) ?… ?(-?[\d.]+) (.+)$")
G120_READ = re.compile(
    r"Table 5- ?20 Structure of a read request via slave number (\d+), example Value Byte Description "
    r"([0-9A-F]{2}) h 0 Slave address ([0-9A-F]{2}) h 1 Function code "
    r"([0-9A-F]{2}) h 2 Register start address .High. \(register (4\d{4})\) "
    r"([0-9A-F]{2}) h 3 Register start address .Low. "
    r"([0-9A-F]{2}) h 4 Number of registers .High. \((\d+) registers: (4\d{4}); (4\d{4})\) "
    r"([0-9A-F]{2}) h 5 number of registers .Low. ")
G120_WRITE = re.compile(
    r"Table 5- ?23 Structure of a write request for slave number (\d+), example Value Byte Description "
    r"([0-9A-F]{2}) h 0 Slave address ([0-9A-F]{2}) h 1 Function code "
    r"([0-9A-F]{2}) h 2 Register start address .High. \(write register (4\d{4})\) "
    r"([0-9A-F]{2}) h 3 Register start address .Low. ")

# V20: (description, occurrence in the table): (point id, unit in the table, scaling factor, read source)
V20 = {
    ("Frequency output", 0): ("output_frequency", "Hz", 100, "r0024"),
    ("Speed", 0): ("speed", "RPM", 1, "r0022"),
    ("Current filtered", 0): ("output_current", "A", 100, "r0027"),
    ("Torque", 0): ("torque", "Nm", 100, "r0031"),
    ("Actual power", 0): ("active_power", "kW", 100, "r0032"),
    ("Total kWh", 0): ("energy_consumption", "kWh", 1, "r0039"),
    ("DC bus voltage", 0): ("dc_bus_voltage", "V", 1, "r0026"),
    ("Reference", 0): ("frequency_reference", "Hz", 100, "r0020"),
    ("Rated power", 0): ("rated_power", "kW", 100, "r0206"),
    ("Voltage output", 0): ("output_voltage", "V", 1, "r0025"),
    ("Analog input 1", 0): ("analog_input_1", "%", 100, "r0754[0]"),
    ("Analog output 1", 0): ("analog_output_1", "%", 100, "r0774[0]"),
    ("Actual frequency", 0): ("actual_frequency", "%", 100, "HIW"),
    ("Last fault", 0): ("last_fault", "-", 1, "r0947[0]"),
    ("Last warning", 0): ("last_warning", "-", 1, "r2110"),
    ("Inverter version", 0): ("inverter_version", "-", 100, "r0018"),
    ("Inverter model", 0): ("inverter_model", "-", 1, "r0201"),
    ("Current unfiltered", 0): ("current_unfiltered", "A", 100, "r0068"),
}
# Status word bit: (flag name, description on the row's line, rest of a description that wraps to the next line)
V20_STATUS = {
    0: ("enabled", "Enabled", None),
    1: ("ready_to_run", "Ready to run", None),
    2: ("stop_run", "Stop/run", None),
    3: ("fault", "Fault", None),
    7: ("warning", "Warning", None),
    9: ("control_mode", "Control mode", None),
    10: ("run_at_maximum_frequency", "Run at maximum", "frequency"),
    14: ("forward_reverse", "Forward/reverse", None),
}
V20_ROW = re.compile(r"^(\d{1,3}) (4\d{4}) (.+?) (R/W|RW|RO|R) (-|ms|%|s|Hz|RPM|A|Nm|kWh|kW|V) (\d+|-) ?(.*)$")
V20_RESERVED = re.compile(r"^(\d{1,3}) (4\d{4}) \(Reserved\)$")
V20_RANGE = re.compile(r"^(-?[\d.]+) - (-?[\d.]+) (\S+) (\S+)$")
V20_BIT = re.compile(r"^(\S+) (\S+) ZSW:(\d+) ZSW:(\d+)$")


def lines(page):
    return [" ".join(line.split()) for line in page.splitlines() if line.strip()]


def number_type(label, low, high, factor):
    """Type from the documented range, which must fit 16 bits after scaling."""
    low, high = Decimal(low) * factor, Decimal(high) * factor
    require(low == low.to_integral_value() and high == high.to_integral_value() and low < high,
            f"SINAMICS {label}: range does not scale to whole numbers")
    kind = "i16" if low < 0 else "u16"
    bounds = (-32768, 32767) if low < 0 else (0, 65535)
    require(bounds[0] <= low and high <= bounds[1], f"SINAMICS {label}: range exceeds {kind} after scaling")
    return kind


def value_point(point_id, reference, label, unit, factor, low, high, source, note):
    exponent = Decimal(factor).log10()
    require(exponent == exponent.to_integral_value(), f"SINAMICS {label}: scaling factor {factor} is not 10^n")
    point = {"id": point_id, "address": modicon_reference(reference, "holding_register"),
             "type": number_type(label, low, high, factor)}
    if exponent:
        point["conversion"] = {"exponent10": -int(exponent)}
    if unit in UNITS:
        point["unit"] = UNITS[unit]
    point["aliases"] = [label]
    point["description"] = f"{note}; documented range {low} to {high}."
    point["source"] = source
    return point


def g120_addressing(flat):
    require("FC 03: Holding register to read data from the converter" in flat
            and "R: read via FC03; W: write via FC06; R/W: read via FC03 or write via FC06" in flat,
            "G120: FC 03 read access statement missing")
    read = G120_READ.findall(flat)
    require(len(read) == 1, "G120: read request example (table 5-20) not found once")
    slave, address, function, high, register, low, count_high, count, first, second, count_low = read[0]
    require(int(address, 16) == int(slave) and function == "03", "G120: read example is not FC 03 to the stated slave")
    require(int(high + low, 16) == modicon_reference(register, "holding_register"),
            f"G120: read example sends {high} {low} for register {register}")
    require(register == first and int(second) == int(first) + 1 and int(count_high + count_low, 16) == int(count) == 2,
            "G120: read example register count disagrees")
    write = G120_WRITE.findall(flat)
    require(len(write) == 1, "G120: write request example (table 5-23) not found once")
    slave, address, function, high, register, low = write[0]
    require(int(address, 16) == int(slave) and function == "06", "G120: write example is not FC 06 to the stated slave")
    require(int(high + low, 16) == modicon_reference(register, "holding_register"),
            f"G120: write example sends {high} {low} for register {register}")


def g120_scope(pages):
    """Table 5-1 must list the G120C USS/MB with Modbus RTU (second column, after USS)."""
    for page in pages:
        flat = " ".join(page.split())
        if re.search(r"Table 5- ?1 Assignment table - fieldbus systems via RS485", flat):
            require(re.search(r"USS Modbus BACnet P1 RTU MS/TP", flat), "G120 table 5-1: unexpected columns")
            require(re.search(r"G120C USS/MB ✓ ✓ --- ---", flat),
                    "G120 table 5-1: G120C USS/MB with Modbus RTU not listed")
            return
    require(False, "G120: table 5-1 (fieldbus systems via RS485) missing")


def extract_g120c(pages):
    flat = " ".join(" ".join(pages).split())
    require("Fieldbuses Function Manual, 11/2020, FW V4.7 SP13, A5E34229197B AG" in flat,
            "G120: document number or edition changed")
    g120_scope(pages)
    g120_addressing(flat)

    points, seen, table, done = [], set(), None, False
    full_scale = False
    for number, page in enumerate(pages, start=1):
        rows = lines(page)
        if "5.4 Communication using Modbus RTU" not in rows:
            continue
        for row in rows:
            if row == G120_END and table:
                table, done = None, True
            caption = G120_CAPTION.match(row)
            if caption and not done:
                table = int(caption.group(1))
                continue
            if table is None or not re.match(r"4\d{4}\b|… ", row):
                continue
            process, match = G120_PROCESS.match(row), G120_ROW.match(row)
            if G120_ELLIPSIS.match(row):
                continue
            require(process or match, f"G120 table 5-{table} page {number}: unexpected row {row!r}")
            if process:
                reference, label, access, factor, parameter = process.groups()
                unit, tail = None, None
            else:
                reference, _, label, access, unit, factor, tail = match.groups()
            key = (table, label, access)
            if key not in G120C:
                continue
            point_id, expected_unit, expected_factor, parameter_expected = G120C[key]
            require(key not in seen, f"G120 {label}: listed twice in table 5-{table}")
            seen.add(key)
            require(unit == expected_unit and factor == str(expected_factor),
                    f"G120 {label}: unit {unit}, scaling {factor}")
            source = {"address": reference, "page": number, "reference": f"Table 5-{table}, {label}"}
            if process:
                require(parameter == parameter_expected, f"G120 {label}: carries {parameter}")
                points.append({
                    "id": point_id, "address": modicon_reference(reference, "holding_register"), "type": "u16",
                    "aliases": [label],
                    "description": "Process data 1 sent by the converter. The manual gives the bits of status word 1 "
                                   "in its USS section; the signals are interconnected in the converter (p2080).",
                    "source": source})
                continue
            bounds = G120_RANGE.match(tail)
            require(bounds, f"G120 {label}: no numeric range in {tail!r}")
            low, high, parameter = bounds.group(1).replace(" ", ""), bounds.group(2), bounds.group(3)
            require(parameter == parameter_expected, f"G120 {label}: parameter {parameter}")
            full_scale = full_scale or (int(factor) == 100 and Decimal(high) * 100 == 32767)
            note = f"Converter parameter {parameter}" if parameter != "--" else "No converter parameter"
            points.append(value_point(point_id, reference, label, unit, int(factor), low, high, source, note))
    require(done, "G120: end of the mapping tables not found")
    require(seen == G120C.keys(), f"G120: rows not found {sorted(G120C.keys() - seen)}")
    require(full_scale, "G120: no selected range ends at the 16-bit limit divided by its scaling factor")
    return sorted(points, key=lambda point: point["address"])


def extract_v20(pages):
    flat = " ".join(" ".join(pages).split())
    require("SINAMICS V20 Inverter Operating Instructions, 01/2018, A5E34559884-009" in flat,
            "V20: document number or edition changed")
    require("The SINAMICS V20 supports only three Function Codes." in flat
            and "FC3 - Read Holding Registers" in flat, "V20: FC 3 statement missing")
    require("a parameter, which has a position after decimal point, is multiplied by a factor, to get rid of the "
            "fractional part. The scaling factor is as defined in the above table." in flat,
            "V20: parameter scaling statement missing")

    table = []  # (page, following lines, inverter number, MODBUS number, description, access, unit, factor, tail)
    inside = False
    for number, page in enumerate(pages, start=1):
        rows = lines(page)
        if "7.2 MODBUS communication" not in rows:
            continue
        for index, row in enumerate(rows):
            if row == "Mapping table":
                inside = True
            elif row == "Program example":
                inside = False
            if not inside or not re.match(r"\d{1,3} 4\d{4}\b", row):
                continue
            reserved, match = V20_RESERVED.match(row), V20_ROW.match(row)
            require(reserved or match, f"V20 mapping table page {number}: unexpected row {row!r}")
            inverter, modbus = (reserved or match).group(1, 2)
            require(int(modbus) == int(inverter) + 40001, f"V20: register {inverter} is printed as {modbus}")
            if match:
                table.append((number, rows[index + 1:index + 3], *match.groups()))
    require(table and table[0][2:5] == ("0", "40001", "Watchdog time"),
            "V20: mapping table does not start at register 0")
    require(len({row[2] for row in table}) == len(table), "V20: a register is listed twice")

    points, counts, flags, seen, status = [], {}, {}, set(), None
    for number, following, inverter, modbus, label, access, unit, factor, tail in table:
        occurrence = counts.get(label, 0)
        counts[label] = occurrence + 1
        source = {"address": f"{inverter} ({modbus})", "page": number, "reference": f"Mapping table, {label}"}
        bit = V20_BIT.match(tail)
        if bit and access == "R":
            require(bit.group(3) == bit.group(4) and (unit, factor) == ("-", "1"), f"V20 {label}: unexpected bit row")
            index = int(bit.group(3))
            require(index in V20_STATUS and V20_STATUS[index][1] == label and index not in flags,
                    f"V20: status word bit {index} is {label!r}")
            wrapped = V20_STATUS[index][2]
            if wrapped:
                require(wrapped in following, f"V20 {label}: description continues with {following!r}")
                label = f"{label} {wrapped}"
            flags[index] = {"bit": index, "name": V20_STATUS[index][0], "label": label,
                            "description": f"ON/OFF texts {bit.group(1)} / {bit.group(2)}; also readable as "
                                           f"register {inverter} ({modbus})."}
            continue
        if label == "ZSW":
            require(status is None and (access, unit, factor, tail) == ("R", "-", "1", "PZD 1 PZD 1"),
                    "V20: unexpected status word row")
            status = {"id": "status_word", "address": int(inverter), "type": "u16", "aliases": [label],
                      "source": source}
            continue
        if (label, occurrence) not in V20:
            continue
        point_id, expected_unit, expected_factor, read = V20[(label, occurrence)]
        seen.add((label, occurrence))
        require(access == "R" and unit == expected_unit and factor == str(expected_factor),
                f"V20 {label}: access {access}, unit {unit}, scaling {factor}")
        bounds = V20_RANGE.match(tail)
        require(bounds and bounds.group(3) == bounds.group(4) == read, f"V20 {label}: unexpected range {tail!r}")
        note = "Actual value (HIW)" if read == "HIW" else f"Inverter parameter {read}"
        point = value_point(point_id, modbus, label, unit, int(factor), bounds.group(1), bounds.group(2), source, note)
        require(point["address"] == int(inverter), f"V20 {label}: address differs from the inverter register number")
        points.append(point)
    require(seen == V20.keys(), f"V20: rows not found {sorted(V20.keys() - seen)}")
    require(status and flags.keys() == V20_STATUS.keys(), "V20: status word or its bit rows missing")
    status["flags"] = {"flags": [flags[index] for index in sorted(flags)]}
    status["description"] = ("Status word (ZSW, PZD 1). The mapping table assigns the listed bits; it does not state "
                             "which text of an ON/OFF pair stands for 1.")
    status["source"] = status.pop("source")
    points.append(status)
    return sorted(points, key=lambda point: point["address"])


def extract(data, selector):
    require(selector in ("g120c", "v20"), f"Unknown SINAMICS selector {selector!r}")
    pages = pdf_pages(data, 1, pdf_page_count(data))
    return extract_g120c(pages) if selector == "g120c" else extract_v20(pages)
