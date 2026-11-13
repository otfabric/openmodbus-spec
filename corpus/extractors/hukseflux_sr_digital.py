"""Hukseflux digital pyranometer user manual (PDF): Modbus register tables, SR20-D2 layout.

The selector is the model on the manual's cover, e.g. "SR20-D2". Each selected row must
appear once in the chapter 6 register tables and once in the appendix overview, with
the same address, access, format and description.
"""
from decimal import Decimal
import re
import struct

from sourcelib import pdf_page_count, pdf_pages, require

ROW = re.compile(r"^ ?(\d+(?: ?\+ ?\d+)?|\d+ to \d+|\d+ - \d+)(?= {2,}|$)")
FORMATS = {"U16": ("u16", 1), "S16": ("i16", 1), "U32": ("u32", 2), "S32": ("i32", 2), "Float": ("f32", 2),
           "String": ("string", None)}
SCALES = {"0.01": -2, "0.1": -1, "1": 0, "10-9": -9}
# The manual types the ohm as U+2126 OHM SIGN; accept the Greek capital omega as well.
UNITS = {"W/m²": "W/m2", "°C": "Cel", "\u2126": "Ohm", "\u03a9": "Ohm", "V": "V", "s": "s"}
SCALED = re.compile(r"^(?:Temperature compensated signal |Uncompensated signal )?[Ii]n x (0\.01|0\.1|1|10-9) "
                    r"(W/m²|°C|\u2126|\u03a9|V|s)$")
# The sensitivity unit is typeset with superscripts that pdftotext moves to a line of their own.
SENSITIVITY = {"In x 10 V/(W/m ) -6 2": "In x 10-6 V/(W/m2)", "In x 10-6 V/(W/m2)": "In x 10-6 V/(W/m2)"}
NUMBERS = {"four": 4, "five": 5, "six": 6, "eight": 8, "ten": 10}

# parameter: (point id, format, description)
SELECTED = {
    "Irradiance (temperature compensated signal)": (
        "irradiance", "S32", "Temperature-compensated irradiance."),
    "Irradiance (uncompensated signal)": (
        "irradiance_uncompensated", "S32", "Irradiance not compensated for temperature; for comparison only."),
    "Sensor body temperature": ("body_temperature", "S16", "Instrument body temperature."),
    "Sensor electrical resistance": (
        "sensor_resistance", "U16", "Thermopile electrical resistance; 0 until a measurement is triggered."),
    "Scaling factor irradiance": (
        "irradiance_scaling_factor", "U16",
        "Irradiance scaling factor, default 100. The manual does not state its relation to the irradiance "
        "registers, which it gives in 0.01 W/m2."),
    "Sensor voltage output": ("sensor_voltage", "S32", "Thermopile voltage output."),
    "Sensor serial number": ("serial_number", "U16", "Sensor serial number."),
    "Sensor sensitivity": ("sensitivity", "Float", "Sensitivity from the last calibration."),
    "Response time": ("response_time", "U16", "Response time measured during calibration."),
    "Sensor calibration date": (
        "calibration_date", "U32", "Last calibration date as the decimal number YYYYMMDD."),
    "Firmware version": ("firmware_version", "U16", "Firmware version."),
    "Hardware version": ("hardware_version", "U16", "Hardware version."),
}


def normal(text):
    return " ".join(text.split())


def cells(line):
    return [(match.start(), match.group()) for match in re.finditer(r"\S+(?: \S+)*", line)]


def table_rows(page_number, page):
    """Rows of every register table on a page, split into columns by the header positions."""
    rows = []
    columns = None
    current = None
    for line in page.split("\n"):
        if re.match(r"^ ?REGISTE", line) and "PARAMETER" in line and "FORMAT" in line:
            names = ("PARAMETER", "DESCRIPTION", "TYPE", "FORMAT")
            positions = [line.index(name) for name in names]
            columns = list(zip(positions, ("parameter", "description", "access", "format")))
            current = None
            continue
        if columns is None:
            continue
        match = ROW.match(line)
        if match:
            current = {"address": normal(match.group(1)), "page": page_number,
                       "parameter": [], "description": [], "access": [], "format": []}
            rows.append(current)
            rest = line[match.end():]
            offset = match.end()
        elif current is not None and line.strip() and line.startswith("     "):
            rest, offset = line, 0
        elif current is not None and not line.strip():
            continue
        else:
            if current is not None or not re.match(r"^ ?(R|NUMBER|ADDRESS)\b", line):
                columns = None if current is not None else columns
            current = None
            continue
        for start, text in cells(rest):
            column = [name for position, name in columns if position <= start + offset + 2]
            require(column, f"Hukseflux: cell left of the parameter column: {text!r}")
            current[column[-1]].append(text)
    for row in rows:
        for key in ("parameter", "description", "access", "format"):
            row[key] = normal(" ".join(row[key]))
    return rows


def register_span(address, width):
    match = re.fullmatch(r"(\d+)(?: ?\+ ?(\d+))?", address)
    require(match is not None, f"Hukseflux: unexpected register notation {address!r}")
    first = int(match.group(1))
    if width == 1:
        require(match.group(2) is None, f"Hukseflux: {address} is wider than one register")
    else:
        require(match.group(2) is not None and int(match.group(2)) == first + 1,
                f"Hukseflux: {address} is not two consecutive registers")
    return first


