"""Lovato Electric DMG series, Modbus communication protocol (PDF, I317 I GB 02_22): selected measures.

The selector is the model: "DMG110", "DMG210" or "DMG800". Rows of Table 2 ("Measures supplied by
serial communication protocol") are selected by their Italian and English label, section and word
count; address, word count, unit, format and the model columns are parsed from the row.

Stated in the document and required here:

- Table 2 is "to be used with functions 03 and 04"; the contracts use the input-register table of
  the worked example (function 04).
- "The address in the query message must be decreased by one from the effective address reported
  in the table." The worked request reads "active power of line L2, which resides at location 22
  (16 Hex)" with the bytes 01 04 00 15 00 02 and a valid CRC; the table row for that label must sit
  at 0016H with two words.
- The worked answer carries 00 01 FB 00 = 129792 = 1.29792 kW: the first register is the most
  significant, and the row's unit "W/100" means the value divided by 100 is in W.
- Formats: "Unsigned long" and "Signed long" take 2 words, "Unsigned int" 1, "Unsigned long-long" 4.
- A mark in a model column means the address is supported by that model; a number next to it is the
  software revision from which it is supported. The first model column is shared by the DMG110 and
  the DMG210; a model name written in a cell limits the row to that model.
- The maximum number of registers per message for the selected model.

Three things the selection depends on:

- Frequency is Hz/1000, and "Hz/100 DMG210" for the DMG210; the unit cell is parsed per model.
- The note on the power rows says the resolution changes from 1/100 W to 1/10 W above 5 MW per
  phase, "simultaneously on all power measurements", as a function "available starting from SW
  revision 08 (DMG700) - 09 (DMG800) - 06 (DMG900)". The contract cannot state a scale that depends
  on another register, so the DMG800 selection has no power rows. The note names neither the DMG110
  nor the DMG210, and their equivalent power rows carry no note mark; they are mapped as W/100.
- The DMG110 has only the 4-word "Unsigned long-long" energy counters. The worked answer shows the
  register order of a 2-word value only, so those counters are left out of the DMG110 selection.

Text is read from Poppler's word boxes (`pdftotext -bbox`), which carry positions and are the same
in every Poppler version tried. The PDF's cross-reference table is damaged; Poppler repairs it when
it reads the file by path, so the bytes are written to a temporary file outside the checkout.
"""
import re
import subprocess
import tempfile
from decimal import Decimal
from html import unescape
from pathlib import Path

from sourcelib import require

MODELS = {"DMG110": "first", "DMG210": "first", "DMG800": "800"}
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', re.S)
LINE = 2.0       # points: word boxes whose centres differ by less are on one line
COLUMN = 9.0     # points: a mark belongs to the model column whose centre is this close
LABELS = 96.0    # points: the label columns start right of this on every table page
ENGLISH = 380.0  # points: the English text column of the two-column pages starts right of this
ROW = 25.0       # points: the tallest row that hangs below its address
ADDRESS = re.compile(r"[0-9A-F]{4}H")
FORMATS = {("Unsigned", "long"): ("u32", 2), ("Signed", "long"): ("i32", 2), ("Unsigned", "int"): ("u16", 1),
           ("Unsigned", "long-long"): ("u64", 4)}
UNITS = {"V": "V", "A": "A", "W": "W", "VA": "V.A", "Hz": "Hz", "%": "%", "kWh": "kW.h", "s": "s"}
NOT_UCUM = {"Var": "Vendor unit: var.", "bool": "The document gives the unit as bool."}
MEASURE_SECTIONS = ("IN", "HI", "LO", "AV", "MD")

IDENTITY = ["DMG SERIES", "MODBUS® COMMUNICATION PROTOCOL", "Doc. I317IGB02_22.doc 07/02/2022 P. 1 / 41"]
SERIAL = ("The digital multimeters DMG110 and DMG210 support the communication protocols Modbus RTU® and Modbus "
          "ASCII® on the RS-485 serial port.")
