"""Danfoss VLT Micro Drive FC 51 Operating Instructions (MG.02.A4.02, PDF): parameter readouts.

Parameters are holding registers at PDU address 10 x parameter number - 1 (section 5.4.1); the
manual's read example maps PNU 342 to starting address 0x0D5B. Values are whole numbers scaled by the
parameter's conversion index (section 6.2.1). The 32-bit write example (PNU 734, page 34) sends the
high-order register first. Units come from the parameter list on page 44 where it shows them in
brackets, or from the parameter name (Running Hours, kWh Counter); the manual gives no unit for
16-30 DC Link Voltage, so that point has none.
"""
import re

from sourcelib import pdf_pages, require

TYPES = {"Int16": "i16", "Uint16": "u16", "Int32": "i32", "Uint32": "u32"}
# (group, number): (point id, parameter description, type, conversion index, unit, unit shown on page 44)
SELECTED = {
    (15, 1): ("running_hours", "Running Hours", "Uint32", 0, "h", None),
    (15, 2): ("energy_counter", "kWh Counter", "Uint32", 0, "kW.h", None),
    (16, 3): ("status_word", "Status Word", "Uint16", 0, None, None),
    (16, 10): ("power", "Power [kW]", "Uint16", -3, "kW", "16-10Power[kW]"),
    (16, 12): ("motor_voltage", "Motor Voltage", "Uint16", 0, "V", "16-12MotorVoltage[V]"),
    (16, 13): ("output_frequency", "Frequency", "Uint16", -1, "Hz", "16-13Frequency[Hz]"),
    (16, 14): ("motor_current", "Motor Current", "Uint16", -2, "A", "16-14MotorCurrent[A]"),
    (16, 30): ("dc_link_voltage", "DC Link Voltage", "Uint16", 0, None, None),
    (16, 90): ("alarm_word", "Alarm Word", "Uint32", 0, None, None),
    (16, 92): ("warning_word", "Warning Word", "Uint32", 0, None, None),
}
TABLE_PAGES = {15: 57, 16: 58}
ROW = re.compile(r"\b(\d+) - (\d+)\s{2,}(.+?)\s{2,}(\S+)\s+(?:1 set-up|All set-ups)\s+(?:TRUE|FALSE)\s+"
                 r"(-?\d+|-)\s+(Int\d+|Uint\d+|VisibleString)\s*$")
# Alarm and warning words (section 7.1.1, page 60): parameter number -> column header
WORD_COLUMNS = {1690: "AlarmWord", 1692: "WarningWord", 1694: "ExtendedStatusWord"}
# Cells whose column the parser must place exactly: (bit, column header, text)
WORD_CHECKS = [(0, "AlarmWord", "Brake check"), (0, "ExtendedStatusWord", "Ramping"),
               (6, "WarningWord", "Torque limit"), (12, "AlarmWord", "Short Circuit"),
               (25, "WarningWord", "Current limit"), (29, "AlarmWord", "Drive initialised"),
               (31, "ExtendedStatusWord", "DatabaseBusy")]
# Status word according to FC profile (section 5.6.3): bit -> (flag name, text for bit value 1)
STATUS_FLAGS = {
    0: ("control_ready", "Control ready"),
    1: ("unit_ready", "Unit ready"),
    2: ("enable", "Enable"),
    3: ("trip", "Error, trip"),
    4: ("error_no_trip", "Error (no trip)"),
    6: ("trip_locked", "Trip locked"),
    7: ("warning", "Warning"),
    8: ("speed_equals_reference", "Speed = reference"),
    9: ("bus_control", "Bus control"),
    10: ("frequency_limit_ok", "Frequency limit OK"),
    11: ("running", "Running"),
    12: ("resistor_brake_fault", "Resistor brake fault"),
    13: ("voltage_exceeded", "Voltage exceeded"),
    14: ("torque_exceeded", "Torque exceeded"),
    15: ("thermal_warning", "Thermal warning"),
}


def flat(text):
    return " ".join(text.split())


