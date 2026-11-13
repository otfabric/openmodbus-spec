"""EKO Instruments MS-40S / MS-60S / MS-80S instruction manuals (PDF), appendix A4 Modbus RTU.

The selector is the model, e.g. "MS-80S". Registers 0-49 follow the S-series register
type (the default of register 103); registers 96-99 and 100-199 do not depend on it.
Rows are selected by label; addresses, types and units are parsed from the tables.
"""
import re
import struct

from sourcelib import pdf_page_count, pdf_pages, require

FOOTER = re.compile(r"^\s*EKO INSTRUMENTS CO\., LTD\. - Pyranometer .* Pg\. \d+\s*$")
ADDRESS = re.compile(r"^[ \t]*(\d+)(?=[ \t]|$)")
WIDE = re.compile(r"(?<!\S)(F32|U32|S32)(?!\S)")
SINGLE = re.compile(r"^[ \t]*(\d+)[ \t]+(\S.*?)[ \t]{2,}(U16)(?:[ \t]{2,}(\S.*?))?[ \t]*$")
TYPES = {"U16": "u16", "U32": "u32", "S32": "i32", "F32": "f32"}
UNITS = {"(W/m2)": "W/m2", "W/m2": "W/m2", "(°C)": "Cel", "(°)": "deg", "°": "deg", "(mV)": "mV", "mV": "mV",
         "(% RH)": "%", "RH %": "%", "(°C / °F / K)": None}

# S-series rows: label pattern -> (point id, type, allowed units, description)
S_SERIES = {
    r"Comp\.Irr": ("irradiance", "F32", {"W/m2"}, "Irradiance after temperature and linearity compensation."),
    r"Pt100": ("sensor_temperature", "F32", {"Cel"}, "Sensor temperature (Pt100)."),
    r"X-axis tilt angle(?: \(degree\))?": ("tilt_x", "F32", {"deg"}, "X-axis component of the tilt angle."),
    r"Y-axis tilt angle(?: \(degree\))?": ("tilt_y", "F32", {"deg"}, "Y-axis component of the tilt angle."),
    r"Raw\.Irr": ("irradiance_raw", "F32", {"W/m2"}, "Irradiance before correction."),
    r"ADmV": ("sensor_voltage", "F32", {"mV"}, "Sensor output voltage."),
    r"Internal temperature": ("internal_temperature", "F32", {"Cel", None},
                              "Temperature measured by the internal temperature sensor."),
    r"Internal humidity": ("internal_humidity", "F32", {"%"},
                           "Relative humidity measured by the internal humidity sensor."),
    r"(?:Alerts for abnormal )?internal humidity of(?: the pyranometer)?": (
        "humidity_alert", "U32", {"enum"}, "Alert for abnormal internal humidity of the pyranometer."),
}
# The alert label wraps around its two address lines differently in each manual.
ALERT = "Alerts for abnormal internal humidity of the pyranometer"
# Registers 100-199: label -> (point id, type, description)
SETTINGS = {
    "Serial number": ("serial_number", "U32", "Serial number as an integer, without the leading letter S."),
    "Cal.Date": ("calibration_date", "U32", "Calibration date as the decimal number YYYYMMDD."),
    "Cal.Value": ("sensitivity", "F32", "Calibration value (sensitivity) in µV per W/m2."),
}
VERSIONS = {"Firmware version": ("firmware_version", "Firmware version number."),
            "Hardware version": ("hardware_version", "Hardware version.")}


def normal(text):
    return " ".join(text.split())


def cells(line):
    return [(match.start(), match.group()) for match in re.finditer(r"\S+(?: \S+)*", line)]


def region(lines, start, stop):
    first = [index for index, (_, line) in enumerate(lines) if line.strip().startswith(start)]
    require(len(first) == 1, f"EKO: table {start!r} not found once")
    last = [index for index, (_, line) in enumerate(lines) if index > first[0] and line.strip().startswith(stop)]
    require(last, f"EKO: end of table {start!r} not found")
    return [(page, line) for page, line in lines[first[0] + 1:last[0]]
            if not FOOTER.match(line)]


