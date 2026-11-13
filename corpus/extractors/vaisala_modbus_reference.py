"""Vaisala user guides (PDF): Modbus reference appendices of the MMT162, MHT410 and OPT100.

The selector names the guide: "mmt162", "mht410" or "opt100". Each guide states
its own address notation (decimal register number plus a hexadecimal PDU
address) and the word order of 32-bit values (least significant word first).
"""
import re
import struct

from sourcelib import pdf_pages, require

UNITS = {"°C": "Cel", "%RS": "%", "hPa": "hPa", "ppm": "[ppm]", "ppmv": "[ppm]", "ppmw": "[ppm]",
         "ppmv (in oil)": "[ppm]"}
LSW_FIRST = re.compile(
    r"The least significant 16 bits of a floating point number are placed at the Modbus register listed\s+"
    r"in the table, while the most significant 16 bits are placed in the register with number/\s+"
    r"address \+ 1")


def text(pages):
    return "\n".join(pages)


def squash(value):
    return " ".join(value.split())


def cells(line):
    """Split a layout line into (start column, text) cells separated by two or more spaces."""
    return [(match.start(), match.group()) for match in re.finditer(r"\S+(?: \S+)*", line)]


def fragment_at(line, column, tolerance=2):
    for start, cell in cells(line):
        if abs(start - column) <= tolerance:
            return cell
    return None


def unit_of(raw, expected):
    raw = squash(raw)
    require(raw == expected, f"Vaisala: expected unit {expected!r}, found {raw!r}")
    scale = re.fullmatch(r"(.+?)\s*\*\s*(10|0\.1)", raw)
    base = scale.group(1) if scale else raw
    conversion = {"10": {"exponent10": -1}, "0.1": {"exponent10": 1}}[scale.group(2)] if scale else None
    return UNITS.get(base), conversion


def point(point_id, address, kind, label, source_address, page, reference, **extra):
    result = {"id": point_id, "address": address, "type": kind}
    if kind in ("u32", "i32", "f32"):
        result["wordOrder"] = "little"
    result.update({key: value for key, value in extra.items() if value is not None})
    result["aliases"] = [label]
    result["source"] = {"address": source_address, "page": page, "reference": reference}
    return result


# --- MMT162 -------------------------------------------------------------------------------------

MMT162_SELECTED = {
    # label: (point id, data format, notes column)
    "T (measured)": ("temperature", "f32", "°C"),
    "aw (measured)": ("water_activity", "f32", ""),
    "H2O (oil) (measured) *": ("moisture_in_oil", "f32", "ppm"),
    "Fault status": ("fault_status", "u16", "1 = no errors"),
    "Error Code": ("error_code", "u32", "0 = no errors"),
    "Oil factor A (set value) *": ("oil_factor_a", "f32", ""),
    "Oil factor B (set value) *": ("oil_factor_b", "f32", ""),
}
MMT162_ROW = re.compile(r"^(?P<logical>\d+)\s+(?P<hi>[0-9A-F]{2}) (?P<lo>[0-9A-F]{2})\s+(?P<rest>.*)$")
MMT162_FIRST = re.compile(r"^(?P<label>.*?)\s+(?:(?P<word>LSW)\s+)?(?P<width>16|32)-bit\s+"
                          r"(?P<access>read-only|read/write)\s*(?P<notes>.*)$")


