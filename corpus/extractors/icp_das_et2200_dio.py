"""ICP DAS ET-2200 Series user manual (PDF): section 6.3 DIO Modbus register tables.

The selector is a model from the section 6.3.2 channel table, e.g. "ET-2251". The
tables state zero-based addresses ("Base 0") in decimal with the hexadecimal value
below; both must agree. Rows whose Points column reads "1 to nDI" or "1 to nDO"
become array points sized by the model's channel counts.
"""
import re

from sourcelib import pdf_pages, require

PAGES = (176, 181)
SECTION = re.compile(r"^\s*(?:[^\w\s]\s*)?([0134])xxxx: (DO|DI|AI|AO) Address \(Base 0\)\s*$")
TABLES = {"0": "coil", "1": "discrete_input", "3": "input_register", "4": "holding_register"}
DECIMAL = re.compile(r"^\s{0,8}(\d+)(?:\s*~\s*(\d+))?(?=\s{2,}|$)")
HEX = re.compile(r"^\s{0,8}\(?0x([0-9A-F]+)\)?(\s*~)?(?=\s{2,}|$)")
HEADER_WORDS = {"Starting", "Address", "Points", "Description", "Bits", "per", "Point", "Range", "Access",
                "Type", "Value"}
POINTS = re.compile(r"1 to (nDI|nDO|UDIO)|1")
ACCESS = re.compile(r"R|W|R/W|R/W/F|R/W/E|W \(Pulse\)")
ORDER = "Data from 32-bit registers is transmitted as two 16-bit registers and is in low-word first order."

# (table, description) -> (point ID, I/O group, encoding, extra)
COMMON = {
    ("input_register", "Firmware Version"): ("firmware_version", None, "u16", "“123” denotes that the version is 1.2.3"),
    ("input_register", "Modbus Communication Status"):
        ("modbus_communication_status", None, "enum", {"No Error": "no_error", "Timeout": "timeout"}),
    ("input_register", "Pair-Connection Status"):
        ("pair_connection_status", None, "enum", {"Normal": "normal", "Timeout": "timeout",
                                                  "Disconnected": "disconnected"}),
    ("holding_register", "CPU Reset Status"):
        ("cpu_reset_status", None, "enum", {"Reset at Power-on": "power_on", "Reset by the WDT": "watchdog",
                                            "Reset using the reset command": "reset_command"}),
    ("holding_register", "Host WDT Events"): ("host_wdt_events", None, "u16", None),
    ("holding_register", "Module Name"): ("module_name", None, "u16", "Module Name"),
}
DI = {
    ("discrete_input", "The status of all Digital Input Channels"): ("di_status", "nDI", "bool", None),
    ("discrete_input", "The status of all high-latched DI Channels"): ("di_high_latch", "nDI", "bool", None),
    ("discrete_input", "The status of all low-latched DI Channels"): ("di_low_latch", "nDI", "bool", None),
    ("coil", "Enables the high and low latches for all DI Channels"): ("di_latch_enable", "nDI", "bool", None),
    ("coil", "Enables the high-speed digital counter for all DI Channels"):
        ("di_counter_enable", "nDI", "bool", None),
    ("coil", "Enables frequency measurement for all DI Channels"): ("di_frequency_enable", "nDI", "bool", None),
    ("input_register", "The Digital Counter Value"): ("di_counter", "nDI", "u32", None),
    ("input_register", "The frequency Value is * 1,000. (Note: The Client must first divide the value by 1,000.)"):
        ("di_frequency", "nDI", "u32", "1,000"),
    ("input_register", "Number of DI Channels"): ("di_channel_count", "nDI", "u16", "nDI"),
    ("input_register", "Number of high-speed counters"): ("counter_channel_count", "nDI", "u16", "nDI"),
}
DO = {
    ("coil", "Digital Output Channels"): ("do_status", "nDO", "bool", None),
    ("coil", "Enables the PWM for all DO Channels"): ("do_pwm_enable", "nDO", "bool", None),
    ("coil", "Sets the Power-on value for all DO Channels"): ("do_power_on_value", "nDO", "bool", None),
    ("coil", "Sets the Safe value for all DO Channels"): ("do_safe_value", "nDO", "bool", None),
    ("input_register", "Number of DO Channels"): ("do_channel_count", "nDO", "u16", "nDO"),
    ("holding_register", "The Min-Switching Time for all DO Channels"):
        ("do_min_switching_time", "nDO", "u16", "1 to 65535 second"),
    ("holding_register", "The Auto-off Time for all DO Channels"):
        ("do_auto_off_time", "nDO", "u16", "1 to 65535 second"),
}
SINGLE = {"di_latch_enable", "di_channel_count", "counter_channel_count", "do_channel_count"}
BITS = {"bool": "1", "u16": "16", "u32": "32"}


