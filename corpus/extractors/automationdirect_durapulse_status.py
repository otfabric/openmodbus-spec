"""AutomationDirect DURApulse GS20, GS30 and GS4 user manuals (PDF): serial Modbus status addresses.

The selector names the manual: gs20, gs30 or gs4. Each address row gives the register in hexadecimal,
as a 40001-based decimal reference and in octal; all three must agree. The manuals' RTU read example
puts the hexadecimal address (2102H) in the request, so the hexadecimal column is the PDU address.
Values are holding registers read with function 03H.
"""
from html import unescape
import re
import subprocess

from sourcelib import pdf_pages, require

MANUALS = {
    "gs20": {"title": "DURApulse GS20 & GS20X AC Drive User Manual – 1st Edition, Rev. F",
             "list": (296, 299), "example": 292},
    "gs30": {"title": "DURApulse GS30 AC Drive User Manual – 1st Ed., Rev B",
             "list": (314, 317), "example": 311},
    "gs4": {"title": "DURApulse GS4 AC Drive User Manual – 1st Ed. Rev N – 04/02/2025",
            "list": (312, 313), "example": 320},
}
RTU_EXAMPLE = {
    "gs20": r"Function\s+03H\s+Function\s+03H\s*\n\s+21H\s.*\n\s+Starting data register\s*\n\s+02H\s",
    "gs30": r"Function\s+03H\s+Function\s+03H\s*\n\s+21H\s.*\n\s+Starting data register\s*\n\s+02H\s",
    "gs4": r"CMD\s+03H\s+CMD\s+03H\s*\n\s+21H\s.*\n\s+Starting data\s*\n.*\n\s+address\s+02H\s",
}
ADDRESS = re.compile(r"\s([0-9A-F]{4})h?\s+(4\d{4})\s+([0-7]{5})\s*$")
UNITS = {"Hz": "Hz", "V": "V", "kW": "kW", "rpm": "/min"}

# GS20 and GS30: (label on the address line, occurrence in the status section): (point id, unit or None)
# A unit of None means the unit and scale are parsed from "(XXX.XX Hz)" in the label.
# The status list gives no signedness, so values that can be negative (motor speed 210Ch, torque 210Bh)
# are left out.
GS2X_VALUES = {
    ("Frequency command (XXX.XX Hz)", 0): ("frequency_command", None),
    ("Output frequency (XXX.XX Hz)", 0): ("output_frequency", None),
    ("DC bus voltage (XXX.X V)", 0): ("dc_bus_voltage", None),
    ("Output voltage (XXX.X V)", 0): ("output_voltage", None),
    ("Display the output power of U, V, W (XXXX.X kW)", 0): ("output_power", None),
    ("KWH display (XXXX.X)", 0): ("energy", "kW.h"),
}
# GS4: label -> (point id, unit, exponent): the label gives the format "(xxx.x)" but no unit.
GS4_VALUES = {
    "DC-BUS Voltage U (xxx.x)": ("dc_bus_voltage", "V", -1),
    "Output Voltage E (xxx.x)": ("output_voltage", "V", -1),
    "Active Warning": ("active_warning", None, 0),
}
# Bit fields: field -> (point id, {raw value: (name, phrase the manual uses)})
GS2X_STATUS = {
    (1, 0): ("operation_status", {0: ("stopped", "The drive stops"),
                                  1: ("decelerating", "The drive is decelerating"),
                                  2: ("standby", "The drive is in standby status"),
                                  3: ("operating", "The drive is operating")}),
    (4, 3): ("operation_direction", {0: ("forward", "FWD running"),
                                     1: ("reverse_to_forward", "From REV running to FWD running"),
                                     2: ("forward_to_reverse", "From FWD running to REV running"),
                                     3: ("reverse", "REV running")}),
}
GS2X_DRIVE_STATUS = {
    (3, 2): ("drive_state", {1: ("ready", "Drive ready"), 2: ("error", "Error")}),
    (5, 5): ("warning_active", {0: ("no_warning", "No warning"), 1: ("warning", "Warning")}),
}
GS4_STATUS = {
    "Bit 0,1": ("operation_status", (1, 0), [("0", "stop", "Stop"),
                                             ("1", "decelerating", "Decelerate during the drive stopping"),
                                             ("10", "standby", "The drive standby"),
                                             ("11", "run", "Run")]),
    "Bit 3,4": ("operation_direction", (4, 3), [("0", "forward", "FWD"),
                                                ("1", "reverse_to_forward", "REV to FWD"),
                                                ("10", "forward_to_reverse", "FWD to REV"),
                                                ("11", "reverse", "REV")]),
}
IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)*")
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', re.S)
LINE = 2.0  # points: word boxes whose tops differ by less are on one line
TOUCH = 0.5  # points: boxes closer than this are one word; a space is about 2.5 pt


