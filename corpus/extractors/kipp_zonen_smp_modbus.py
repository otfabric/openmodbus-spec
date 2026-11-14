"""Kipp & Zonen Smart Pyranometer Modbus communication manual (PDF), SMP series.

The selector is the model as the device-type table names it, e.g. "SMP3". Rows are
selected by register name; addresses come from the overview tables ("PDU Address +
1 = Modbus register number") and are cross-checked against the register details.
"""
import re

from sourcelib import pdf_page_count, pdf_pages, require

INPUT = "input_register"
DISCRETE = "discrete_input"
SECTIONS = {
    "Input Registers Overview": "input",
    "Holding Registers Overview": "holding",
    "Discrete Inputs Overview": "discrete",
    "Discrete Coils Overview": "coils",
    "Input Register Details": "input_details",
    "Holding Register Details": "holding_details",
    "Discrete Inputs Details": "discrete_details",
    "Discrete Coils Details": "coil_details",
    "Requesting Serial Number": "serial_details",
    "Demonstration Program": "end",
}
TYPES = {"U16": "u16", "S16": "i16", "S32": "i32"}
OVERVIEW_ROW = re.compile(
    r"^[ \t]*(\d+)[ \t]+(IO_[A-Z0-9_]+)[ \t]+(R|R/W)[ \t]+(U16|S16|S32)[ \t]+(All|N, S)[ \t]+(\S.*?)[ \t]*$")
DISCRETE_ROW = re.compile(r"^[ \t]*(\d+)[ \t]+(IO_[A-Z0-9_]+)[ \t]+R[ \t]+(0|1\(1\))[ \t]+All[ \t]+(\S.*?)[ \t]*$")
DETAIL_ROW = re.compile(r"^[ \t]*(\d+)[ \t]+(IO_[A-Z0-9_]+)(?:[ \t]{2,}(\S.*?))?[ \t]*$")
# The discrete-input overview spells this name differently from the details.
DETAIL_NAMES = {"IO_UNDEFLOW_ERROR": "IO_UNDERFLOW_ERROR"}

# name: (point id, type, conversion exponent, unit, text the overview description must contain, description)
SCALED = ("Irradiance in W/m2 = raw / 10^scale_factor. Not converted here: the draft's exponent10 "
          "reference cannot negate the scale factor.")