def check_addressing(data):
    page27, page30 = pdf_pages(data, 27)[0], pdf_pages(data, 30)[0]
    require("Holding register 40001 is addressed as register 0000" in flat(page27),
            "FC 51 page 27: holding register reference rule missing")
    require("translated to Modbus register address as (10 x parameter number -1)DECIMAL" in flat(page30),
            "FC 51 page 30: parameter address rule missing")
    page33 = flat(pdf_pages(data, 33)[0])
    match = re.search(r"Read PNU (\d+) which is mapped to register 0x([0-9A-F]{4})\(RegAdr = \1 x 10 - 1\) "
                      r"Field Nam e Ex am ple \( HEX\) Slave address 01 Function 03 "
                      r"Starting Address HI ([0-9A-F]{2}) Starting Address LO ([0-9A-F]{2})", page33)
    require(match, "FC 51 page 33: read holding registers example missing")
    pnu, mapped, high, low = int(match.group(1)), int(match.group(2), 16), match.group(3), match.group(4)
    require(10 * pnu - 1 == mapped == int(high + low, 16), "FC 51 page 33: example address disagrees")


def check_word_order(data):
    page34 = flat(pdf_pages(data, 34)[0])
    match = re.search(r"Write (\d+) \([\d.]+s\) to PNU(\d+) \(4-bytes\) mapped to 0 x ([0-9A-F]{4}) .*? "
                      r"Write Data HI \(Register (\d+)\) ([0-9A-F]{2}) Write Data LO \(Register \4\) ([0-9A-F]{2}) "
                      r"Write Data HI \(Register (\d+)\) ([0-9A-F]{2}) Write Data LO \(Register \7\) ([0-9A-F]{2})",
                      page34)
    require(match, "FC 51 page 34: 32-bit write example missing")
    value, pnu, mapped = int(match.group(1)), int(match.group(2)), int(match.group(3), 16)
    first, second = int(match.group(4)), int(match.group(7))
    words = [int(match.group(5) + match.group(6), 16), int(match.group(8) + match.group(9), 16)]
    require(10 * pnu - 1 == mapped == first and second == first + 1, "FC 51 page 34: example address disagrees")
    require(words[0] << 16 | words[1] == value and words[0] != words[1],
            "FC 51 page 34: example does not show high-order register first")


def conversion_table(data):
    page = pdf_pages(data, 45)[0]
    require("Table 6.1: Conversion table" in page, "FC 51 page 45: conversion table missing")
    factors = {int(index): factor for index, factor in
               re.findall(r"^\s*(-?\d)\s{10,}(\d+(?:\.\d+)?)\b", page, re.MULTILINE)}
    for index in (0, -1, -2, -3):
        require(factors.get(index) == ("1" if index == 0 else "0." + "0" * (-index - 1) + "1"),
                f"FC 51 conversion index {index}: unexpected factor {factors.get(index)!r}")
    return factors


def status_flags(data):
    page = pdf_pages(data, 37)[0]
    require("5.6.3 St at us Wor d Accor ding t o FC Pr of ile ( STW)" in page, "FC 51 page 37: STW table missing")
    rows = {int(bit): (zero, one) for bit, zero, one in
            re.findall(r"^\s*(\d\d)\s{2,}(\S.*?)\s{2,}(\S.*?)\s*$", page.split("( STW)")[1], re.MULTILINE)}
    require(sorted(rows) == list(range(16)), f"FC 51 STW: unexpected bit rows {sorted(rows)}")
    flags = []
    for bit, (name, text) in sorted(STATUS_FLAGS.items()):
        zero, one = rows[bit]
        require(one == text, f"FC 51 STW bit {bit}: expected {text!r}, found {one!r}")
        flags.append({"bit": bit, "name": name, "label": one, "description": f"0: {zero}; 1: {one}"})
    return flags


def snake(text):
    name = re.sub(r"[^a-z0-9]+", "_", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text).lower()).strip("_")
    require(re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name), f"FC 51: cannot name {text!r}")
    return name