def wide_rows(lines):
    """Two-register rows: the type sits on the first address line or on a line between two addresses.

    Text lines between two rows add to the description of the next row when they lead
    straight into its first address line, and to the previous row otherwise.
    """
    lines = [(page, line) for page, line in lines if line.strip()]
    frames = []
    for index, (_, line) in enumerate(lines):
        match = WIDE.search(line)
        if not match:
            continue
        own = ADDRESS.match(line)
        if own:
            first_index = index
        else:
            require(index > 0, f"EKO: {match.group()} row without an address: {line.strip()!r}")
            first_index = index - 1
        first = ADDRESS.match(lines[first_index][1])
        second = ADDRESS.match(lines[index + 1][1]) if index + 1 < len(lines) else None
        require(first and second and int(second.group(1)) == int(first.group(1)) + 1,
                f"EKO: {match.group()} row without consecutive addresses: {line.strip()!r}")
        frame_lines = [(lines[first_index][1], first.end(), True)]
        if not own:
            frame_lines.append((line, 0, True))
        frame_lines.append((lines[index + 1][1], second.end(), True))
        frames.append({"first": first_index, "last": index + 1, "match": match, "type_line": index,
                       "address": int(first.group(1)), "lines": frame_lines})
    starts = {frame["first"]: number for number, frame in enumerate(frames)}
    for number, frame in enumerate(frames):
        gap = []
        index = frame["last"] + 1
        while index < len(lines) and not ADDRESS.match(lines[index][1]):
            gap.append((lines[index][1], 0, False))
            index += 1
        if starts.get(index) == number + 1:
            frames[number + 1]["lines"][:0] = gap
        else:
            frame["lines"].extend(gap)
    rows = []
    for frame in frames:
        match = frame["match"]
        label, description = [], []
        for text_line, skip, in_frame in frame["lines"]:
            for start, text in cells(text_line):
                if start < skip or (text_line is lines[frame["type_line"]][1] and start == match.start()):
                    continue
                (label if in_frame and start < match.start() else description).append(text)
        rows.append({"address": frame["address"], "type": match.group(), "label": normal(" ".join(label)),
                     "description": normal(" ".join(description)), "page": lines[frame["type_line"]][0]})
    return rows


def single_rows(lines, labels):
    rows = {}
    for page, line in lines:
        match = SINGLE.match(line)
        if match and match.group(2) in labels:
            require(match.group(2) not in rows, f"EKO: duplicate row {match.group(2)}")
            rows[match.group(2)] = {"address": int(match.group(1)), "description": match.group(4) or "",
                                    "page": page}
    require(rows.keys() == set(labels), f"EKO: rows missing: {sorted(set(labels) - rows.keys())}")
    return rows


def check_data_format(text):
    require("Coil, Discrete Input, Holding Register, Input Register addresses start from “0”." in text,
            "EKO: address base statement missing")
    require("There is no distinction between Holding Register and Input Register addresses." in text,
            "EKO: register table statement missing")
    # Read-only rows are mapped as input registers and settings as holding registers: both read
    # functions must be supported, on one shared register map.
    require(re.search(r"Table A4-2\. Supported Function Codes Function code \(hexadecimal\) Function "
                      r"(?:0x0[12] Read [A-Za-z ]+? )*0x03 Read Holding Registers 0x04 Read Input Register ", text)
            and "Outline of 1 Holding/Input register map" in text, "EKO: read function codes missing")
    require("The register map starts from address 0." in text, "EKO: register map start missing")
    require("Registers No. 0 to 99 are read-only." in text, "EKO: read-only range missing")
    require("4byte values are sent in the order of H word → L word" in text, "EKO: word order missing")
    # The first character of a string is the first byte on the wire, i.e. the high byte of its register.
    require("2byte values are sent in the order of H byte → L byte" in text and
            "Character strings are sent in the order of 1 byte from the beginning." in text,
            "EKO: string byte order missing")
    require(re.search(r"(?:Unless otherwise stated, ?)?[Tt]he 32-bit register is in the order of high word \(MSW\) "
                      r"followed by low word \(LSW\)\.", text), "EKO: 32-bit register order missing")
    match = re.search(r"Table A4-6\. Assignment of 8/16 bits and F32 8bit 0x41 0x45 0x85 0x1E 16bit "
                      r"0x([0-9A-F]{4})\(MSW\) 0x([0-9A-F]{4})\(LSW\) F32 (\d+\.\d+)", text)
    require(match is not None, "EKO: F32 assignment example missing")
    value = struct.unpack(">f", bytes.fromhex(match.group(1) + match.group(2)))[0]
    require(abs(value - float(match.group(3))) < 1e-5, "EKO: F32 example does not decode high word first")