def mmt162(data):
    operation, reference_pages = pdf_pages(data, 47), pdf_pages(data, 73, 74)
    functions, table = reference_pages
    require(re.search(r"3\s+03\s+Read Holding Registers", functions), "MMT162: FC 03 row missing")
    require("Table 19           Modbus Register Map" in table and
            re.search(r"Logical\s+PDU Address", table), "MMT162 page 74: register map header missing")
    require(re.search(r"LSW\s+Least significant word \(bits 15 … 0\)\.", table) and
            re.search(r"MSW\s+Most significant word \(bits 31 … 16\)\.", table),
            "MMT162: LSW/MSW definitions missing")
    lines = table.split("\n")
    rows = []
    for index, line in enumerate(lines):
        match = MMT162_ROW.match(line)
        if match:
            rows.append((index, match))
    points = {}
    for position, (index, match) in enumerate(rows):
        first = MMT162_FIRST.match(match["rest"])
        if not first or squash(first["label"]) not in MMT162_SELECTED:
            continue
        label = squash(first["label"])
        point_id, kind, notes = MMT162_SELECTED[label]
        require(point_id not in points, f"MMT162: duplicate row {label}")
        logical, address = int(match["logical"]), int(match["hi"] + match["lo"], 16)
        require(logical == address + 1, f"MMT162 {label}: logical and PDU address disagree")
        require(squash(first["notes"]) == notes, f"MMT162 {label}: unexpected notes {first['notes']!r}")
        if first["word"]:
            require(first["width"] == "32", f"MMT162 {label}: LSW on a 16-bit row")
            _, second = rows[position + 1]
            second_logical, second_address = int(second["logical"]), int(second["hi"] + second["lo"], 16)
            low_format = re.fullmatch(r"MSW\s+(float|bit field)", squash(second["rest"]))
            require(low_format and second_logical == logical + 1 and second_address == address + 1,
                    f"MMT162 {label}: MSW row missing")
            found = {"float": "f32", "bit field": "u32"}[low_format.group(1)]
        else:
            require(first["width"] == "16" and squash(lines[index + 1]) == "boolean",
                    f"MMT162 {label}: expected a 16-bit boolean")
            found = "u16"
        require(found == kind, f"MMT162 {label}: expected {kind}, found {found}")
        extra = {}
        if notes == "°C" or notes == "ppm":
            extra["unit"] = UNITS[notes]
            if notes == "ppm":
                extra["description"] = "Moisture in oil (ppm). Availability depends on the device model."
        elif kind == "u16":
            value, name = re.fullmatch(r"(\d+) = (no errors)", notes).groups()
            extra["enum"] = {"values": [{"value": int(value), "name": "no_errors", "label": "No errors"}]}
            extra["description"] = "16-bit boolean."
        elif kind == "u32":
            extra["description"] = "32-bit bit field; 0 = no errors. The guide does not name the bits."
        elif label.startswith("Oil factor"):
            extra["description"] = ("Oil-specific coefficient of the ppm conversion. Read/write in the device; "
                                    "availability depends on the device model.")
        points[point_id] = point(point_id, address, kind, label.removesuffix(" *"), str(logical), 74,
                                 "Table 19 Modbus Register Map", **extra)
    missing = {value[0] for value in MMT162_SELECTED.values()} - points.keys()
    require(not missing, f"MMT162: missing rows {sorted(missing)}")

    # Worked example (section "Modbus Communication"): read T and decode the response.
    page = operation[0]
    request = re.search(r"Request to read registers 3 and 4 \(currently measured value of T\):\s+"
                        r"F0h\s+03h\s+([0-9A-F]{2})h\s+([0-9A-F]{2})h\s+00h\s+02h", page)
    require(request and int(request.group(1) + request.group(2), 16) == points["temperature"]["address"],
            "MMT162 example: request address does not match the T row")
    response = re.search(r"\(([0-9A-F]{8})h = ([\d.]+) °C\):\s+F0h\s+03h\s+04h\s+([0-9A-F]{2})h ([0-9A-F]{2})h\s+"
                         r"([0-9A-F]{2})h ([0-9A-F]{2})h", page)
    require(response, "MMT162 example: response missing")
    value, decimal, first_hi, first_lo, second_hi, second_lo = response.groups()
    words = (int(first_hi + first_lo, 16), int(second_hi + second_lo, 16))
    require((words[1] << 16 | words[0]) == int(value, 16), "MMT162 example: response is not LSW first")
    decoded = struct.unpack(">f", int(value, 16).to_bytes(4, "big"))[0]
    require(abs(decoded - float(decimal)) < 1e-4, "MMT162 example: value does not decode")
    return sorted(points.values(), key=lambda item: item["address"])