def word_bits(data):
    """Bit texts of the alarm, warning and extended status words, assigned by column position."""
    lines = pdf_pages(data, 60)[0].splitlines()
    heads = [index for index, line in enumerate(lines) if "Alarm Wor d" in line and "Bit" in line]
    require(len(heads) == 1, "FC 51 page 60: alarm word table header missing")
    numbers = re.findall(r"Par (\d+)", lines[heads[0] - 1])
    require([int(number) for number in numbers] == list(WORD_COLUMNS), "FC 51 page 60: unexpected parameters")
    header = lines[heads[0]]
    centres = {}
    for match in re.finditer(r"\S+(?: \S+)*", header):
        name = "".join(match.group(0).split())
        if name in WORD_COLUMNS.values():
            centres[name] = (match.start() + match.end()) / 2
    require(list(centres) == list(WORD_COLUMNS.values()), f"FC 51 page 60: unexpected header {header!r}")
    bits = {name: {} for name in centres}
    for line in lines[heads[0] + 1:]:
        row = re.match(r"^(?:\d)?\s+(\d+)\s+([0-9A-F]+)\s+(\d+)(?=\s|$)", line)
        if not row:
            if bits["AlarmWord"]:
                break
            continue
        bit, mask, value = int(row.group(1)), int(row.group(2), 16), int(row.group(3))
        require(mask == value == 1 << bit, f"FC 51 page 60: bit {bit} masks disagree")
        for cell in re.finditer(r"\S+(?: \S+)*", line[row.end():]):
            start, end = row.end() + cell.start(), row.end() + cell.end()
            column = min(centres, key=lambda name: abs(centres[name] - (start + end) / 2))
            require(bit not in bits[column], f"FC 51 page 60: two cells for bit {bit} in {column}")
            bits[column][bit] = cell.group(0).strip('"')
    require(set().union(*bits.values()) <= set(range(32)) and 31 in bits["ExtendedStatusWord"],
            "FC 51 page 60: bit table incomplete")
    for bit, column, text in WORD_CHECKS:
        require(bits[column].get(bit) == text, f"FC 51 page 60: bit {bit} of {column} is {bits[column].get(bit)!r}")
    return bits


def word_flags(bits):
    """Flags for one word; a cell reading "Undefined" names no condition and is left out."""
    flags = [{"bit": bit, "name": snake(text), "label": text} for bit, text in sorted(bits.items())
             if text != "Undefined"]
    require(len({flag["name"] for flag in flags}) == len(flags), "FC 51 page 60: duplicate flag name")
    return flags


def extract(data, selector=None):
    check_addressing(data)
    check_word_order(data)
    conversion_table(data)
    menu = "".join(pdf_pages(data, 44)[0].split())
    words = word_bits(data)
    points = {}
    for group, page_number in TABLE_PAGES.items():
        page = pdf_pages(data, page_number)[0]
        for line in page.splitlines():
            match = ROW.search(line)
            if not match or int(match.group(1)) != group:
                continue
            key = (group, int(match.group(2)))
            if key not in SELECTED:
                continue
            point_id, description, kind, index, unit, shown = SELECTED[key]
            require(point_id not in points, f"FC 51 parameter {group}-{key[1]}: listed twice")
            require(match.group(3).strip() == description and match.group(6) == kind
                    and match.group(5) == str(index),
                    f"FC 51 parameter {group}-{key[1]}: unexpected row {line.strip()!r}")
            require(shown is None or shown in menu, f"FC 51 parameter {group}-{key[1]}: unit not shown on page 44")
            pnu = group * 100 + key[1]
            point = {"id": point_id, "label": description, "aliases": [f"{group}-{key[1]:02d}"],
                     "address": 10 * pnu - 1, "type": TYPES[kind]}
            if point_id == "status_word":
                point["flags"] = {"flags": status_flags(data)}
                point["description"] = "Status word according to the FC profile (section 5.6.3)."
            elif pnu in WORD_COLUMNS:
                point["flags"] = {"flags": word_flags(words[WORD_COLUMNS[pnu]])}
                point["description"] = "Bit meanings from section 7.1.1 (page 60); unlisted bits are not described."
            elif index:
                point["conversion"] = {"exponent10": index}
            if unit:
                point["unit"] = unit
            elif point_id == "dc_link_voltage":
                point["description"] = "The manual states no unit for this parameter."
            reference = f"Parameter overview {group}-**, PNU {pnu}"
            if "flags" in point:
                reference += ("; bits: section 5.6.3, page 37" if point_id == "status_word"
                              else "; bits: section 7.1.1, page 60")
            point["source"] = {"address": f"{group}-{key[1]:02d}", "page": page_number, "reference": reference}
            points[point_id] = point
    missing = {value[0] for value in SELECTED.values()} - points.keys()
    require(not missing, f"FC 51: missing parameters {sorted(missing)}")
    return sorted(points.values(), key=lambda point: point["address"])