def clean(text):
    """The GS4 manual's text layer carries BEL (0x07) characters inside words; drop them."""
    return text.replace("\x07", "")


def field_mask(high, low):
    return ((1 << (high - low + 1)) - 1) << low


def address_rows(lines):
    """(line index, hex, label) for every line that ends in a hex/decimal/octal address triple."""
    rows = []
    for index, line in enumerate(lines):
        match = ADDRESS.search(line)
        if not match:
            continue
        hex_text, decimal, octal = match.groups()
        address = int(hex_text, 16)
        require(int(decimal) == 40001 + address and int(octal, 8) == address,
                f"DURApulse {hex_text}h: hex, decimal and octal addresses disagree")
        rows.append((index, hex_text, " ".join(line[:match.start()].split())))
    return rows


def source(hex_text, page, reference):
    return {"address": f"{hex_text}h", "page": page, "reference": reference}


def check_manual(data, selector):
    manual = MANUALS[selector]
    first, last = manual["list"]
    pages = pdf_pages(data, first, last)
    for page in pages:
        require(manual["title"] in " ".join(page.split()), f"DURApulse {selector}: page footer missing")
    example = pdf_pages(data, manual["example"])[0]
    require(re.search(RTU_EXAMPLE[selector], example), f"DURApulse {selector}: RTU read example of 2102H missing")
    return pages


def page_lines(pages, first):
    lines, page_of = [], []
    for offset, page in enumerate(pages):
        for line in page.splitlines():
            lines.append(line)
            page_of.append(first + offset)
    return lines, page_of


def parse_bits(lines):
    """Bit fields from GS20/GS30 rows such as 'bit 4–3  Operation direction' and '01B: ...'."""
    fields, current = {}, None
    for line in lines:
        line = ADDRESS.sub("", line)
        match = re.search(r"\bbit (\d+)(?:[–-](\d+))?\s+(.*)$", line)
        text = match.group(3) if match else line.strip()
        if match:
            high = int(match.group(1))
            current = (high, int(match.group(2)) if match.group(2) else high)
            require(current not in fields, f"DURApulse bit field {current} listed twice")
            fields[current] = {}
        value = re.search(r"(?:^|\s)([01]+)[Bb]?: (.+)$", text.strip())
        if value and current is not None:
            fields[current][int(value.group(1), 2)] = value.group(2).strip()
    return fields


def bit_points(lines, start, end, hex_text, page, selection, reference):
    begin = [index for index, line in enumerate(lines) if start in line]
    require(len(begin) == 1, f"DURApulse {hex_text}h: bit list start {start!r} not unique")
    stop = [index for index in range(begin[0], len(lines)) if end in lines[index]]
    require(stop, f"DURApulse {hex_text}h: bit list end {end!r} missing")
    block = lines[begin[0]:stop[0] + 1]
    require(any(re.search(rf"\s{hex_text}\s+4\d{{4}}\s+[0-7]{{5}}\s*$", line) for line in block),
            f"DURApulse {hex_text}h: address not inside its bit list")
    fields = parse_bits(block)
    points = []
    for (high, low), (point_id, values) in selection.items():
        require((high, low) in fields, f"DURApulse {hex_text}h: bit field {high}-{low} missing")
        found = fields[(high, low)]
        enum = []
        for raw, (name, phrase) in sorted(values.items()):
            require(found.get(raw) == phrase, f"DURApulse {hex_text}h bits {high}-{low}: value {raw} is "
                                              f"{found.get(raw)!r}, expected {phrase!r}")
            enum.append({"value": raw, "name": name, "label": phrase})
        points.append({"id": point_id, "address": int(hex_text, 16), "type": "u16",
                       "mask": field_mask(high, low), "enum": {"values": enum},
                       "description": f"Bits {high}-{low} of status address {hex_text}h.",
                       "source": source(hex_text, page, reference)})
    return points


