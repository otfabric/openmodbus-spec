"""Moxa ioLogik E1200 Series user's manual (PDF): Appendix A default Modbus/TCP maps.

The selector is the model, e.g. "E1210". Each table row gives the zero-based start
address and the 5- or 6-digit start register reference; both must agree. A row's
Length is the number of channels (bits or words), so rows become array points.
"""
import re

from sourcelib import modicon_reference, pdf_pages, require

MODEL_PAGE = 6
APPENDIX = (97, 114)
FUNCTIONS = {"01": ("COIL", "coil"), "02": ("INPUT", "discrete_input"),
             "03": ("HOLDI", "holding_register"), "04": ("INPUT", "input_register")}
ROW = re.compile(
    r"^(?P<indent>\s+)(?P<name>[A-Za-z][\w-]*)(?P<gap>\s+)(?P<desc>.*?)\s*(?P<address>\d{4})\s+"
    r"(?P<function>0[1-4]):(?P<fname>[A-Z]+)\s+(?P<reference>\d{5,6})\s+(?P<length>\d+)\s+"
    r"(?P<access>R/W|R)\s+(?P<kind>bit|word|2 words)\s*$")
SECTION = re.compile(r"^ioLogik (E12\d\d) Modbus Address and Register$")
ASCII = "Each byte represents ASCII code of each character"

# Parameter name -> (point ID, encoding, extra). Encodings: bool, u16, u32 (high/low
# word), string, bytes, enum (extra: label -> enum name), unit (extra: vendor unit).
DI = {
    "DI_status": ("di_status", "bool", None),
    "DI_counterValue": ("di_counter_value", "u32", None),
    "DI_counterOverflowFlag": ("di_counter_overflow_flag", "bool", None),
    "DI_counterStatus": ("di_counter_status", "bool", None),
}
DO = {
    "DO_status": ("do_status", "bool", None),
    "DO_pulseStatus": ("do_pulse_status", "bool", None),
    "DO_p2pStatus": ("do_p2p_status", "bool", None),
    "DO_pulseOnWidth": ("do_pulse_on_width", "unit", "1 ms"),
    "DO_pulseOffWidth": ("do_pulse_off_width", "unit", "1 ms"),
}
AI = {
    "AI_rawValue": ("ai_raw_value", "u16", None),
    "AI_rawValueMin": ("ai_raw_value_min", "u16", None),
    "AI_rawValueMax": ("ai_raw_value_max", "u16", None),
    "AI_status": ("ai_status", "enum", {"normal": "normal", "burnout": "burnout", "over range": "over_range",
                                        "under range": "under_range"}),
    "AI_mode": ("ai_mode", "enum", {"0-10 V": "voltage_0_10v", "4-20mA": "current_4_20ma",
                                    "0-20mA": "current_0_20ma", "4-20mA burnout": "current_4_20ma_burnout"}),
}
SYSTEM = {
    "modelName": ("model_name", "string", None),
    "deviceName": ("device_name", "string", None),
    "firmwareVersion": ("firmware_version", "bytes", None),
}
AI_IDS = [point_id for point_id, _, _ in AI.values()]
MODELS = {"E1210": {**DI, **SYSTEM}, "E1212": {**DI, **DO, **SYSTEM}, "E1240": {**AI, **SYSTEM}}
UNITS = {"1 ms": "ms"}


def channel_counts(page, model):
    match = re.search(rf"^\s+ioLogik {model}\s+Remote Ethernet I/O with 2-port Ethernet switch(?P<io>.*)$",
                      page, re.MULTILINE)
    require(match is not None, f"Moxa {model}: model description missing")
    counts = {kind: int(count) for count, kind in re.findall(r"(\d+) (DIs|DIOs|AIs)\b", match.group("io"))}
    require(counts, f"Moxa {model}: no channel counts in {match.group('io')!r}")
    return counts


def rows(pages, model):
    """Yield the parsed rows of one model's section, with continuation text joined."""
    lines = [(number, line) for number, page in enumerate(pages, APPENDIX[0]) for line in page.splitlines()]
    starts = [index for index, (_, line) in enumerate(lines) if SECTION.match(line)]
    begin = [index for index in starts if SECTION.match(lines[index][1]).group(1) == model]
    require(len(begin) == 1, f"Moxa {model}: {len(begin)} register map sections")
    end = min([index for index in starts if index > begin[0]], default=len(lines))
    require(lines[begin[0] + 1][1].strip() == "Map", f"Moxa {model}: unexpected section heading")
    section = lines[begin[0]:end]
    headers = [index for index, (_, line) in enumerate(section) if re.fullmatch(
        r"\s+Parameter Name\s+Description\s+Start\s+Function\s+Start\s+Length\s+Access\s+Type", line)]
    require(headers, f"Moxa {model}: table header missing")
    for index in headers:
        require(re.fullmatch(r"\s+Address\s+Code\s+Register", section[index + 1][1]) and
                re.fullmatch(r"\s+\(decimal\)\s+\(decimal\)", section[index + 2][1]),
                f"Moxa {model}: unexpected table header")
    current = None
    for page, line in section:
        match = ROW.match(line)
        if match:
            if current:
                yield current
            name_col = len(match.group("indent"))
            desc_col = match.start("desc") if match.group("desc") else None
            current = {**match.groupdict(), "page": page, "name_col": name_col, "desc_col": desc_col,
                       "address_col": match.start("address"), "descs": [match.group("desc")]}
            continue
        if current is None or not line.strip():
            continue
        if not re.match(r"\s", line) or re.match(r"\s+(I/O|System)$", line) or "Parameter Name" in line:
            yield current
            current = None
            continue
        text = line[:current["address_col"]]
        if len(text) > current["name_col"] and text[current["name_col"]] != " " and \
                text[current["name_col"] - 1] == " ":
            current["name"] += text[current["name_col"]:].split()[0]
        if current["desc_col"] is not None:
            current["descs"].append(text[current["desc_col"]:].strip())
    if current:
        yield current