BUILT_IN = (r"The digital multimeter DMG\S+ DMG700, DMG800 and DMG900 support the communication protocols Modbus "
            r"RTU®, Modbus ASCII® and Modbus TCP® on the built-in port and on the expansion modules: x EXP 10 10 USB "
            r"x EXP 10 11 RS232 x EXP 10 12 RS485 x EXP 10 13 Ethernet")
MAXIMUM = (r"For the DMG series, the maximum length for the data field is: DMG110-210-300: (\d+) 16-bit registers "
           r"\(128 bytes\) \(from rev 5 del DMG300: 80 16-bit registers \(160 bytes\)\): DMG 6\S+-700-800-900: (\d+) "
           r"16-bit registers \(160 bytes\)")
REQUEST = (r"For instance, to read the value of active power of line L2 , which resides at location (\d+) "
           r"\(([0-9A-F]+) Hex\) from the DMG with serial address 01, the message to send is the following: "
           r"((?:[0-9A-F]{2} ){7}[0-9A-F]{2}) Whereas: 01= slave address (.{10,60}?) "
           r"([0-9A-F]{2} [0-9A-F]{2}) = Address of the required register \(active power L2\) decreased by one "
           r"([0-9A-F]{2} [0-9A-F]{2}) = Number of registers to be read beginning from address (\d+) "
           r"([0-9A-F]{2} [0-9A-F]{2}) = CRC Checksum")
ANSWER = (r"The DMG answer is the following: ((?:[0-9A-F]{2} ){8}[0-9A-F]{2}) Where: 01 = DMG address \(Slave 01\) "
          r"04 = Function requested by the master 04 = Number of bytes sent by the DMG "
          r"((?:[0-9A-F]{2} ){3}[0-9A-F]{2}) = Hex value of the active power L2=(\d+) = ([\d.]+) KW")
FUNCTION_04 = ("FUNCTION 04: READ INPUT REGISTER The Modbus® function 04 allows to read one or more consecutive "
               "registers from the slave memory. The address of each measure is given in the tables 2-4 on the final "
               "pages of this manual. As for Modbus® standard, the address in the query message must be decreased by "
               "one from the effective address reported in the table.")
TABLE_2 = "TABLE 2: MISURE FORNITE DAL PROTOCOLLO DI COM. MEASURES SUPPLIED BY SERIAL COMMUNICATION PROTOCOL " \
          "(Utilizzabili con funzioni 03 e 04) (To be used with functions 03 and 04)"
POWER_NOTE = (r"The power measuremet are normally specified with the resolution of 1/100W\. In case the maximum "
              r"theorical power per phase \(given by combination of CT and VT ratios\) is more than 5MW, then the "
              r"resolution of all power measurements will be 1/10W\. It is possible to make query to address 2F70H to "
              r"see if the device if it is working with lower or higher resolution\. If it returns 0000h then it is "
              r"working with standard 1/100W resolution, otherwise it is working with 1/10W\. The scale never changes "
              r"during operation of the instrument, unless CT or VT settings are changed\. The scale change is applied "
              r"simultaneously on all power measurements \(W, var, VA\)\. This function is available starting from SW "
              r"revision 08 \(DMG700\) \S 09 \(DMG800\) \S 06 \(DMG900\)\.")
ROLLOVER_2 = (r"The energy counters at these addresses are 2 words \(4 bytes\) long\. They roll-over to 0 after having "
              r"exceeded the count value of (19 999 999) \.(99 kWh)\.")
REVISION_NOTE = r"Note: (\S+)rting from which the address is supported by the protocol\."
ALARM_NOTE = (r"(\S) The status of bit 0 indicates a latched alarm\. (?:.{0,60}? )?The status of bit 1 indicates an "
              r"active alarm\.")
POWER_SCOPE = ("Resolution 1/100 W. The document's note on power resolution describes a change to 1/10 W above 5 MW "
               "per phase as a function of the DMG700, DMG800 and DMG900.")