# --- MHT410 -------------------------------------------------------------------------------------

MHT410_SELECTED = {
    # (first label line, data format): (point id, unit column)
    ("H2, 1 hour average", "32-bit float"): ("h2_1h_average", "ppmv (in oil)"),
    ("H2, 24 hour average", "32-bit float"): ("h2_24h_average", "ppmv (in oil)"),
    ("Oil moisture, relative", "32-bit float"): ("oil_relative_saturation", "%RS"),
    ("Oil moisture, current", "32-bit float"): ("oil_moisture", "ppmw"),
    ("Oil temperature", "32-bit float"): ("oil_temperature", "°C"),
    ("H2, 1 h average", "16-bit integer"): ("h2_1h_average_int", "ppmv (in oil)"),
    ("Oil moisture, relative", "16-bit integer"): ("oil_relative_saturation_int", "%RS*10"),
    ("Oil moisture, current", "16-bit integer"): ("oil_moisture_int", "ppmw*10"),
    ("Oil temperature", "16-bit integer"): ("oil_temperature_int", "°C *10"),
}
MHT410_STATUS_BITS = {
    "Critical Error active": "critical_error",
    "Error active": "error",
    "RH measurement error": "rh_measurement_error",
    "T measurement error": "t_measurement_error",
    "H2 measurement error": "h2_measurement_error",
    "Other error": "other_error",
    "H2 alarm level exceeded": "h2_alarm_level_exceeded",
}
MHT410_ROW = re.compile(r"^\s*(?P<number>\d+)\s+(?P<address>[0-9A-F]{4})hex\s+(?P<rest>.*)$")


def mht410_constraints(data):
    page = pdf_pages(data, 41)[0]
    match = re.search(r"The minimum time between requests from Modbus is (\d+) seconds?\.", page)
    require(match and "6.1 Overview of Modbus protocol support" in page, "MHT410: request interval missing")
    return {"minRequestIntervalMs": int(match.group(1)) * 1000}