def byte_points(rows, lines, page_of, hex_text, low_phrase, high_phrase, names, reference):
    matches = [(index, label) for index, row_hex, label in rows if row_hex == hex_text]
    require(len(matches) == 1, f"DURApulse {hex_text}h: expected one address row")
    index = matches[0][0]
    window = " ".join(" ".join(line.split()) for line in lines[index - 1:index + 2])
    require(low_phrase in window and high_phrase in window, f"DURApulse {hex_text}h: byte layout text missing")
    low_id, high_id = names
    page = page_of[index]
    return [
        {"id": low_id, "address": int(hex_text, 16), "type": "u16", "mask": 0x00FF,
         "description": f"Low byte of status address {hex_text}h: {low_phrase}.",
         "source": source(hex_text, page, reference)},
        {"id": high_id, "address": int(hex_text, 16), "type": "u16", "mask": 0xFF00,
         "description": f"High byte of status address {hex_text}h: {high_phrase}.",
         "source": source(hex_text, page, reference)},
    ]


def scaled_point(point_id, hex_text, label, page, unit, exponent, reference):
    point = {"id": point_id, "label": label, "address": int(hex_text, 16), "type": "u16"}
    if exponent:
        point["conversion"] = {"exponent10": exponent}
    if unit:
        point["unit"] = unit
    point["source"] = source(hex_text, page, reference)
    return point


def label_format(label):
    match = re.search(r"\((X+)(?:\.(X+))? (Hz|V|kW|rpm)\)$", label)
    require(match, f"DURApulse: no value format in {label!r}")
    return UNITS[match.group(3)], -len(match.group(2) or "")


def extract_gs2x(data, selector):
    first = MANUALS[selector]["list"][0]
    lines, page_of = page_lines(check_manual(data, selector), first)
    require(any("4) Address list" in line for line in lines), f"DURApulse {selector}: address list heading missing")
    rows = address_rows(lines)
    status_start = [position for position, (_, hex_text, _) in enumerate(rows) if hex_text == "2100"]
    require(len(status_start) == 1, f"DURApulse {selector}: status monitor section start missing")
    status_rows = rows[status_start[0]:]
    reference = "Address list, status monitor read only"
    points = byte_points(rows, lines, page_of, "2100", "Low Byte: Fault code", "High byte: Warning code",
                         ("fault_code", "warning_code"), reference)
    seen = {}
    for index, hex_text, label in status_rows:
        label = re.sub(r"^(Status monitor read\s+)?(only \(continued\)\s+)?", "", label)
        occurrence = seen.get(label, 0)
        seen[label] = occurrence + 1
        if (label, occurrence) not in GS2X_VALUES:
            continue
        point_id, unit = GS2X_VALUES[(label, occurrence)]
        if unit is None:
            unit, exponent = label_format(label)
        else:
            require(re.search(r"\(XXXX\.X\)$", label), f"DURApulse {label}: unexpected format")
            exponent = -1
        points.append(scaled_point(point_id, hex_text, label, page_of[index], unit, exponent, reference))
    found = {point["id"] for point in points}
    missing = {point_id for point_id, _ in GS2X_VALUES.values()} - found
    require(not missing, f"DURApulse {selector}: missing rows {sorted(missing)}")
    status_index = [index for index, hex_text, _ in rows if hex_text == "2101"][0]
    points += bit_points(lines, "AC motor drive operation status", "bit 15–13", "2101", page_of[status_index],
                         GS2X_STATUS, reference)
    drive_index = [index for index, hex_text, _ in rows if hex_text == "2226"][0]
    points += bit_points(lines, "Drive status", "1b: Warning", "2226", page_of[drive_index],
                         GS2X_DRIVE_STATUS, reference)
    return {"points": sorted(points, key=lambda point: (point["address"], point.get("mask", 0)))}