# (section, Italian label, English label, words) -> (point id, format, vendor unit, extras)
VOLTAGE_CURRENT = {
    ("IN", "Tensione di fase L1", "L1 Phase Voltage", 2): ("voltage_l1_n", "Unsigned long", "V/100", {}),
    ("IN", "Tensione di fase L2", "L2 Phase Voltage", 2): ("voltage_l2_n", "Unsigned long", "V/100", {}),
    ("IN", "Tensione di fase L3", "L3 Phase Voltage", 2): ("voltage_l3_n", "Unsigned long", "V/100", {}),
    ("IN", "Corrente di fase L1", "L1 Current", 2): ("current_l1", "Unsigned long", "A/10000", {}),
    ("IN", "Corrente di fase L2", "L2 Current", 2): ("current_l2", "Unsigned long", "A/10000", {}),
    ("IN", "Corrente di fase L3", "L3 Current", 2): ("current_l3", "Unsigned long", "A/10000", {}),
    ("IN", "Tensione L1-L2", "L1-L2 Voltage", 2): ("voltage_l1_l2", "Unsigned long", "V/100", {}),
    ("IN", "Frequenza", "Frequency", 2): ("frequency", "Unsigned long", ("Hz/1000", "Hz/100"),
                                          {"band": "between"}),
}
POWER = {
    ("IN", "Potenza Attiva equivalente", "Eqv. Active Power", 2): (
        "active_power_total", "Signed long", "W/100", {"description": POWER_SCOPE}),
    ("IN", "Potenza Reattiva equivalente", "Eqv. Reactive Power", 2): (
        "reactive_power_total", "Signed long", "Var/100", {"description": POWER_SCOPE}),
    ("IN", "Potenza Apparente equivalente", "Eqv. Apparent Power", 2): (
        "apparent_power_total", "Unsigned long", "VA/100", {"description": POWER_SCOPE}),
}
QUALITY = {
    ("IN", "Fattore Di Potenza equivalente", "Eqv Power Factor", 2): (
        "power_factor_total", "Signed long", "/10000", {}),
    ("IN", "Thd Tensione L1", "L1 Voltage Thd", 2): ("voltage_thd_l1", "Unsigned long", "%/100", {}),
    ("IN", "Thd Corrente L1", "L1 Current Thd", 2): ("current_thd_l1", "Unsigned long", "%/100", {}),
}
ENERGY_2 = {
    (None, "Energia Attiva Importata totale", "Total imp. Active Energy", 2): (
        "active_energy_import", "Unsigned long", "kWh / 100", {"rollover": True}),
    (None, "Energia Attiva Esportata totale", "Total exported Active Energy", 2): (
        "active_energy_export", "Unsigned long", "kWh / 100", {"rollover": True}),
}
HOUR_METER = {
    (None, "Contaore totale", "Total Hour meter", 2): ("hour_meter_total", "Unsigned long", "s", {}),
}
PHASE_SEQUENCE = {
    (None, "Sequenza fasi", "Phase sequence", 1): (
        "phase_sequence", "Unsigned int", None,
        {"band": "below", "enum": {1: ("good", "good"), 0: ("not_good", "not good")}}),
}
DMG800_STATUS = {
    (None, "Anno", "Year", 1): ("clock_year", "Unsigned int", None, {}),
    (None, "Ingresso 1", "Input 1", 1): ("input_1", "Unsigned int", "bool", {}),
    (None, "Allarme 1", "Alarm 1", 1): (
        "alarm_1", "Unsigned int", None,
        {"note_flags": {0: ("latched", "latched alarm"), 1: ("active", "active alarm")}}),
}
SELECTED = {
    "DMG110": {**VOLTAGE_CURRENT, **POWER, **QUALITY, **HOUR_METER, **PHASE_SEQUENCE},
    "DMG210": {**VOLTAGE_CURRENT, **POWER, **QUALITY, **ENERGY_2, **HOUR_METER, **PHASE_SEQUENCE},
    "DMG800": {**VOLTAGE_CURRENT, **QUALITY, **ENERGY_2, **HOUR_METER, **DMG800_STATUS},
}
# The row the worked request and answer read.
EXAMPLE_ROW = ("IN", "Potenza Attiva L2", "L2 Active Power", 2)


def crc16(frame):
    """Modbus RTU CRC; the frame carries the low byte first."""
    crc = 0xFFFF
    for byte in frame:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, crc >> 8])