def mht410(data):
    pages = pdf_pages(data, 110, 115)
    joined = text(pages)
    require(re.search(r"03\s+03hex\s+Read Holding", joined), "MHT410: FC 03 row missing")
    require(LSW_FIRST.search(joined), "MHT410: 32-bit word order statement missing")
    require(re.search(r"Some 16-bit integer values in the data registers are scaled to include the necessary "
                      r"decimals\.\s+The scaling factors for those values are shown in the register tables\.",
                      joined), "MHT410: 16-bit scaling statement missing")
    require(re.search(r"32768\s+8000hex\s+Value is not available", joined), "MHT410: 8000hex sentinel missing")
    require(re.search(r"32767\s+7FFFhex\s+Value is 32767 or larger", joined) and
            re.search(r"32769\s+8001hex\s+Value is −32767 or smaller", joined), "MHT410: saturation rows missing")
    require(re.search(r"Register\s+number 1 corresponds to address 0hex in the actual Modbus message\.", joined),
            "MHT410: register number base statement missing")
    require(re.search(r"Table 62\s+Modbus measurement data registers \(read-only\)", joined),
            "MHT410: Table 62 missing")
    points = {}
    for page_number, page in enumerate(pages[2:4], start=112):
        lines = page.split("\n")
        anchors = [(index, MHT410_ROW.match(line)) for index, line in enumerate(lines)]
        anchors = [(index, match) for index, match in anchors if match]
        for position, (index, match) in enumerate(anchors):
            rest = match["rest"]
            if squash(rest) == "MSW":
                continue
            row = (re.fullmatch(r"(?P<label>.+?)\s+LSW\s+(?P<format>32-bit float)\s+(?P<unit>.+)", rest) or
                   re.fullmatch(r"(?P<label>.+?)\s+(?P<format>16-bit integer)\s+(?P<unit>.+)", rest))
            require(row, f"MHT410 page {page_number}: unrecognized row {squash(lines[index])!r}")
            key = (squash(row["label"]), row["format"])
            if key not in MHT410_SELECTED:
                continue
            point_id, expected_unit = MHT410_SELECTED[key]
            require(point_id not in points, f"MHT410: duplicate row {key}")
            number, address = int(match["number"]), int(match["address"], 16)
            require(number == address + 1, f"MHT410 {key}: register number and address disagree")
            label_column = match.start("rest") + rest.index(row["label"])
            following = anchors[position + 1][0] if position + 1 < len(anchors) else len(lines)
            label = [squash(row["label"])]
            for extra_line in lines[index + 1:following]:
                fragment = fragment_at(extra_line, label_column)
                if fragment:
                    label.append(fragment)
            unit, conversion = unit_of(row["unit"], expected_unit)
            extra = {"unit": unit, "conversion": conversion}
            if row["format"] == "32-bit float":
                _, second = anchors[position + 1]
                require(squash(second["rest"]) == "MSW" and int(second["address"], 16) == address + 1,
                        f"MHT410 {key}: MSW row missing")
                kind = "f32"
            else:
                kind = "i16"
                extra["invalid"] = [-32768]
            notes = []
            if unit == "[ppm]":
                notes.append(f"Unit in the guide: {squash(row['unit'])}.")
            if kind == "i16":
                notes.append("Raw 7FFFhex means 32767 or larger and 8001hex means -32767 or smaller (Table 60).")
            extra["description"] = " ".join(notes) or None
            points[point_id] = point(point_id, address, kind, " ".join(label), str(number), page_number,
                                     "Table 62 Modbus measurement data registers", **extra)
    missing = {value[0] for value in MHT410_SELECTED.values()} - points.keys()
    require(not missing, f"MHT410: missing rows {sorted(missing)}")

    status_page = pages[4]
    status = re.search(r"^\s*(\d+)\s+([0-9A-F]{2}) ([0-9A-F]{2})hex\s+Device status bits\s+16-bit integer\s*$",
                       status_page, re.MULTILINE)
    require(status and "Table 64   Modbus device status bits" in status_page, "MHT410: status register missing")
    number, address = int(status.group(1)), int(status.group(2) + status.group(3), 16)
    require(number == address + 1, "MHT410 status: register number and address disagree")
    table = status_page.split("Table 64   Modbus device status bits", 1)[1].split("Multiple device statuses", 1)[0]
    bits = []
    for line in table.split("\n"):
        row = re.match(r"^(\d+)(\s+)(\S+(?: \S+)*)", line)
        if row:
            bits.append([int(row.group(1)), [row.group(3)], len(row.group(1)) + len(row.group(2))])
        elif bits:
            fragment = fragment_at(line, bits[-1][2])
            if fragment:
                bits[-1][1].append(fragment)
    require(bits and bits[0][:2] == [0, ["Status OK"]], "MHT410: status bit table does not start with Status OK")
    flags = []
    for mask, words, _ in bits[1:]:
        name = " ".join(words)
        require(mask & (mask - 1) == 0 and name in MHT410_STATUS_BITS, f"MHT410: unexpected status bit {mask} {name}")
        flags.append({"bit": mask.bit_length() - 1, "name": MHT410_STATUS_BITS[name], "label": name})
    require(len(flags) == len(MHT410_STATUS_BITS), "MHT410: status bits missing")
    points["device_status"] = point(
        "device_status", address, "u16", "Device status bits", str(number), 114, "Table 63 Modbus status registers",
        flags={"flags": flags}, description="0 = status OK. Several bits can be set at once.")
    return {"points": sorted(points.values(), key=lambda item: item["address"]),
            "constraints": mht410_constraints(data)}


# --- OPT100 -------------------------------------------------------------------------------------