def word_boxes(data, page):
    """(xMin, yMin, xMax, yMax, text) per word of one page from 'pdftotext -bbox', BEL characters removed."""
    command = ["pdftotext", "-f", str(page), "-l", str(page), "-bbox", "-enc", "UTF-8", "-", "-"]
    result = subprocess.run(command, input=data, capture_output=True, check=True, timeout=120)
    words = []
    for x0, y0, x1, y1, text in WORD.findall(result.stdout.decode("utf-8")):
        text = clean(unescape(text))
        if text.strip():
            words.append((float(x0), float(y0), float(x1), float(y1), text))
    require(words, f"GS4 PDF page {page}: no words")
    return words


def box_lines(words):
    """Line texts, top to bottom. Touching word boxes are one word; a gap between boxes is a space.

    The GS4 text layer puts a BEL glyph at the start of each error description. Poppler versions
    order that glyph and the first letter differently in their text output, but not their boxes.
    """
    rows = []
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        if rows and abs(word[1] - rows[-1][0]) <= LINE:
            rows[-1][1].append(word)
        else:
            rows.append((word[1], [word]))
    texts = []
    for _, row in rows:
        row.sort(key=lambda w: w[0])
        text = row[0][4]
        for previous, word in zip(row, row[1:]):
            text += ("" if word[0] - previous[2] <= TOUCH else " ") + word[4]
        texts.append(text)
    return texts


def error_codes(data, page):
    """The two-column 'Status Monitor 1 Error Codes' list of GS4 status address 2100h, read from word boxes."""
    words = word_boxes(data, page)
    left = [w for w in words if w[4] == "0:" and any(v[4] == "No" and abs(v[1] - w[1]) <= LINE for v in words)]
    right = [w for w in words if w[4] == "40:" and any(v[4] == "Motor" and abs(v[1] - w[1]) <= LINE for v in words)]
    address = [w for w in words if w[4] == "2100"]
    end = [w for w in words if w[4] == "(table"]
    require(len(left) == 1 and len(right) == 1 and len(address) == 1, "GS4 2100h: error code columns not found")
    top = min(left[0][1], right[0][1]) - LINE
    require(len(end) == 1 and end[0][1] > top, "GS4 2100h: end of error code list missing")
    bounds = ((left[0][0], right[0][0]), (right[0][0], address[0][0]))
    columns = ([], [])
    for column, (low, high) in enumerate(bounds):
        boxes = [w for w in words if top <= w[1] < end[0][1] - LINE and low - 1 <= w[0] < high - 1]
        require(all(w[2] < high - 1 for w in boxes), f"GS4 2100h: column {column + 1} overlaps the next")
        for text in box_lines(boxes):
            match = re.fullmatch(r"(\d+)(?:~(\d+))?: (.+)", text)
            if match:
                columns[column].append([int(match.group(1)), int(match.group(2) or match.group(1)),
                                        match.group(3)])
            else:
                require(columns[column], f"GS4 2100h: continuation without entry: {text!r}")
                columns[column][-1][2] += " " + text
    entries = columns[0] + columns[1]
    expected = 0
    values = []
    for low, high, text in entries:
        require(low == expected and high >= low, f"GS4 2100h: code {low} out of sequence")
        expected = high + 1
        if text == "reserved":
            continue
        require(low == high, f"GS4 2100h: range {low}~{high} is not reserved")
        name = re.sub(r"[^a-z0-9]+", "_", text.split("(")[0].lower()).strip("_")
        require(IDENTIFIER.fullmatch(name), f"GS4 2100h: bad enum name {name!r}")
        values.append({"value": low, "name": name, "label": text})
    require(expected == 112, f"GS4 2100h: error code list ends at {expected - 1}")
    require(len({value["name"] for value in values}) == len(values), "GS4 2100h: duplicate enum name")
    return values