def unshift(text):
    """Some runs of this PDF map every glyph 29 code points too low; undo the shift and drop the spaces."""
    shifted = "".join(chr(ord(char) + 29) if ord(char) < 0x63 else char for char in text if not char.isspace())
    return shifted.replace(" ", "")


def document_words(data):
    """Word boxes (x0, y0, x1, y1, text) per page, read from a temporary copy of the PDF."""
    with tempfile.TemporaryDirectory(prefix="openmodbus-") as folder:
        path = Path(folder) / "source.pdf"
        path.write_bytes(data)
        result = subprocess.run(["pdftotext", "-bbox", "-enc", "UTF-8", str(path), "-"], capture_output=True,
                                check=True, timeout=120)
    pages = result.stdout.decode("utf-8").split("<page ")[1:]
    return [[(float(x0), float(y0), float(x1), float(y1), unescape(text))
             for x0, y0, x1, y1, text in WORD.findall(page)] for page in pages]


def page_lines(words):
    """Lines of a page, top to bottom: (y centre, words sorted by x)."""
    lines = []
    for word in sorted(words, key=lambda item: ((item[1] + item[3]) / 2, item[0])):
        centre = (word[1] + word[3]) / 2
        if lines and abs(lines[-1][0] - centre) <= LINE:
            lines[-1][1].append(word)
        else:
            lines.append((centre, [word]))
    return [(centre, sorted(line)) for centre, line in lines]


def text_of(lines, left=0.0):
    return " ".join(word[4] for _, line in lines for word in line if word[0] >= left)


def centre(word):
    return (word[0] + word[2]) / 2


def check_document(pages):
    """Require the statements the mapping rests on; return the facts parsed from them."""
    require(len(pages) == 41, f"Lovato DMG: expected 41 pages, got {len(pages)}")
    title = text_of(pages[0])
    for marker in IDENTITY:
        require(marker in title, f"Lovato DMG: identity {marker!r} not found")
    english = " ".join(text_of(page, ENGLISH) for page in pages[1:5])
    require(SERIAL in english, "Lovato DMG: statement on the DMG110 and DMG210 serial protocols not found")
    require(re.search(BUILT_IN, english), "Lovato DMG: statement on the DMG800 protocols and ports not found")
    require(FUNCTION_04 in english, "Lovato DMG: function 04 section and the decrease-by-one rule not found")
    maximum = re.findall(MAXIMUM, english)
    require(len(maximum) == 1, "Lovato DMG: maximum data field length not found once")

    request = re.findall(REQUEST, english)
    require(len(request) == 1, "Lovato DMG: worked request not found once")
    location, location_hex, frame, function, address, count, start, crc = request[0]
    frame = bytes.fromhex(frame)
    require(crc16(frame[:6]) == frame[6:] == bytes.fromhex(crc), "Lovato DMG: worked request has no valid CRC")
    decoded = unshift(function)
    require(re.fullmatch(r"04Modbus\S?function\SReadinputregister\S", decoded) and frame[1] == 4,
            f"Lovato DMG: worked request does not use function 04 ({decoded!r})")
    require(int(location) == int(location_hex, 16) == int(start), "Lovato DMG: worked request locations disagree")
    require(frame[2:4] == bytes.fromhex(address) and int.from_bytes(frame[2:4], "big") == int(location) - 1,
            "Lovato DMG: worked request does not send the table address decreased by one")
    require(frame[4:6] == bytes.fromhex(count), "Lovato DMG: worked request register count disagrees")

    answer = re.findall(ANSWER, english)
    require(len(answer) == 1, "Lovato DMG: worked answer not found once")
    frame_text, value_hex, value, kilowatt = answer[0]
    reply = bytes.fromhex(frame_text)
    require(crc16(reply[:7]) == reply[7:] and reply[1] == 4 and reply[2] == 4,
            "Lovato DMG: worked answer is not a valid function 04 reply of four bytes")
    require(reply[3:7] == bytes.fromhex(value_hex) and int.from_bytes(reply[3:7], "big") == int(value),
            "Lovato DMG: worked answer is not most significant register first")
    require(Decimal(value).scaleb(-2) == Decimal(kilowatt) * 1000,
            "Lovato DMG: worked answer does not read W/100 as the value divided by 100")
    return {"location": int(location), "registers": int.from_bytes(frame[4:6], "big"),
            "maximum": {"DMG110": int(maximum[0][0]), "DMG210": int(maximum[0][0]), "DMG800": int(maximum[0][1])}}