OPT100_MEASUREMENTS = {
    # (section, first label line, data format): (point id, unit column)
    ("Present values", "Methane", "32-bit float"): ("methane", "ppmv"),
    ("Present values", "Acetylene", "32-bit float"): ("acetylene", "ppmv"),
    ("Present values", "Ethylene", "32-bit float"): ("ethylene", "ppmv"),
    ("Present values", "Ethane", "32-bit float"): ("ethane", "ppmv"),
    ("Present values", "Carbon monoxide", "32-bit float"): ("carbon_monoxide", "ppmv"),
    ("Present values", "Carbon dioxide", "32-bit float"): ("carbon_dioxide", "ppmv"),
    ("Present values", "Total dissolved", "32-bit float"): ("tdcg", "ppmv"),
    ("Present values", "Hydrogen", "32-bit float"): ("hydrogen", "ppmv"),
    ("Present values", "Moisture in oil", "32-bit float"): ("moisture_in_oil", "ppmw"),
    ("Present values", "Temperature of", "32-bit float"): ("chamber_temperature", "°C"),
    ("Present values", "Relative moisture", "32-bit float"): ("relative_moisture_in_oil", "%RS"),
    ("Present values", "Total gas pressure", "32-bit float"): ("total_gas_pressure", "hPa"),
    ("Present values as 16-bit signed integer", "Methane", "16-bit signed"): ("methane_int", "ppmv"),
}
OPT100_SECTIONS = ("Present values", "24 hour average values", "Rate of change (ROC), 24 hour",
                   "Rate of change (ROC), 7 days", "Rate of change (ROC), 30 days",
                   "Gas ratios (24 hour average values)", "Other", "Custom averages",
                   "Present values as 16-bit signed integer")
OPT100_STATUS = {
    "Device stopped": ("device_stopped", {0: ("measuring_normally", "Device measuring normally"),
                                          1: ("stopped", "Device stopped")}),
    "Measurement reliability": ("measurement_reliable", {0: ("unreliable", "Measurement is unreliable"),
                                                         1: ("reliable", "Measurement is reliable")}),
    "Combined cautions": ("combined_cautions", {0: ("none", "No cautions are active"),
                                                1: ("active", "At least one caution is active")}),
    "Combined alarms": ("combined_alarms", {0: ("none", "No alarms are active"),
                                            1: ("active", "At least one alarm is active")}),
}
OPT100_ALERTS = {
    # (register description, name of bit 0): point id. The oxygen/nitrogen registers share the descriptions.
    ("Gas level caution alerts for present values", "Methane"): "gas_caution_alerts_present",
    ("Gas level alarms for present values", "Methane"): "gas_alarms_present",
}
OPT100_ALERT_BITS = {
    "Methane": "methane", "Acetylene": "acetylene", "Ethylene": "ethylene", "Ethane": "ethane",
    "Carbon monoxide": "carbon_monoxide", "Carbon dioxide": "carbon_dioxide", "TDCG": "tdcg",
    "Hydrogen": "hydrogen", "Moisture in oil": "moisture_in_oil",
    "Relative moisture in oil": "relative_moisture_in_oil",
    "TGP above maximum limit": "tgp_above_maximum", "TGP below minimum limit": "tgp_below_minimum",
    "Any caution alert active in this register": "any_active", "Any alarm active in this register": "any_active",
}
OPT100_ROW = re.compile(r"^\s*(?P<number>\d+)\s+0x(?P<address>[0-9A-F]{4})\s+(?P<rest>.*)$")
OPT100_FORMAT = re.compile(r"^(?P<label>.*?)\s*(?P<format>32-bit float|64-bit float|32-bit integer|16-bit signed|"
                           r"16-bit field|16-bit unsigned integer|32-bit unsigned integer|64-bit unsigned integer|"
                           r"16-bit integer|64-bit integer)\s*(?P<unit>.*)$")


def opt100_rows(pages, first_page):
    """Yield (page, section, row match, continuation lines) for every table row.

    The section is the latest table caption or Table 33 subheading above the row.
    """
    section = ""
    for page_number, page in enumerate(pages, start=first_page):
        lines = page.split("\n")
        anchors = []
        for index, line in enumerate(lines):
            if squash(line) in OPT100_SECTIONS or re.match(r"^\s*Table \d+\s", line):
                anchors.append((index, None))
                continue
            match = OPT100_ROW.match(line)
            if match:
                anchors.append((index, match))
        for position, (index, match) in enumerate(anchors):
            following = anchors[position + 1][0] if position + 1 < len(anchors) else len(lines)
            if match is None:
                section = squash(lines[index])
                continue
            yield page_number, section, match, lines[index + 1:following]