def extract(data, selector):
    pages = pdf_pages(data, 1, pdf_page_count(data))
    lines = [(number, line) for number, page in enumerate(pages, start=1) for line in page.split("\n")]
    text = normal(" ".join(pages))
    require(f"Sensor Name: Sensor name ({selector})" in text, f"EKO: manual does not cover {selector}")
    check_data_format(text)

    points = []
    table = region(lines, "Table A4-9. No. 0-49 Register S-series type (default)", "Table A4-10.")
    model = single_rows(table, ["Model"])["Model"]
    point = {"id": "model_code", "address": model["address"], "type": "u16", "aliases": ["Model"],
             "description": "Model number of the transmitter.", "stability": "constant"}
    code = re.search(r"\((MS-\d+S):0x([0-9A-F]{4})\)", model["description"])
    if code:
        require(code.group(1) == selector, f"EKO: model code is for {code.group(1)}")
        point["enum"] = {"values": [{"value": int(code.group(2), 16), "name": selector.lower().replace("-", "_"),
                                     "label": selector}]}
    point["source"] = {"address": str(model["address"]), "page": model["page"],
                       "reference": "Table A4-9 S-series type: Model"}
    points.append(point)

    seen = set()
    for row in wide_rows(table):
        matches = [key for key in S_SERIES if re.fullmatch(key, row["label"])]
        require(len(matches) == 1, f"EKO: unrecognised S-series row {row['label']!r}")
        point_id, kind, units, description = S_SERIES[matches[0]]
        require(point_id not in seen and row["type"] == kind, f"EKO: unexpected row {row}")
        seen.add(point_id)
        alias = ALERT if point_id == "humidity_alert" else row["label"]
        point = {"id": point_id, "address": row["address"], "type": TYPES[kind], "aliases": [alias]}
        if units == {"enum"}:
            match = re.search(r"Normal: (\d+), Abnormality occurs: (\d+)", row["description"])
            require(match is not None, "EKO: humidity alert values missing")
            point["enum"] = {"values": [{"value": int(match.group(1)), "name": "normal"},
                                        {"value": int(match.group(2)), "name": "abnormal"}]}
        else:
            match = re.search(r"Unit: (.+)$", row["description"])
            require(match is not None and match.group(1) in UNITS, f"EKO {point_id}: unit not recognised")
            unit = UNITS[match.group(1)]
            require(unit in units, f"EKO {point_id}: unexpected unit {match.group(1)}")
            if unit is None:
                description += f" Unit {match.group(1)} follows the temperature unit setting (°C by default)."
            else:
                point["unit"] = unit
        point["description"] = description
        point["source"] = {"address": str(row["address"]), "page": row["page"],
                           "reference": f"Table A4-9 S-series type: {alias}"}
        points.append(point)
    require({"irradiance", "irradiance_raw", "tilt_x", "tilt_y"} <= seen, "EKO: core S-series rows missing")

    info = region(lines, "Table A4-14.", "Table A4-17.")
    for label, row in single_rows(info, list(VERSIONS)).items():
        require(row["address"] <= 99, f"EKO {label}: outside the read-only range")
        points.append({"id": VERSIONS[label][0], "table": "input_register", "address": row["address"], "type": "u16",
                       "aliases": [label], "description": VERSIONS[label][1],
                       "source": {"address": str(row["address"]), "page": row["page"],
                                  "reference": f"Table A4-14: {label}"}})
    found = {}
    for row in wide_rows(info):
        if row["label"] in SETTINGS:
            require(row["label"] not in found, f"EKO: duplicate row {row['label']}")
            found[row["label"]] = row
    require(found.keys() == SETTINGS.keys(), f"EKO: rows missing from Table A4-15: {sorted(SETTINGS - found.keys())}")
    require("4294967295" in found["Serial number"]["description"], "EKO: serial number description changed")
    require("YYYYMMDD" in found["Cal.Date"]["description"], "EKO: calibration date format changed")
    require("μV/W・m-2" in found["Cal.Value"]["description"], "EKO: calibration value unit changed")
    for label, (point_id, kind, description) in SETTINGS.items():
        row = found[label]
        require(row["type"] == kind and row["address"] > 99, f"EKO {label}: unexpected type or address")
        point = {"id": point_id, "table": "holding_register", "address": row["address"], "type": TYPES[kind],
                 "aliases": [label], "description": description}
        if point_id == "serial_number":
            point["stability"] = "constant"
        if point_id == "sensitivity":
            point["unit"] = "uV.m2/W"
        point["source"] = {"address": str(row["address"]), "page": row["page"], "reference": f"Table A4-15: {label}"}
        points.append(point)

    names = []
    for page, line in info:
        match = re.match(r"^[ \t]*(\d+)[ \t]+Sensor name \((\d+),(\d+)\)", line)
        if match:
            names.append((int(match.group(1)), int(match.group(2)), int(match.group(3)), page))
    require(len(names) == 8, "EKO: sensor name rows missing")
    for index, (address, first, second, _) in enumerate(names):
        require(address == names[0][0] + index and (first, second) == (2 * index, 2 * index + 1),
                "EKO: sensor name rows are not consecutive character pairs")
    require("Sensor name according to ASCII format, up to 16 characters" in text and
            "Null-terminated unless all 16 characters are used" in text, "EKO: sensor name format changed")
    points.append({"id": "sensor_name", "table": "holding_register", "address": names[0][0], "type": "string",
                   "registers": len(names), "aliases": ["Sensor name"],
                   "description": "Sensor name, ASCII, up to 16 characters, NUL-terminated when shorter.",
                   "source": {"address": f"{names[0][0]}-{names[-1][0]}", "page": names[0][3],
                              "reference": "Table A4-15: Sensor name"}})
    return sorted(points, key=lambda point: point["address"])