REGISTERS = {
    "IO_DEVICE_TYPE": ("device_type", "U16", None, None, "Device type of the sensor", "Device type of the sensor."),
    "IO_DATAMODEL_VERSION": ("data_model_version", "U16", None, None, "Version of the object data model",
                             "Data-model version; the manual describes version 107."),
    "IO_OPERATIONAL_MODE": ("operational_mode", "U16", None, None, "Operational mode", "Operational mode."),
    "IO_STATUS_FLAGS": ("status_flags", "U16", None, None, "Device Status flags",
                        "Device status and data validity flags."),
    "IO_SCALE_FACTOR": ("scale_factor", "S16", None, None, "Scale factor for sensor data",
                        "Decimal places of IO_SENSOR1_DATA and IO_RAW_SENSOR1_DATA: W/m2 = raw / 10^scale_factor "
                        "(2: /100, 1: /10, 0: x1, -1: x10). Default 0; IO_AUTO_RANGE or IO_DEF_SCALE_FACTOR can "
                        "change it."),
    "IO_SENSOR1_DATA": ("irradiance_scaled", "S16", None, None, "Temperature compensated radiation in W/m2",
                        "Temperature-compensated irradiance. " + SCALED),
    "IO_RAW_SENSOR1_DATA": ("irradiance_uncompensated_scaled", "S16", None, None,
                            "Raw, non-linearized and non-temperature compensated radiation",
                            "Calibrated irradiance before linearisation and temperature compensation. " + SCALED),
    "IO_BODY_TEMPERATURE": ("body_temperature", "S16", -1, "Cel", "Body temperature in 0.1 °C",
                            "Sensor body temperature (register resolution 0.1 °C)."),
    "IO_EXT_POWER_SENSOR": ("supply_voltage", "S16", -1, "V", "External power voltage",
                            "External supply voltage at the chassis socket (register resolution 0.1 V)."),
    "IO_ADC1_COUNTS": ("sensor_input_voltage", "S32", -2, "uV", "Input voltage sensor 1 in 0.01 µV",
                       "Input voltage of sensor 1 (register resolution 0.01 µV), most significant word first."),
    "IO_ERROR_CODE": ("error_code", "U16", None, None, "Most recent/ actual error code",
                      "Most recent or actual error code."),
    "IO_SENSOR_ON_TIMEH": ("on_time", "U16", None, "s", "On time in seconds (MSB word)",
                           "On time: IO_SENSOR_ON_TIMEH (MSB word) and IO_SENSOR_ON_TIMEL (LSB word) read as one "
                           "32-bit value."),
    "IO_SENSOR_ON_TIMEL": (None, "U16", None, "s", "On time in seconds (LSB word)", None),
    "IO_BATCH_NUMBER": ("batch_number", "U16", None, None, "Production batch number = year in YY",
                        "Production year as YY (20 = 2020); unique only together with serial_number."),
    "IO_SERIAL_NUMBER": ("serial_number", "U16", None, None, "Serial number", "Four-digit serial number."),
    "IO_SOFTWARE_VERSION": ("software_version", "U16", None, None, "Software version", "Software version."),
    "IO_HARDWARE_VERSION": ("hardware_version", "U16", None, None, "Hardware version", "Hardware version."),
}
# The details text that confirms each 0.1-unit scale.
DETAIL_SCALES = {
    "IO_BODY_TEMPERATURE": "in 0.1°C",
    "IO_EXT_POWER_SENSOR": "in 0.1 Volt",
}
INPUTS = {
    "IO_ERROR_FLAG": ("error_flag", "General hardware error",
                      "General hardware or software error; also set after every power-up until cleared."),
    "IO_CALIBRATION_ERROR": ("calibration_error", "Calibration checksum error",
                             "Sensor not calibrated or calibration checksum error."),
}
CLEARED_ON_READ = ("IO_VOID_DATA_FLAG", "IO_OVERFLOW_ERROR", "IO_UNDERFLOW_ERROR")
SCALE_TABLE = {"2": ("/", "100"), "1": ("/", "10"), "0": (None, None), "-1": ("*", "10")}