def table_pages(pages):
    """Indices of the pages of Table 2: from its heading to the page before Table 3."""
    first = [index for index, page in enumerate(pages) if TABLE_2 in text_of(page)]
    last = [index for index, page in enumerate(pages) if "TABLE 3:" in text_of(page) or "TABELLA 3:" in text_of(page)]
    require(len(first) == 1 and len(last) == 1 and first[0] < last[0], "Lovato DMG: Table 2 pages not found")
    return range(first[0], last[0])


def header_of(lines, index):
    """Column positions from the header line holding "Address UNIT ... 300 700 800 900"."""
    y, line = lines[index]
    texts = [word[4] for word in line]
    if not {"Address", "UNIT", "300", "700", "800", "900"} <= set(texts):
        return None
    columns = {word[4]: centre(word) for word in line if word[4] in ("300", "700", "800", "900")}
    limit = columns["300"] - COLUMN
    first = [word for line_y, near in lines if y - 14 <= line_y <= y + 6
             for word in near if word[4] in ("110", "210") and word[2] < limit]
    require(first, "Lovato DMG: first model column not found in a table header")
    columns["first"] = sum(centre(word) for word in first) / len(first)
    return {"columns": columns, "first_models": {f"DMG{word[4]}" for word in first},
            "unit": next(word[0] for word in line if word[4] == "UNIT"), "top": y - 14, "bottom": y + 6}


def table_rows(pages, indices):
    """Address rows of Table 2 with their header columns, section and neighbours."""
    rows, section = [], None
    for index in indices:
        lines = pages[index]
        header, on_page = None, []
        for position, (y, line) in enumerate(lines):
            found = header_of(lines, position)
            if found:
                header = found
                continue
            if header is None or header["top"] <= y <= header["bottom"]:
                continue
            text = " ".join(word[4] for word in line)
            if ADDRESS.fullmatch(line[0][4]) and line[0][0] < 60:
                on_page.append({"page": index + 1, "y": y, "line": line, "header": header, "section": section,
                                "lines": lines})
                continue
            marker = re.search(r"\((IN|HI|LO|AV|MD)\)", text)
            if marker:
                section = marker.group(1)
            elif text == "ARMONICHE HARMONICS":
                section = "HARMONICS"
        for row in on_page:
            same = [other for other in on_page if other["header"] is row["header"]]
            place = same.index(row)
            row["previous"] = same[place - 1]["y"] if place else None
            row["next"] = same[place + 1]["y"] if place + 1 < len(same) else None
        rows += on_page
    return rows


def band(row, kind):
    """The words of a row: its address line, plus the lines its cells spread over."""
    y, previous, following = row["y"], row["previous"], row["next"]
    if kind == "line":
        low, high = y - LINE, y + LINE
    elif kind == "between":
        require(previous is not None and following is not None, "Lovato DMG: row has no neighbours")
        low, high = previous + LINE, following - LINE
    else:
        low, high = y - LINE, min(following - LINE if following else y + ROW, y + ROW)
    return [(abs(line_y - y) <= LINE, word) for line_y, line in row["lines"] if low < line_y < high for word in line]