def enum_values(description, labels, name):
    pairs = re.findall(r"(\d+):\s*(.+?)(?=,?\s+\d+:|$)", description)
    values = [{"value": int(value), "name": labels[label.strip(" ,")], "label": label.strip(" ,")}
              for value, label in pairs if label.strip(" ,") in labels]
    require(len(values) == len(pairs) == len(labels), f"Moxa {name}: unexpected enumeration {description!r}")
    return values


def extract(data, selector):
    require(selector in MODELS, f"Unknown Moxa model {selector!r}")
    counts = channel_counts(pdf_pages(data, MODEL_PAGE)[0], selector)
    pages = pdf_pages(data, *APPENDIX)
    for page in pages:
        require("Modbus/TCP Default Address Mappings" in page.splitlines()[0],
                "Moxa appendix page header missing")
    wanted = MODELS[selector]
    points = {}
    for row in rows(pages, selector):
        if row["name"] not in wanted:
            continue
        name = row["name"]
        point_id, encoding, extra = wanted[name]
        require(point_id not in points, f"Moxa {selector}: duplicate row {name}")
        fname, table = FUNCTIONS[row["function"]]
        require(row["fname"].startswith(fname), f"Moxa {name}: unexpected function code {row['fname']}")
        address = int(row["address"])
        require(modicon_reference(row["reference"], table) == address,
                f"Moxa {name}: start address and start register disagree")
        description = " ".join(" ".join(row["descs"]).split())
        length = int(row["length"])
        point = {"id": point_id, "aliases": [name], "table": table, "address": address}
        if encoding == "bool":
            require(row["kind"] == "bit", f"Moxa {name}: expected bits")
            point["type"] = "bool"
        elif encoding == "u32":
            require(row["kind"] == "2 words" and length % 2 == 0 and description.startswith("high/low word"),
                    f"Moxa {name}: expected high/low word pairs")
            point.update(type="u32", wordOrder="big")
            length //= 2
        elif encoding in ("string", "bytes"):
            require(row["kind"] == "word", f"Moxa {name}: expected words")
            expected = ASCII if encoding == "string" else "e.g. V1.2.3 -> 1st byte: 1, 2nd byte: 2, 3rd byte: 3"
            require(description == expected, f"Moxa {name}: unexpected description {description!r}")
            point.update(type=encoding, registers=length)
            if point_id != "device_name":  # the device name is user-configurable
                point["stability"] = "constant"
            length = 1
        else:
            require(row["kind"] == "word", f"Moxa {name}: expected words")
            point["type"] = "u16"
            if encoding == "enum":
                point["enum"] = {"values": enum_values(description, extra, name)}
            elif encoding == "unit":
                require(description == f"unit: {extra}", f"Moxa {name}: unexpected unit {description!r}")
                point["unit"] = UNITS[extra]
        if length > 1:
            point["count"] = length
        if row["access"] != "R":
            point["description"] = f"Vendor access {row['access']}; read-only in this contract."
        point["source"] = {"address": row["reference"], "page": row["page"],
                           "reference": f"Appendix A, ioLogik {selector} Modbus address and register map"}
        points[point_id] = point
    missing = sorted({point_id for point_id, _, _ in wanted.values()} - points.keys())
    require(not missing, f"Moxa {selector}: rows missing: {missing}")

    def size(point_id):
        return points[point_id].get("count", 1)
    if "di_status" in points:
        require(size("di_status") == counts.get("DIs", 0) + counts.get("DIOs", 0) and
                size("di_counter_value") == size("di_status") == size("di_counter_overflow_flag") ==
                size("di_counter_status"), f"Moxa {selector}: DI channel counts disagree")
    if "do_status" in points:
        require(all(size(point_id) == counts["DIOs"] for point_id in
                    ("do_status", "do_pulse_status", "do_p2p_status", "do_pulse_on_width", "do_pulse_off_width")),
                f"Moxa {selector}: DO channel counts disagree")
    if "ai_raw_value" in points:
        require(all(size(point_id) == counts["AIs"] for point_id in AI_IDS),
                f"Moxa {selector}: AI channel counts disagree")
    order = {point_id: index for index, (point_id, _, _) in enumerate(wanted.values())}
    return sorted(points.values(), key=lambda point: order[point["id"]])