def check_protocol(text, selector):
    require(f"USER MANUAL {selector}" in text, f"Hukseflux: manual does not cover {selector}")
    require("If the format of data is a signed or an unsigned 32 bit integer, the first register received is the "
            "most significant word (MSW) and the second register is the least significant word (LSW)." in text,
            "Hukseflux: word order statement missing")
    require("The instrument does not distinguish between discrete input and coil; neither between input register "
            "and holding register." in text, "Hukseflux: register table statement missing")
    # Worked example: a read of 4 registers from address 0 returns register 2 as the MSW of the irradiance.
    require("[00][00] = Starting register, the master requests data starting from register 0." in text and
            "[03] = Modbus function; 03 Read holding registers" in text, "Hukseflux: request example missing")
    match = re.search(r"\[([0-9A-F]{2})\]\[([0-9A-F]{2})\] = Register 2; Temperature compensated signal, Most "
                      r"Significant Word \(MSW\)\. Decimal equivalent = \d+ \[([0-9A-F]{2})\]\[([0-9A-F]{2})\] = "
                      r"Register 3; Temperature compensated signal, Least Significant Word \(LSW\) = Decimal "
                      r"equivalent = \d+ .*? In this example the result is: .*? = (\d+\.\d+) W/m²", text)
    require(match is not None, "Hukseflux: irradiance example missing")
    raw = int("".join(match.group(1, 2, 3, 4)), 16)
    require(Decimal(raw) / 100 == Decimal(match.group(5)), "Hukseflux: irradiance example does not decode")
    # Appendix example: the sensitivity float, MSW in the first register.
    match = re.search(r"which is (\d+\.\d+): Data in register \d+, (\d+) \(MSW\) Data in register \d+, (\d+) \(LSW\)",
                      text)
    require(match is not None, "Hukseflux: float example missing")
    value = struct.unpack(">f", struct.pack(">HH", int(match.group(2)), int(match.group(3))))[0]
    require(abs(value - float(match.group(1))) < 0.005, "Hukseflux: float example is not MSW first")
    match = re.search(rf"Up to (\w+) 16 bit registers can be requested in one request\. In case six or more "
                      rf"registers are requested in just one request, {selector} will not respond\.", text)
    require(match is not None and match.group(1) in NUMBERS, "Hukseflux: request size limit missing")
    return NUMBERS[match.group(1)]


def extract(data, selector):
    pages = pdf_pages(data, 1, pdf_page_count(data))
    text = normal(" ".join(pages))
    max_read = check_protocol(text, selector)
    require("This register returns a 0 by default. To read the resistance, first a measurement has to be "
            "performed." in text, "Hukseflux: resistance default missing")
    require("the sensitivity of the sensor in x 10-6 V/(W/m²). Format of data is float." in text,
            "Hukseflux: sensitivity unit missing")
    appendix = [number for number, page in enumerate(pages, start=1) if re.search(r"^Table 9\.\d+\.2 Modbus registers",
                                                                                  page, re.MULTILINE)]
    require(len(appendix) == 1, "Hukseflux: appendix register overview not found")
    chapter, overview = {}, {}
    for number, page in enumerate(pages, start=1):
        for row in table_rows(number, page):
            if row["parameter"] not in SELECTED:
                continue
            target = overview if number >= appendix[0] else chapter
            require(row["parameter"] not in target, f"Hukseflux: duplicate row {row['parameter']}")
            target[row["parameter"]] = row
    require(chapter.keys() == overview.keys() == SELECTED.keys(),
            f"Hukseflux: rows missing: {sorted(SELECTED.keys() - (chapter.keys() & overview.keys()))}")

    points = []
    for parameter, (point_id, kind, description) in SELECTED.items():
        row, check = chapter[parameter], overview[parameter]
        require({key: row[key] for key in ("address", "description", "access", "format")} ==
                {key: check[key] for key in ("address", "description", "access", "format")},
                f"Hukseflux {parameter}: chapter table and appendix disagree")
        require(row["format"] == kind and row["access"] == "R", f"Hukseflux {parameter}: unexpected {row}")
        point_type, width = FORMATS[kind]
        address = register_span(row["address"], width)
        point = {"id": point_id, "address": address, "type": point_type, "aliases": [parameter]}
        vendor = row["description"]
        if parameter == "Sensor sensitivity":
            require(SENSITIVITY.get(vendor) == "In x 10-6 V/(W/m2)", f"Hukseflux: sensitivity unit {vendor!r}")
            point["unit"] = "uV.m2/W"
        elif parameter == "Scaling factor irradiance":
            require(vendor == "Default = 100", f"Hukseflux: scaling factor {vendor!r}")
        elif parameter == "Sensor calibration date":
            require(vendor == "Calibration date of the sensor in YYYYMMDD", f"Hukseflux: date {vendor!r}")
        elif kind != "U16" or vendor:
            match = SCALED.fullmatch(vendor)
            require(match is not None, f"Hukseflux {parameter}: no scale in {vendor!r}")
            if SCALES[match.group(1)]:
                point["conversion"] = {"exponent10": SCALES[match.group(1)]}
            point["unit"] = UNITS[match.group(2)]
        if point_id == "sensor_resistance":
            point["invalid"] = [0]
        if point_id == "serial_number":
            point["stability"] = "constant"
        point["description"] = description
        point["source"] = {"address": row["address"], "page": row["page"],
                           "reference": f"Modbus registers table: {parameter}"}
        points.append(point)
    return {"points": sorted(points, key=lambda point: point["address"]),
            "constraints": {"maxReadRegisters": max_read}}