def parse_row(row, kind, italian, english, count):
    """Parse one row; None when its labels or its word count differ."""
    labels = italian.split() + english.split()
    anchor = [word for word in row["line"] if word[0] >= LABELS]
    if [word[4] for word in anchor[:len(labels)]] != labels:
        return None
    words = band(row, kind)
    header = row["header"]
    columns = header["columns"]
    address = row["line"][0][4]
    lead = [word[4] for _, word in words if word[2] <= LABELS and word[4] != address]
    counts = [text for text in lead if text in ("1", "2", "4")]
    require(len(counts) == 1 and all(len(text) == 1 for text in lead), f"Lovato DMG {address}: no single word count")
    if int(counts[0]) != count:
        return None

    rest = [(on_anchor, word) for on_anchor, word in words
            if word[0] >= LABELS and not (on_anchor and word in anchor[:len(labels)])]
    formats = [(index, (first[1][4], second[1][4])) for index, (first, second) in enumerate(zip(rest, rest[1:]))
               if (first[1][4], second[1][4]) in FORMATS and abs(first[1][1] - second[1][1]) <= LINE]
    require(len(formats) == 1, f"Lovato DMG {address}: no single format")
    position, kind_of = formats[0]
    del rest[position:position + 2]

    marks = {}  # column -> {"mark": bool, "revision": text or None, "names": set}
    units, extra_units, continuation = [], [], []
    for on_anchor, word in rest:
        if centre(word) >= columns["first"] - 12:
            column = min(columns, key=lambda name: abs(columns[name] - centre(word)))
            text = word[4]
            if abs(columns[column] - centre(word)) > COLUMN:
                # The "6..." column lies right of the 900 column and is not used.
                require(centre(word) > columns["900"] + COLUMN, f"Lovato DMG {address}: {text!r} is in no column")
                continue
            entry = marks.setdefault(column, {"mark": False, "revision": None, "names": set()})
            if text in ("DMG110", "DMG210"):
                entry["names"].add(text)
            elif text in ("110", "210"):
                entry["names"].add(f"DMG{text}")
            elif re.fullmatch(r"\d{1,2}", text):
                entry["revision"] = text
            elif re.fullmatch(r"[^\x00-\x7f]\d{0,2}", text):
                entry["mark"] = True
                entry["revision"] = text[1:] or entry["revision"]
            else:
                require(text == "DMG", f"Lovato DMG {address}: unexpected {text!r} in a model column")
        elif on_anchor:
            require(word[0] >= header["unit"] - 14, f"Lovato DMG {address}: unexpected {word[4]!r} after the labels")
            units.append(word[4])
        elif word[0] >= header["unit"] - 14:
            extra_units.append(word[4])
        else:
            continuation.append(word)
    english_x = anchor[len(italian.split())][0]
    return {"address": address, "page": row["page"], "section": row["section"], "words": int(counts[0]),
            "format": " ".join(kind_of), "units": units, "extra_units": extra_units, "marks": marks,
            "first_models": header["first_models"],
            "english_lines": [" ".join(word[4] for word in line if word[0] >= english_x - 1)
                              for _, line in page_lines(continuation)]}


def supported(parsed, model):
    """(supported, software revision written next to the mark) for the model."""
    column = MODELS[model]
    entry = parsed["marks"].get(column)
    if entry is None:
        return False, None
    if column == "first":
        require(model in parsed["first_models"], f"Lovato DMG {parsed['address']}: first column is not for {model}")
        if entry["names"]:
            return model in entry["names"], entry["revision"]
    return entry["mark"], entry["revision"]


def unit_fields(point, text, extra):
    """Unit, scale and description from a unit cell such as "V/100" or "kWh / 100"."""
    notes = [extra["description"]] if "description" in extra else []
    scaled = re.fullmatch(r"([A-Za-z%]*) ?/ ?(10+)", text)
    base = scaled.group(1) if scaled else text
    if scaled:
        point["conversion"] = {"exponent10": 1 - len(scaled.group(2))}
    if base in UNITS:
        point["unit"] = UNITS[base]
    elif base in NOT_UCUM:
        notes.append(NOT_UCUM[base])
    else:
        require(base == "", f"Lovato DMG {point['id']}: unknown unit {text!r}")
    return notes