def channel_counts(text, model):
    """Return {nDI, nDO} for a model from the section 6.3.2 channel table."""
    head = re.search(r"Model\s+Universal DIO \(UDIO\)\s+DI channels \(nDI\)\s+DO channels \(nDO\)", text)
    require(head is not None, "ICP DAS channel table header missing")
    rows = []
    for line in text[head.end():].splitlines()[1:]:
        if not line.strip():
            break
        rows.append(line)
    names = [re.match(r"\s*(?:\(P\))?(\S+)", line).group(1) for line in rows]
    matches = [line for name, line in zip(names, rows) if name == model]
    require(len(matches) == 1, f"ICP DAS {model}: not in the channel table")
    values = matches[0].split()[1:]
    require(len(values) == 3 and all(re.fullmatch(r"-|\d+", value) for value in values),
            f"ICP DAS {model}: channel counts not stated per model ({matches[0].strip()!r})")
    _, inputs, outputs = (0 if value == "-" else int(value) for value in values)
    return {"nDI": inputs, "nDO": outputs}


def fragments(line):
    return [(match.start(), match.group()) for match in re.finditer(r"\S+(?: \S+)*", line)]


def header_columns(lines):
    columns = {}
    for line in lines:
        for start, text in fragments(line):
            for word, key in (("Points", "points"), ("Description", "description"), ("Bits per", "bits"),
                              ("Range", "range"), ("Value", "range"), ("Access", "access")):
                if text.startswith(word):
                    columns[key] = start
    require(columns.keys() == {"points", "description", "bits", "range", "access"},
            f"ICP DAS: unexpected table header {lines!r}")
    return columns


def table_rows(pages):
    """Yield every row of the section 6.3 tables, tagged with its section."""
    lines = []
    for number, page in enumerate(pages, PAGES[0]):
        for line in page.splitlines():
            if "Copyright ©" in line or line.strip() == "ET-2200 Series Ethernet I/O Modules":
                continue
            lines.append((number, line))
    index = 0
    while index < len(lines):
        match = SECTION.match(lines[index][1])
        index += 1
        if not match:
            continue
        table = TABLES[match.group(1)]
        section = f"{match.group(1)}xxxx {match.group(2)} address table"
        body, headers, skipping = [], [], False
        while index < len(lines) and not SECTION.match(lines[index][1]):
            page, line = lines[index]
            index += 1
            words = set(line.split())
            if re.match(r"\s*(Notes\b|“[A-Z]”:)", line):
                break
            if words and words <= HEADER_WORDS:
                headers.append(line)
                continue
            if re.fullmatch(r"\s*Note:\s*", line):
                skipping = True
                continue
            if skipping and not DECIMAL.match(line):
                continue
            skipping = False
            body.append((page, line))
        for row in parse_rows(table, body, header_columns(headers)):
            yield {**row, "section": section}


def parse_rows(table, body, columns):
    anchors = []
    position = 0
    while position < len(body):
        decimal = DECIMAL.match(body[position][1])
        if not decimal:
            position += 1
            continue
        hexes = [offset for offset in range(position + 1, min(position + 4, len(body)))
                 if HEX.match(body[offset][1])]
        require(hexes, f"ICP DAS {table}: address {decimal.group(1)} without hexadecimal value")
        hex_line = hexes[0]
        hex_match = HEX.match(body[hex_line][1])
        lines = {position, hex_line}
        if decimal.group(2):
            ends = [offset for offset in range(hex_line + 1, min(hex_line + 4, len(body)))
                    if HEX.match(body[offset][1])]
            require(hex_match.group(2) and ends, f"ICP DAS {table}: unexpected address range {decimal.group()!r}")
            lines.add(ends[0])
        anchors.append({"table": table, "decimal": decimal.group(1), "hex": hex_match.group(1),
                        "page": body[position][0], "span": bool(decimal.group(2)),
                        "anchor_lines": lines, "center": (position + hex_line) / 2, "lines": []})
        position = max(lines) + 1
    require(anchors, f"ICP DAS {table}: no rows")
    assign_lines(anchors, body)
    for row in anchors:
        fields = {"points": [], "description": [], "bits": [], "range": [], "access": []}
        for number, line in row["lines"]:
            for start, text in fragments(line):
                if number in row["anchor_lines"] and start <= 8 and (DECIMAL.match(text) or HEX.match(text)):
                    continue
                for field, part in classify(start, text, columns):
                    fields[field].append(part)
        row.update({key: join_text(value) for key, value in fields.items()})
        row["range_items"] = fields["range"]
        yield row


def assign_lines(anchors, body):
    """Give each text line to the row whose vertical centre is nearest.

    Cell text is centred vertically on its row, so a line equidistant from two
    rows goes to the row that has a line mirrored on the far side of its centre.
    """
    owner, ties = {}, []
    for row in anchors:
        for number in row["anchor_lines"]:
            owner[number] = row
    for number, (_, line) in enumerate(body):
        if not line.strip() or number in owner:
            continue
        distances = sorted(anchors, key=lambda row: abs(row["center"] - number))
        if len(distances) > 1 and abs(distances[0]["center"] - number) == abs(distances[1]["center"] - number):
            ties.append((number, sorted(distances[:2], key=lambda row: row["center"])))
        else:
            owner[number] = distances[0]
    for number, (upper, lower) in ties:
        mirror_upper = owner.get(int(2 * upper["center"] - number))
        mirror_lower = owner.get(int(2 * lower["center"] - number))
        if mirror_upper is upper and mirror_lower is not lower:
            owner[number] = upper
        else:
            owner[number] = lower
    for number, row in sorted(owner.items()):
        row["lines"].append((number, body[number][1]))