def slug(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    require(words, f"Kipp & Zonen: cannot name {text!r}")
    return "_".join(words)


def normal(text):
    return " ".join(text.split())


def read_sections(data):
    count = pdf_page_count(data)
    lines = {"preface": []}
    section = "preface"
    for page_number, page in enumerate(pdf_pages(data, 1, count), start=1):
        for line in page.split("\n"):
            heading = line.strip()
            if heading in SECTIONS:
                section = SECTIONS[heading]
                lines.setdefault(section, [])
                continue
            lines[section].append((page_number, line))
    require(set(SECTIONS.values()) <= lines.keys(), "Kipp & Zonen: register sections missing")
    return lines


def overview(lines):
    rows = {}
    for index, (page, line) in enumerate(lines):
        match = OVERVIEW_ROW.match(line)
        if not match:
            continue
        address, name, access, kind, mode, description = match.groups()
        require(name not in rows, f"Kipp & Zonen: duplicate overview row {name}")
        rows[name] = {"address": int(address), "access": access, "type": kind, "mode": mode,
                      "description": description, "page": page,
                      "next": lines[index + 1][1] if index + 1 < len(lines) else ""}
    return rows


def details(lines):
    rows = {}
    current = None
    for page, line in lines:
        match = DETAIL_ROW.match(line)
        if match and not re.match(r"^[ \t]*-?\d+[ \t]+floating point", line):
            address, name, text = match.groups()
            require(name not in rows, f"Kipp & Zonen: duplicate details row {name}")
            current = rows[name] = {"address": int(address), "page": page, "lines": [text or ""]}
        elif current is not None:
            current["lines"].append(line)
    for row in rows.values():
        row["text"] = normal(" ".join(row["lines"]))
    return rows


def device_types(row):
    values = []
    for line in row["lines"]:
        match = re.match(r"^[ \t]*((?:SMP|SGR|SHP|SUV)\d+ \((?:volt|current loop|current) version\))[ \t]+"
                         r"(\d{3})[ \t]+(\d\*?)[ \t]*$", line)
        if match:
            label, value, _ = match.groups()
            values.append({"value": int(value), "name": slug(label), "label": label})
    require(len(values) >= 10 and len({value["value"] for value in values}) == len(values),
            "Kipp & Zonen: device type table incomplete")
    return values


def operational_modes(row):
    values = []
    for line in row["lines"]:
        match = re.match(r"^[ \t]*([1-5])[ \t]+(Normal|Service|Calibration|Factory|Error) [Mm]ode[ \t]*$", line)
        if match:
            values.append({"value": int(match.group(1)), "name": match.group(2).lower(),
                           "label": f"{match.group(2)} mode"})
    require([value["value"] for value in values] == [1, 2, 3, 4, 5], "Kipp & Zonen: operational modes")
    return values


def status_flags(row):
    flags = []
    for line in row["lines"]:
        match = re.match(r"^[ \t]*(\d{1,2})[ \t]+(\S.*?\S)[ \t]{2,}see (\w+)[ \t]*$", line)
        if match:
            bit, label, see = match.groups()
            flags.append({"bit": int(bit), "name": slug(label), "label": label,
                          "description": f"See {see}."})
    require([flag["bit"] for flag in flags] == list(range(13)), "Kipp & Zonen: status flag bits")
    return flags


def check_scale_factor(row):
    found = {}
    for line in row["lines"]:
        match = re.match(r"^[ \t]*(-?\d)[ \t]+floating point result = integer register X(?:[ \t]*([/*])[ \t]*(\d+))?"
                         r"[ \t]*$", line)
        if match:
            found[match.group(1)] = (match.group(2), match.group(3))
    require(found == SCALE_TABLE, f"Kipp & Zonen: unexpected scale factor table {found}")
    require("IO_SENSOR1_DATA, IO_SENSOR2_DATA, IO_RAW_SENSOR1_DATA and IO_RAW_SENSOR2_DATA" in row["text"],
            "Kipp & Zonen: scale factor scope changed")


def extract(data, selector):
    sections = read_sections(data)
    intro = normal(" ".join(line for _, line in sections["input"][:3]))
    require(intro.startswith("Input registers are read only."), "Kipp & Zonen: input register intro missing")
    legend = normal(" ".join(line for _, line in sections["input"]))
    require("PDU Address PDU Address + 1 = Modbus® register number" in legend,
            "Kipp & Zonen: PDU address legend missing")
    preface = normal(" ".join(line for _, line in sections["preface"]))
    require("do not make a difference between a holding register and an input register" in preface,
            "Kipp & Zonen: register table statement missing")
    # The command table must list the read functions for the two tables mapped here.
    for code, name in (("0X02", "Read Discrete Inputs"), ("0X04", "Read Input Register")):
        require(f"{code} N/A {name}" in preface, f"Kipp & Zonen: function {code} {name} not implemented")

    registers = overview(sections["input"])
    register_details = details(sections["input_details"] + sections["serial_details"])
    types = device_types(register_details["IO_DEVICE_TYPE"])
    require(f"{selector} (volt version)" in {value["label"] for value in types},
            f"Kipp & Zonen: {selector} is not in the device type table")
    require("This document is valid for data-model version: 107" in register_details["IO_DATAMODEL_VERSION"]["text"],
            "Kipp & Zonen: data model version changed")
    check_scale_factor(register_details["IO_SCALE_FACTOR"])

    points = []
    for name, (point_id, kind, exponent, unit, text, description) in REGISTERS.items():
        row = registers.get(name)
        require(row is not None, f"Kipp & Zonen: overview row {name} missing")
        require(row["type"] == kind and row["access"] == "R" and text in row["description"],
                f"Kipp & Zonen {name}: unexpected type or description {row}")
        detail = register_details.get(name)
        if detail is not None:
            require(detail["address"] == row["address"], f"Kipp & Zonen {name}: overview and details disagree")
        if name in DETAIL_SCALES:
            require(DETAIL_SCALES[name] in detail["text"] and f"({name}) / 10" in detail["text"],
                    f"Kipp & Zonen {name}: scale not confirmed by the details")
        if kind == "S32":
            # The order of the two words is stated on the line below the row.
            low = row["address"] + 1
            require(re.match(rf"^[ \t]*{low}[ \t]+\(R{row['address']}=MSB, R{low}=LSB\)[ \t]*$", row["next"]),
                    f"Kipp & Zonen {name}: word order not stated")
        if point_id is None:
            continue
        point = {"id": point_id, "table": INPUT, "address": row["address"], "type": TYPES[kind], "aliases": [name]}
        if name == "IO_SENSOR_ON_TIMEH":
            low = registers["IO_SENSOR_ON_TIMEL"]
            require(low["address"] == row["address"] + 1, "Kipp & Zonen: on-time words are not adjacent")
            point["type"] = "u32"
            point["aliases"].append("IO_SENSOR_ON_TIMEL")
        if exponent is not None:
            point["conversion"] = {"exponent10": exponent}
        if unit is not None:
            point["unit"] = unit
        if name == "IO_DEVICE_TYPE":
            point["enum"] = {"values": types}
            point["stability"] = "constant"
        elif name == "IO_OPERATIONAL_MODE":
            point["enum"] = {"values": operational_modes(register_details[name])}
        elif name == "IO_STATUS_FLAGS":
            point["flags"] = {"flags": status_flags(register_details[name])}
        point["description"] = description
        point["source"] = {"address": str(row["address"]), "page": row["page"],
                           "reference": f"Input registers overview: {name}"}
        points.append(point)

    discrete = {}
    for page, line in sections["discrete"]:
        match = DISCRETE_ROW.match(line)
        if match:
            address, name, _, description = match.groups()
            name = DETAIL_NAMES.get(name, name)
            require(name not in discrete, f"Kipp & Zonen: duplicate discrete input {name}")
            discrete[name] = {"address": int(address), "description": description, "page": page}
    discrete_details = details(sections["discrete_details"])
    for name, row in discrete.items():
        require(discrete_details.get(name, {}).get("address") == row["address"],
                f"Kipp & Zonen discrete input {name}: overview and details disagree")
    for name, (point_id, text, description) in INPUTS.items():
        row = discrete.get(name)
        require(row is not None and text in row["description"], f"Kipp & Zonen: discrete input {name} missing")
        points.append({
            "id": point_id, "table": DISCRETE, "address": row["address"], "type": "bool", "aliases": [name],
            "description": description,
            "source": {"address": str(row["address"]), "page": row["page"],
                       "reference": f"Discrete inputs overview: {name}"},
        })

    ranges = []
    stdev = registers.get("IO_STDEV_SENSOR1")
    require(stdev is not None and "a new calculation is started" in register_details["IO_STDEV_SENSOR1"]["text"],
            "Kipp & Zonen: IO_STDEV_SENSOR1 read side effect not found")
    ranges.append({"table": INPUT, "start": stdev["address"], "count": 1, "policy": "side_effects",
                   "reason": "Reading IO_STDEV_SENSOR1 returns the standard deviation and starts a new period."})
    cleared = sorted(discrete[name]["address"] for name in CLEARED_ON_READ)
    for name in CLEARED_ON_READ:
        require(re.search(rf"{name} and bit \d of the IO_STATUS_FLAGS are cleared when the\s+{name} is read",
                          discrete_details[name]["text"]),
                f"Kipp & Zonen: clear-on-read statement for {name} missing")
    require(cleared == list(range(cleared[0], cleared[0] + len(cleared))), "Kipp & Zonen: clear-on-read inputs")
    ranges.append({"table": DISCRETE, "start": cleared[0], "count": len(cleared), "policy": "side_effects",
                   "reason": "Reading these discrete inputs clears them and the matching IO_STATUS_FLAGS bits."})
    return {"points": points, "constraints": {"ranges": ranges}}