def extract(data, selector):
    require(selector in MODELS, f"Unknown Lovato DMG model {selector!r}")
    pages = [page_lines(words) for words in document_words(data)]
    facts = check_document(pages)
    indices = table_pages(pages)
    notes = " ".join(text_of(pages[index]) for index in indices)
    require(re.search(POWER_NOTE, notes), "Lovato DMG: note on the power resolution not found")
    rollover = re.findall(ROLLOVER_2, notes)
    require(len(rollover) == 1, "Lovato DMG: note on the 2-word energy counters not found once")
    revision = re.findall(REVISION_NOTE, notes)
    require(len(revision) == 1 and unshift(revision[0]).startswith("Inthefollowingtables,thenumbernearofthesymbol")
            and "indicatestheSWrevisionoftheDMGsta" in unshift(revision[0]),
            "Lovato DMG: note on software revisions next to the marks not found")
    alarm = re.findall(ALARM_NOTE, notes)
    require(len(alarm) == 1, "Lovato DMG: note on the alarm bits not found once")
    rows = table_rows(pages, indices)

    def find(key, kind):
        section, italian, english, count = key
        matches = []
        for row in rows:
            if (row["section"] in MEASURE_SECTIONS) != (section is not None) or (section and row["section"] != section):
                continue
            parsed = parse_row(row, kind, italian, english, count)
            if parsed:
                matches.append(parsed)
        return matches

    example = find(EXAMPLE_ROW, "line")
    require(len(example) == 1 and int(example[0]["address"][:-1], 16) == facts["location"]
            and example[0]["words"] == facts["registers"] and example[0]["format"] == "Signed long"
            and example[0]["units"][:1] == ["W/100"],
            "Lovato DMG: Table 2 disagrees with the worked request for L2 active power")

    points = []
    for key, (point_id, kind, vendor_unit, extra) in SELECTED[selector].items():
        matches = [(parsed, supported(parsed, selector)) for parsed in find(key, extra.get("band", "line"))]
        matches = [(parsed, revision) for parsed, (applies, revision) in matches if applies]
        require(len(matches) == 1, f"Lovato DMG {selector}: {len(matches)} rows for {key}")
        parsed, revision = matches[0]
        address = parsed["address"]
        require(parsed["format"] == kind and FORMATS[tuple(kind.split())][1] == parsed["words"],
                f"Lovato DMG {address}: format {parsed['format']!r} with {parsed['words']} words")
        units = list(parsed["units"])
        if "note_flags" in extra:
            require(units == [alarm[0]], f"Lovato DMG {address}: unit cell does not point at the alarm note")
            units = []
        if isinstance(vendor_unit, tuple):
            default, other = vendor_unit
            require(units == [] and parsed["extra_units"][:2] == [default, other]
                    and parsed["extra_units"][2:] in (["DMG110"], ["DMG210"]),
                    f"Lovato DMG {address}: unexpected unit cell {parsed['extra_units']}")
            text = other if parsed["extra_units"][2] == selector else default
        else:
            require(not parsed["extra_units"], f"Lovato DMG {address}: unexpected unit lines")
            text = " ".join(units)
            require(text == (vendor_unit or ""), f"Lovato DMG {address}: unit {text!r}, expected {vendor_unit!r}")
        point = {"id": point_id, "address": int(address[:-1], 16) - 1, "type": FORMATS[tuple(kind.split())][0]}
        notes_of = unit_fields(point, text, extra)
        if "rollover" in extra:
            notes_of.append("Rolls over to 0 above {}.{}.".format(*rollover[0]))
        if revision:
            notes_of.append(f"The document marks this address with software revision {revision} for the model.")
        if notes_of:
            point["description"] = " ".join(notes_of)
        if "enum" in extra:
            found = [re.fullmatch(r"(\d) = (.+)", line) for line in parsed["english_lines"]]
            require(all(found) and {int(match.group(1)): match.group(2) for match in found}
                    == {raw: label for raw, (_, label) in extra["enum"].items()},
                    f"Lovato DMG {address}: unexpected value list {parsed['english_lines']}")
            point["enum"] = {"values": [{"value": raw, "name": name, "label": label}
                                        for raw, (name, label) in extra["enum"].items()]}
        if "note_flags" in extra:
            point["flags"] = {"flags": [{"bit": bit, "name": name, "label": label}
                                        for bit, (name, label) in extra["note_flags"].items()]}
        point["aliases"] = [key[2]]
        reference = "Table 2" + (f", section ({parsed['section']})" if key[0] else "")
        point["source"] = {"address": address, "page": parsed["page"], "reference": f"{reference}, {key[2]}"}
        points.append(point)
    return {"points": sorted(points, key=lambda point: point["address"]),
            "constraints": {"maxReadRegisters": facts["maximum"][selector]}}