def opt100_enum(notes, expected, point_id):
    values = []
    for value, (name, prefix) in expected.items():
        found = [entry for entry in notes if entry[0] == value]
        require(len(found) == 1 and found[0][1].startswith(prefix), f"OPT100 {point_id}: value {value} not found")
        values.append({"value": value, "name": name, "label": found[0][1]})
    require(len(notes) == len(expected), f"OPT100 {point_id}: unexpected status values")
    return {"values": values}


def numbered_entries(match, continuation, column):
    """Collect "<n> = text" entries that start at `column` on the row and its continuation lines."""
    entries = []
    for line in [" " * match.start("rest") + match["rest"], *continuation]:
        fragment = None
        for start, cell in cells(line):
            if start >= column - 2:
                fragment = (start, " ".join(cell for _, cell in cells(line[start:])))
                break
        if fragment is None:
            continue
        item = re.match(r"^(\d+) = (.*)$", fragment[1])
        if item:
            entries.append([int(item.group(1)), item.group(2)])
        elif entries:
            entries[-1][1] += " " + fragment[1]
    return [(value, squash(label)) for value, label in entries]


def opt100(data):
    pages = pdf_pages(data, 124, 142)
    joined = text(pages)
    require(re.search(r"03\s+0x03\s+Read Holding Registers", joined), "OPT100: FC 03 row missing")
    require(LSW_FIRST.search(joined), "OPT100: 32-bit word order statement missing")
    require(re.search(r"Register\s+number 1 corresponds to address 0x0 in the actual Modbus message\.", joined),
            "OPT100: register number base statement missing")
    require(re.search(r"“Unavailable” value \(a quiet NaN for floating point data or 0x8000 for integer data\)",
                      joined), "OPT100: unavailable value statement missing")
    require("Only the first bit of each status bit field is used." in joined, "OPT100: status bit statement missing")
    points = {}
    for page_number, section, match, continuation in opt100_rows(pages, 124):
        number, address = int(match["number"]), int(match["address"], 16)
        require(number == address + 1, f"OPT100 page {page_number}: register {number} and 0x{address:04X} disagree")
        row = OPT100_FORMAT.match(match["rest"])
        if not row:
            continue
        label = squash(row["label"])
        key = (section, label, row["format"])
        label_column = match.start("rest") + match["rest"].index(row["label"]) if label else None
        fragments = [fragment_at(line, label_column) for line in continuation] if label else []
        full_label = squash(" ".join([label] + [fragment for fragment in fragments if fragment]))
        full_label = re.sub(r" See .*$", "", full_label)
        if key in OPT100_MEASUREMENTS:
            point_id, expected_unit = OPT100_MEASUREMENTS[key]
            require(point_id not in points, f"OPT100: duplicate row {key}")
            unit, conversion = unit_of(row["unit"], expected_unit)
            require(conversion is None, f"OPT100 {key}: scaled rows are not selected")
            extra = {"unit": unit}
            if row["format"] == "32-bit float":
                require(any(squash(line).startswith(f"0x{address + 1:04X}") for line in continuation),
                        f"OPT100 {key}: second register missing")
                kind = "f32"
            else:
                require([squash(line) for line in continuation][:1] == ["integer"],
                        f"OPT100 {key}: expected a 16-bit signed integer")
                kind = "i16"
                extra["invalid"] = [-32768]
            if unit == "[ppm]":
                extra["description"] = f"Unit in the guide: {expected_unit}."
            points[point_id] = point(point_id, address, kind, full_label, str(number), page_number,
                                     f"Table 33 Measurement data registers, {section}", **extra)
        elif section.startswith("Table 35") and label in OPT100_STATUS and row["format"] == "16-bit field":
            point_id, expected = OPT100_STATUS[label]
            require(point_id not in points, f"OPT100: duplicate status row {label}")
            notes = numbered_entries(match, continuation, match.start("rest") + row.start("unit"))
            points[point_id] = point(point_id, address, "u16", label, str(number), page_number,
                                     "Table 35 Status registers", mask=1,
                                     enum=opt100_enum(notes, expected, point_id),
                                     description="Only the first bit of the register is used.")
        elif section.startswith("Table 34") and row["format"] == "16-bit field":
            description = full_label
            entries = numbered_entries(match, continuation, match.start("rest") + row.start("unit"))
            require(entries and entries[0][0] == 0, f"OPT100: alert register {number} has no bit 0")
            if (description, entries[0][1]) not in OPT100_ALERTS:
                continue
            point_id = OPT100_ALERTS[(description, entries[0][1])]
            require(point_id not in points, f"OPT100: duplicate alert row {description}")
            flags = []
            for bit, name in entries:
                require(name in OPT100_ALERT_BITS, f"OPT100 {point_id}: unexpected bit {bit} {name!r}")
                flags.append({"bit": bit, "name": OPT100_ALERT_BITS[name], "label": name})
            require([flag["bit"] for flag in flags] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15],
                    f"OPT100 {point_id}: unexpected bit list")
            points[point_id] = point(point_id, address, "u16", description, str(number), page_number,
                                     "Table 34 Alert registers", flags={"flags": flags},
                                     description="A bit is 0 when the alert is inactive, turned off or muted.")
        elif (section.startswith("Table 36") and label == "" and row["format"] == "32-bit unsigned integer"
              and squash(row["unit"]) == "1234567890"):
            require("test_value_u32" not in points, "OPT100: duplicate test register")
            points["test_value_u32"] = point(
                "test_value_u32", address, "u32", "Test value register (32-bit unsigned integer)", str(number),
                page_number, "Table 36 Test value registers",
                description="Constant test value 1234567890; use it to confirm the word order on a device.")
    expected = ({value[0] for value in OPT100_MEASUREMENTS.values()} | {value[0] for value in OPT100_STATUS.values()}
                | set(OPT100_ALERTS.values()) | {"test_value_u32"})
    require(points.keys() == expected, f"OPT100: missing rows {sorted(expected - points.keys())}")

    # Worked example A.6. Its byte listing contradicts the stated word order (vendor erratum, see
    # the corpus report): the extractor pins the published text so that any revision is reviewed.
    example = text(pages[-2:])
    request = re.search(r"0x03\s+Function \(Read Holding Registers\)\s+0x([0-9A-F]{2})\s+Register address "
                        r"\(Acetylene\)\s+0x([0-9A-F]{2})", example)
    require(request and int(request.group(1) + request.group(2), 16) == points["acetylene"]["address"],
            "OPT100 example: request address does not match the Acetylene row")
    response = re.search(r"0x([0-9A-F]{2})\s+Value of first register \(least significant word\)\s+0x([0-9A-F]{2})\s+"
                         r"0x([0-9A-F]{2})\s+Value of second register \(most significant word\)\s+0x([0-9A-F]{2})",
                         example)
    stated = re.search(r"least\s+significant word first\.\s+Returned value\s+0x([0-9A-F]{8}), which is binary32 "
                       r"representation\s+of 3 \(ppm\)", example)
    require(response and stated, "OPT100 example: response description missing")
    first, second = int(response.group(1) + response.group(2), 16), int(response.group(3) + response.group(4), 16)
    require((first, second, stated.group(1)) == (0x4040, 0x0000, "40400000"),
            "OPT100 example changed: review the word-order erratum")
    return sorted(points.values(), key=lambda item: item["address"])


EXTRACTORS = {"mmt162": mmt162, "mht410": mht410, "opt100": opt100}


def extract(data, selector):
    require(selector in EXTRACTORS, f"Unknown Vaisala selector {selector!r}")
    return EXTRACTORS[selector](data)