def join_text(parts):
    text = ""
    for part in parts:
        text = text + part if text.endswith("-") and part[:1].islower() else f"{text} {part}".strip()
    return text


def classify(start, text, columns):
    """Assign one text fragment of a row to its column: [(field, text), ...]."""
    if ACCESS.fullmatch(text) and start >= columns["access"] - 8:
        return [("access", text)]
    if re.fullmatch(r"\d+", text) and columns["bits"] - 3 <= start <= columns["bits"] + 9:
        return [("bits", text)]
    if start >= columns["bits"] + 4:
        return [("range", text)]
    if POINTS.fullmatch(text) and start < columns["description"]:
        return [("points", text)]
    split = re.fullmatch(r"(1 to (?:nDI|nDO|UDIO)) (.+)", text)
    if split and start <= columns["points"] + 3:
        return [("points", split.group(1)), ("description", split.group(2))]
    return [("description", text)]


def enum_values(items, labels, name):
    joined = []
    for item in items:
        if joined and not re.match(r"[\d<(]", item):
            joined[-1] += " " + item
        else:
            joined.append(item)
    values = []
    for item in joined:
        match = re.fullmatch(r"(\d+) = (.+)", item)
        if match and match.group(2) in labels:
            values.append({"value": int(match.group(1)), "name": labels[match.group(2)],
                           "label": match.group(2)})
    require(sorted(value["label"] for value in values) == sorted(labels),
            f"ICP DAS {name}: unexpected values {joined!r}")
    return sorted(values, key=lambda value: value["value"])


def extract(data, selector):
    pages = pdf_pages(data, *PAGES)
    require(ORDER in " ".join(pages[0].split()), "ICP DAS: 32-bit word order statement missing")
    counts = channel_counts("\n".join(pages), selector)
    wanted = {**(DI if counts["nDI"] else {}), **(DO if counts["nDO"] else {}), **COMMON}
    points = {}
    for row in table_rows(pages):
        key = (row["table"], " ".join(row["description"].split()))
        if key not in wanted:
            continue
        point_id, group, encoding, extra = wanted[key]
        require(point_id not in points, f"ICP DAS {selector}: duplicate row {key}")
        require(not row["span"] and int(row["decimal"]) == int(row["hex"], 16),
                f"ICP DAS {point_id}: decimal {row['decimal']} and hexadecimal 0x{row['hex']} disagree")
        kind = "bool" if encoding == "bool" else "u16" if encoding in ("u16", "enum") else encoding
        require(row["bits"] == BITS[kind], f"ICP DAS {point_id}: {row['bits']!r} bits per point")
        expected_points = "1" if group is None or point_id in SINGLE else f"1 to {group}"
        require(row["points"] == expected_points, f"ICP DAS {point_id}: points {row['points']!r}")
        point = {"id": point_id, "aliases": [key[1]], "table": row["table"], "address": int(row["decimal"]),
                 "type": kind}
        if expected_points != "1":
            point["count"] = counts[group]
        if kind == "u32":
            point["wordOrder"] = "little"
        if encoding == "enum":
            point["enum"] = {"values": enum_values(row["range_items"], extra, point_id)}
        elif point_id == "di_frequency":
            require(row["range"] == "0 to 4294967296", f"ICP DAS {point_id}: unexpected value range")
            point["conversion"] = {"exponent10": -len(extra.split(",")[1])}
            point["description"] = ("Frequency multiplied by 1,000; the client divides by 1,000. "
                                    "Measurement is enabled per channel by di_frequency_enable.")
        elif extra and extra.endswith(" second"):
            require(row["range"] == extra, f"ICP DAS {point_id}: unexpected range {row['range']!r}")
            point["unit"] = "s"
        elif extra:
            require(row["range"].startswith(extra), f"ICP DAS {point_id}: unexpected range {row['range']!r}")
            if point_id == "firmware_version":
                point["description"] = "Decimal digits of the firmware version: 123 means 1.2.3."
                point["stability"] = "constant"
            elif point_id == "module_name":
                point["description"] = "16-bit module name value; the manual does not document its encoding."
                point["stability"] = "constant"
        if row["access"] != "R":
            note = f"Vendor access {row['access']}; read-only in this contract."
            point["description"] = f"{point['description']} {note}" if "description" in point else note
        point["source"] = {"address": f"{row['decimal']} (0x{row['hex']})", "page": row["page"],
                           "reference": f"Section 6.3, {row['section']}"}
        points[point_id] = point
    missing = sorted({spec[0] for spec in wanted.values()} - points.keys())
    require(not missing, f"ICP DAS {selector}: rows missing: {missing}")
    order = {spec[0]: index for index, spec in enumerate(wanted.values())}
    return sorted(points.values(), key=lambda point: order[point["id"]])