def gs4_status_bits(lines, page):
    points = []
    for label, (point_id, (high, low), expected) in GS4_STATUS.items():
        found = [index for index, line in enumerate(lines) if line.strip() == label]
        require(len(found) == 1, f"GS4 2101h: {label!r} not found once")
        index = found[0]
        neighbours = [lines[index - 2], lines[index - 1], lines[index + 1], lines[index + 2]]
        enum = []
        for line, (binary, name, phrase) in zip(neighbours, expected):
            require(line.strip() == f"{binary}: {phrase}", f"GS4 2101h {label}: unexpected line {line!r}")
            enum.append({"value": int(binary, 2), "name": name, "label": phrase})
        points.append({"id": point_id, "address": 0x2101, "type": "u16", "mask": field_mask(high, low),
                       "enum": {"values": enum}, "description": f"{label} of status monitor 2 (2101h).",
                       "source": source("2101", page, "Status Addresses (Read Only), Status Monitor 2")})
    running = [index for index, line in enumerate(lines) if re.fullmatch(r"\s*Bit 12\s+0: Drive stopped", line)]
    require(len(running) == 1 and lines[running[0] - 1].strip() == "Running Status"
            and lines[running[0] + 1].strip() == "1: Drive running (including Standby)",
            "GS4 2101h: running status bit 12 not found")
    points.append({"id": "running", "address": 0x2101, "type": "u16", "mask": 0x1000,
                   "enum": {"values": [{"value": 0, "name": "stopped", "label": "Drive stopped"},
                                       {"value": 1, "name": "running",
                                        "label": "Drive running (including Standby)"}]},
                   "description": "Bit 12 of status monitor 2 (2101h): running status.",
                   "source": source("2101", page, "Status Addresses (Read Only), Status Monitor 2")})
    return points


def extract_gs4(data):
    first, last = MANUALS["gs4"]["list"]
    pages = check_manual(data, "gs4")
    require("GS4 Status Addresses (Read Only)" in pages[0], "GS4: status address table missing")
    example = pdf_pages(data, MANUALS["gs4"]["example"])[0]
    limit = re.search(r"Command code: 03H, read N words\. The maximum value of N is (\d+)\.", " ".join(example.split()))
    require(limit, "GS4: read size limit statement missing")
    lines, page_of = page_lines([clean(page) for page in pages], first)
    rows = address_rows(lines)
    points = []
    row_2100 = [index for index, hex_text, _ in rows if hex_text == "2100"]
    require(len(row_2100) == 1 and "Error Codes" in lines[row_2100[0]], "GS4 2100h: address row missing")
    points.append({"id": "error_code", "label": "Status Monitor 1 error code", "address": 0x2100, "type": "u16",
                   "enum": {"values": error_codes(data, first)},
                   "source": source("2100", first, "Status Addresses (Read Only), Status Monitor 1")})
    points += gs4_status_bits([clean(line) for line in pages[1].splitlines()], last)
    found = set()
    for index, hex_text, label in rows:
        if label not in GS4_VALUES:
            continue
        require(label not in found, f"GS4: duplicate row {label!r}")
        found.add(label)
        point_id, unit, exponent = GS4_VALUES[label]
        format_match = re.search(r"\((x+)\.(x+)\)$", label)
        require((format_match and -len(format_match.group(2)) == exponent) or (not format_match and exponent == 0),
                f"GS4 {label}: format and selected scale disagree")
        points.append(scaled_point(point_id, hex_text, label, page_of[index], unit, exponent,
                                   "Status Addresses (Read Only)"))
    require(found == GS4_VALUES.keys(), f"GS4: missing rows {sorted(GS4_VALUES.keys() - found)}")
    points += byte_points(rows, lines, page_of, "2118", "Low Byte Active Error [2100h = Active Error/Fault]",
                          "High Byte Active Warning [2108h = Active Warning]",
                          ("active_error_low_byte", "active_warning_high_byte"), "Status Addresses (Read Only)")
    points = sorted(points, key=lambda point: (point["address"], point.get("mask", 0)))
    return {"points": points, "constraints": {"maxReadRegisters": int(limit.group(1))}}


def extract(data, selector):
    require(selector in MANUALS, f"Unknown DURApulse selector {selector!r}")
    return extract_gs4(data) if selector == "gs4" else extract_gs2x(data, selector)
