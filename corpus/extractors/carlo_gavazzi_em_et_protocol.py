"""Carlo Gavazzi EM100/ET100, EM210, EM24 and EM300/ET300 series communication protocols (PDF).

The selector is the model: "em111", "em112", "em210", "em24-din", "em24-is",
"em330", "et330", "em340" or "et340". The documents share one table layout:
Modicom address, Physical address, Length, VARIABLE, Data Format, Notes.

A Notes cell often spans several rows (one "Value weight" for six voltages)
and is then centred on them, which only word positions show. The tables are
therefore read from `pdftotext -bbox` word boxes: a row is the words on the
baseline of its Modicom address, and a Notes line is assigned to the rows it
is centred on. Rows are selected by table number and VARIABLE label; the
Modicom and physical addresses must agree.
"""
import re
import subprocess
from html import unescape

from sourcelib import modicon_reference, pdf_page_count, pdf_pages, require

BASE = 1.5    # words of one table row share a baseline within this many points
OWN = 2.0     # a Notes line this close to a row's baseline belongs to that row
CENTRE = 1.0  # a Notes cell is centred on its rows within this many points
GAP = 11.0    # consecutive lines of one Notes cell are closer than this
REACH = 21.0  # half the height of the tallest Notes cell that is centred on a single row

WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
MODICOM = re.compile(r"3\d{5}")
PHYSICAL = re.compile(r"[0-9A-F]{4}h")
TABLE_ID = re.compile(r"\d+\.\d+-\d+")
FORMATS = ("INT16", "INT32", "INT64", "UINT16", "UINT32", "UINT64")
WEIGHT = re.compile(r"(?:\(\*\) )?Value weight: ?(\S+?) ?\* ?(\d+)(?:, (.*))?")
VALUE = re.compile(r"Value=(\d+): (.+?)(?= Value=\d+: |$)")
ITEM = re.compile(r"(E[MT]\d{3})-DIN[ .](AV\d)[ .].*")
UNITS = {"Volt": "V", "Ampere": "A", "Watt": "W", "VA": "V.A", "var": None, "Var": None, "PF": None, "Hz": "Hz",
         "kWh": "kW.h", "kvarh": None}
TYPES = {"INT16": ("i16", 1), "INT32": ("i32", 2), "UINT16": ("u16", 1)}
READ_ONLY = "MODBUS: read only mode with functions code 03 and 04"
ONE_WORD = READ_ONLY + " limited to a word at a time"

# Selection tables: label -> (point id, data format, weight unit, the overflow value applies).
EM100 = {
    "V L-N": ("voltage", "INT32", "Volt", True),
    "A": ("current", "INT32", "Ampere", True),
    "W": ("active_power", "INT32", "Watt", True),
    "VA": ("apparent_power", "INT32", "VA", True),
    "var": ("reactive_power", "INT32", "var", True),
    "W dmd": ("active_power_demand", "INT32", "Watt", False),
    "W dmd peak": ("active_power_demand_peak", "INT32", "Watt", False),
    "PF": ("power_factor", "INT16", "PF", False),
    "Hz": ("frequency", "INT16", "Hz", False),
    "kWh (+) TOT": ("import_active_energy", "INT32", "kWh", False),
    "Kvarh (+) TOT": ("import_reactive_energy", "INT32", "kvarh", False),
    "kWh (-) TOT": ("export_active_energy", "INT32", "kWh", False),
    "kvarh (-) TOT": ("export_reactive_energy", "INT32", "kvarh", False),
}
THREE_PHASE = {
    "V L1-N": ("voltage_l1_n", "INT32", "Volt", True),
    "V L2-N": ("voltage_l2_n", "INT32", "Volt", True),
    "V L3-N": ("voltage_l3_n", "INT32", "Volt", True),
    "V L1-L2": ("voltage_l1_l2", "INT32", "Volt", True),
    "A L1": ("current_l1", "INT32", "Ampere", True),
    "A L2": ("current_l2", "INT32", "Ampere", True),
    "A L3": ("current_l3", "INT32", "Ampere", True),
}
EM210 = {
    **THREE_PHASE,
    "W Σ": ("active_power_total", "INT32", "Watt", True),
    "VA Σ": ("apparent_power_total", "INT32", "VA", True),
    "VAR Σ": ("reactive_power_total", "INT32", "Var", True),
    "PF Σ": ("power_factor_total", "INT16", "PF", False),
    "kWh(+) TOT": ("import_active_energy", "INT32", "kWh", False),
    "kWh(-) TOT": ("export_active_energy", "INT32", "kWh", False),
    "Neutral current (In)": ("neutral_current", "INT32", "Ampere", False),
}
EM24_DIN = {
    **THREE_PHASE,
    "W Σ": ("active_power_total", "INT32", "Watt", True),
    "VA Σ": ("apparent_power_total", "INT32", "VA", True),
    "VAR Σ": ("reactive_power_total", "INT32", "var", True),
    "PF Σ": ("power_factor_total", "INT16", "PF", False),
    "Hz": ("frequency", "INT16", "Hz", False),
    "kWh(+) TOT": ("import_active_energy", "INT32", "kWh", False),
    "kWh(-) TOT": ("export_active_energy", "INT32", "kWh", False),
}
EM24_IS = {
    **THREE_PHASE,
    "V L2-L3": ("voltage_l2_l3", "INT32", "Volt", True),
    "V L-N Σ": ("voltage_l_n_system", "INT32", "Volt", True),
    "V L-L Σ": ("voltage_l_l_system", "INT32", "Volt", True),
    "PF Σ": ("power_factor_total", "INT16", "PF", False),
    "Hz": ("frequency", "INT16", "Hz", False),
    "kWh(+) TOT": ("import_active_energy", "INT32", "kWh", False),
}
EM300 = {
    **THREE_PHASE,
    "W sys": ("active_power_total", "INT32", "Watt", True),
    "VA sys": ("apparent_power_total", "INT32", "VA", True),
    "var sys": ("reactive_power_total", "INT32", "var", True),
    "PF sys": ("power_factor_total", "INT16", "PF", False),
    "Hz": ("frequency", "INT16", "Hz", False),
    "kWh (+) TOT": ("import_active_energy", "INT32", "kWh", False),
    "kWh (-) TOT": ("export_active_energy", "INT32", "kWh", False),
}
# The neutral current row of the EM300/ET300 document carries this restriction in its Notes cell.
AN_SCOPE = "only ET series and EM330 (other cases: value =0)"
AN_MODELS = ("em330", "et330", "et340")
FULL_OVERFLOW = ('The overflow indication "EEE" is displayed when the MSB value of the relevant variable is '
                 "7FFFFFFFh (word order FFFF 7FFF).")
MSW_OVERFLOW = "is displayed when the MSB value of the relevant variable is 7FFFh."
FAMILIES = {
    "em100": {
        "title": ("EM100 Series", "ET100 Series", "COMMUNICATION", "PROTOCOL", "Version 2 Revision 14"),
        "table": "2.4-1", "rows": EM100, "overflow": FULL_OVERFLOW, "firmware": "2.5-1",
    },
    "em210": {
        "title": ("EM210_AV", "COMMUNICATION", "PROTOCOL", "Version 4 Revision 3", "May 10th, 2018"),
        "table": "2.3-1", "rows": EM210, "overflow": MSW_OVERFLOW, "firmware": "2.5-1",
    },
    "em24-din": {
        "title": ("EM24-DIN", "PFA, PFB & X models", "COMMUNICATION", "PROTOCOL", "Version 4 Revision 0",
                  "December 03th, 2012"),
        "table": "2.3-1", "rows": EM24_DIN, "overflow": MSW_OVERFLOW,
    },
    "em24-is": {
        "title": ("EM24-IS", "SFA and SFB versions", "COMMUNICATION", "PROTOCOL", "Revision 2.0"),
        "table": "2.3-1", "rows": EM24_IS, "overflow": MSW_OVERFLOW,
    },
    "em300": {
        "title": ("EM300 Series", "ET300 Series", "COMMUNICATION", "PROTOCOL", "Version 2 Revision 17",
                  "(July 05, 2021)"),
        "table": "2.4-1", "rows": EM300, "overflow": FULL_OVERFLOW, "firmware": "2.7-1",
    },
}
# selector -> (family, text that names the model in the document)
SELECTORS = {
    "em111": ("em100", "EM111-DIN AV8 1 x S1 X"),
    "em112": ("em100", "EM112-DIN AV0 1 x S1 X"),
    "em210": ("em210", "information necessary to read/write from/to EM210 has been reported"),
    "em24-din": ("em24-din", "EM24-DIN PFA, PFB & X models - Communication Protocol"),
    "em24-is": ("em24-is", "EM24-IS – Serial communication Protocol (SFA versions)"),
    "em330": ("em300", "EM330-DIN AV5 3 L S1 X"),
    "et330": ("em300", "ET330-DIN AV5 3 L S1 X"),
    "em340": ("em300", "EM340-DIN AV2 3 X S1 X"),
    "et340": ("em300", "ET340-DIN AV2 3 X S1 X"),
}


def clean(text):
    """Word text with typographic quotes made plain and the summation glyphs written as one letter."""
    for glyph in ("\uf0e5", "∑"):  # Symbol-font sigma (private use) and N-ary summation
        text = text.replace(glyph, "Σ")
    for quote in ("“", "”"):
        text = text.replace(quote, '"')
    return text.replace("’", "'").strip()


def flat(text):
    return " ".join(clean(text).split())


def page_words(data):
    """Per page, the words as (x0, y, text); y is the vertical centre of the word box."""
    command = ["pdftotext", "-bbox", "-enc", "UTF-8", "-", "-"]
    result = subprocess.run(command, input=data, capture_output=True, check=True, timeout=120)
    pages = []
    for chunk in result.stdout.decode("utf-8").split("<page ")[1:]:
        words = []
        for x0, y0, _, y1, text in WORD.findall(chunk):
            text = clean(unescape(text))
            if text:
                words.append((float(x0), (float(y0) + float(y1)) / 2, text))
        pages.append(words)
    require(pages, "Carlo Gavazzi PDF has no pages")
    return pages


def word_lines(words, tolerance):
    """[(y, words left to right)] top to bottom; words whose centres lie within the tolerance form one line."""
    lines = []
    for word in sorted(words, key=lambda item: item[1]):
        if lines and word[1] - lines[-1][0] <= tolerance:
            lines[-1][1].append(word)
        else:
            lines.append((word[1], [word]))
    return [(y, sorted(line)) for y, line in lines]


def text_lines(words, tolerance):
    return [(y, " ".join(text for _, _, text in line)) for y, line in word_lines(words, tolerance)]


def table_rows(words):
    """Rows of one table part: the words on the baseline of each Modicom address, split by their shape.

    A row whose cells are not on one baseline (the address centred beside a two-line label) does not
    parse and cannot be selected.
    """
    rows = []
    for anchor in sorted((word for word in words if MODICOM.fullmatch(word[2])), key=lambda item: item[1]):
        line = sorted(word for word in words if abs(word[1] - anchor[1]) <= BASE)
        texts = [text for _, _, text in line]
        if line[0] is not anchor or len(texts) < 4 or not PHYSICAL.fullmatch(texts[1]) or not texts[2].isdigit():
            continue
        end = next((index for index in range(3, len(texts))
                    if texts[index] in FORMATS or texts[index] in ("INT", "UINT") and texts[index + 1:index + 2]
                    and texts[index + 1] in ("16", "32", "64")), None)
        if end is None:
            continue
        width = 1 if texts[end] in FORMATS else 2
        rest = line[end + width:]
        rows.append({
            "modicom": texts[0], "physical": texts[1], "length": int(texts[2]), "label": " ".join(texts[3:end]),
            "format": "".join(texts[end:end + width]), "y": line[end][1], "notes_x": rest[0][0] if rest else None,
            "label_x": line[3][0] if end > 3 else None, "format_x": line[end][0],
        })
    return rows


def assign_notes(rows, notes):
    """Give each row the Notes text that its cell shows, where the geometry settles it.

    Rows are visited top to bottom. A line on the row's baseline is that row's. Lines centred on a
    single row are that row's multi-line cell. One "Value weight" line centred on several rows is a
    cell that spans them: only that line may lie between their baselines.
    """
    index = 0
    while index < len(rows):
        row = rows[index]
        own = [text for y, text in notes if abs(y - row["y"]) <= OWN]
        require(len(own) <= 1, f"Carlo Gavazzi {row['modicom']}: two Notes lines on one baseline")
        if own:
            row["note"] = own[0]
            index += 1
            continue
        upper = rows[index - 1]["y"] + OWN if index else float("-inf")
        lower = rows[index + 1]["y"] - OWN if index + 1 < len(rows) else float("inf")
        block = [(y, text) for y, text in notes if upper < y < lower and abs(y - row["y"]) <= REACH]
        if len(block) > 1 and abs((block[0][0] + block[-1][0]) / 2 - row["y"]) <= CENTRE:
            row["note"] = " ".join(text for _, text in block)
            index += 1
            continue
        below = [(y, text) for y, text in notes if y > row["y"] + OWN]
        weight = WEIGHT.fullmatch(below[0][1]) if below else None
        if weight and not weight.group(3) and not below[0][1].startswith("("):
            centre = below[0][0]
            ends = [last for last in range(index + 1, len(rows))
                    if abs((row["y"] + rows[last]["y"]) / 2 - centre) <= CENTRE]
            if ends:
                last = ends[0]
                inside = [y for y, _ in notes if row["y"] - OWN <= y <= rows[last]["y"] + OWN]
                if inside == [centre]:
                    for covered in rows[index:last + 1]:
                        covered["note"] = below[0][1]
                    index = last + 1
                    continue
        index += 1


def cell(part, row, centred=False):
    """Text of the row's own Notes cell: evenly spaced lines from its baseline down, or centred on it."""
    rows, notes = part["rows"], part["notes"]
    index = next(position for position, candidate in enumerate(rows) if candidate is row)
    upper = rows[index - 1]["y"] + OWN if index else float("-inf")
    lower = rows[index + 1]["y"] - OWN if index + 1 < len(rows) else float("inf")
    lines = [(y, text) for y, text in notes if upper < y < lower and (centred or y >= row["y"] - OWN)]
    require(lines, f"Carlo Gavazzi {row['modicom']}: empty Notes cell")
    nearest = min(range(len(lines)), key=lambda position: abs(lines[position][0] - row["y"]))
    first = last = nearest
    while first > 0 and lines[first][0] - lines[first - 1][0] <= GAP:
        first -= 1
    while last + 1 < len(lines) and lines[last + 1][0] - lines[last][0] <= GAP:
        last += 1
    middle = (lines[first][0] + lines[last][0]) / 2 if centred else lines[first][0]
    require(abs(middle - row["y"]) <= (CENTRE if centred else OWN),
            f"Carlo Gavazzi {row['modicom']}: Notes cell is not aligned with its row")
    return " ".join(text for _, text in lines[first:last + 1])


def full_label(part, row):
    """The VARIABLE cell with the lines that continue it below the row's baseline, left-aligned with it."""
    rows = part["rows"]
    index = next(position for position, candidate in enumerate(rows) if candidate is row)
    lower = rows[index + 1]["y"] - OWN if index + 1 < len(rows) else float("inf")
    column = [word for word in part["words"] if row["label_x"] - BASE <= word[0] < row["format_x"] - BASE
              and row["y"] + OWN < word[1] < lower]
    label, previous = row["label"], row["y"]
    for y, line in word_lines(column, CENTRE):
        if y - previous > GAP or abs(line[0][0] - row["label_x"]) > BASE:
            break
        label, previous = f"{label} {' '.join(text for _, _, text in line)}", y
    return label


def read_tables(pages):
    """Table parts in document order: {page, table, caption, rows, notes, words}.

    A caption line starts with "MODBUS:" and carries the table number (on that line or the next).
    Rows above the first caption of a page continue the previous page's table.
    """
    parts = []
    table = caption = None
    for number, words in enumerate(pages, start=1):
        captions = sorted((word for word in words if word[2] == "MODBUS:"), key=lambda item: item[1])
        tops = [float("-inf"), *(word[1] - BASE for word in captions), float("inf")]
        for index, top in enumerate(tops[:-1]):
            inside = [word for word in words if top <= word[1] < tops[index + 1]]
            floor = float("-inf")
            if index:
                line = sorted(word for word in inside if abs(word[1] - captions[index - 1][1]) <= BASE)
                caption = " ".join(text for _, _, text in line)
                headers = [word[1] for word in inside if word[2] == "Modicom"]
                require(headers, f"Carlo Gavazzi page {number}: table caption without a header: {caption}")
                floor = min(headers) + BASE
                ids = [word for word in inside if TABLE_ID.fullmatch(word[2]) and word[1] < floor - 2 * BASE]
                require(len(ids) == 1, f"Carlo Gavazzi page {number}: table number of {caption!r} not found")
                table = ids[0][2]
                caption = flat(caption.replace("Table", "").replace(table, ""))
            rows = table_rows([word for word in inside if word[1] > floor])
            if not rows:
                continue
            require(table, f"Carlo Gavazzi page {number}: rows before any table caption")
            starts = [row["notes_x"] for row in rows if row["notes_x"] is not None]
            notes = text_lines([word for word in inside if starts and word[0] >= min(starts) - 1 and word[1] > floor],
                               CENTRE)
            assign_notes(rows, notes)
            for row in rows:
                row.update(page=number, table=table, caption=caption)
            parts.append({"page": number, "table": table, "rows": rows, "notes": notes, "words": inside})
    return parts


def find(parts, table, label, data_format="UINT16", length=1):
    """The single row with this label in this table, and the table part that holds it."""
    found = [(part, row) for part in parts if part["table"] == table for row in part["rows"]
             if row["label"] == label]
    require(len(found) == 1, f"Carlo Gavazzi table {table} / {label}: {len(found)} rows")
    part, row = found[0]
    require((row["format"], row["length"]) == (data_format, length),
            f"Carlo Gavazzi {label}: unexpected format {row['format']} / {row['length']}")
    address = int(row["physical"][:4], 16)
    require(modicon_reference(row["modicom"], "input_register") == address,
            f"Carlo Gavazzi {label}: Modicom and physical addresses disagree")
    return part, row, address


def source(row):
    return {"address": row["physical"], "page": row["page"], "reference": f"Table {row['table']}; {row['modicom']}"}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def enum_values(text, what):
    """Enumeration from a Notes cell of "Value=N: meaning" entries; a repeated meaning gets its value as suffix."""
    pairs = VALUE.findall(text)
    require(pairs and " ".join(f"Value={value}: {label}" for value, label in pairs) == text,
            f"Carlo Gavazzi {what}: unexpected Notes cell {text!r}")
    labels = [label for _, label in pairs]
    return [{"value": int(value), "name": slug(label) + (f"_{value}" if labels.count(label) > 1 else ""),
             "label": label} for value, label in pairs]


def coded(parts, table, label, point_id, values, ranges, **extra):
    """A UINT16 enumeration point; `values` builds the enumeration from the row's Notes cell."""
    part, row, address = find(parts, table, label)
    point = {"id": point_id, "address": address, "type": "u16", "enum": {"values": values(cell(part, row))},
             **extra, "aliases": [full_label(part, row)], "source": source(row)}
    isolate(row, address, ranges)
    return point


def isolate(row, address, ranges):
    require(row["caption"] in (READ_ONLY, ONE_WORD), f"Carlo Gavazzi {row['modicom']}: caption {row['caption']!r}")
    if row["caption"] == ONE_WORD:
        ranges.append({"table": "input_register", "start": address, "count": 1, "policy": "isolated",
                       "reason": "Vendor: read only with function 03 or 04, limited to a word at a time."})


def measurements(parts, spec, selector, overflow):
    points = []
    selected = dict(spec["rows"])
    if selector in AN_MODELS:
        selected["An"] = ("neutral_current", "INT32", "Ampere", False)
    for label, (point_id, data_format, weight_unit, sentinel) in selected.items():
        kind, length = TYPES[data_format]
        part, row, address = find(parts, spec["table"], label, data_format, length)
        require(row["caption"] == READ_ONLY, f"Carlo Gavazzi {label}: caption {row['caption']!r}")
        weight = WEIGHT.fullmatch(row.get("note", ""))
        require(weight and weight.group(1) == weight_unit, f"Carlo Gavazzi {label}: unexpected value weight")
        require(weight.group(3) == (AN_SCOPE if label == "An" else None),
                f"Carlo Gavazzi {label}: unexpected restriction {weight.group(3)!r}")
        factor = weight.group(2)
        require(re.fullmatch(r"10+", factor), f"Carlo Gavazzi {label}: weight {factor} is not a power of ten")
        point = {"id": point_id, "address": address, "type": kind}
        if kind == "i32":
            point["wordOrder"] = "little"
        point["conversion"] = {"exponent10": -(len(factor) - 1)}
        if UNITS[weight_unit]:
            point["unit"] = UNITS[weight_unit]
        elif weight_unit != "PF":
            point["description"] = f"Vendor unit: {weight_unit}"
        elif label != "PF":
            point["description"] = power_factor_sign(part, row)
        if sentinel and overflow:
            require(kind == "i32", f"Carlo Gavazzi {label}: the overflow value is stated for 32-bit variables")
            point["invalid"] = [0x7FFFFFFF]
        point["aliases"] = [label]
        point["source"] = source(row)
        points.append(point)
    return points


def power_factor_sign(part, row):
    """The sign convention that heads the Notes cell shared by the phase and system power factor rows.

    The cell spans PF L1, PF L2, PF L3 and the system row: its lines sit on the first three baselines
    and its "Value weight" on the last.
    """
    rows = part["rows"]
    index = next(position for position, candidate in enumerate(rows) if candidate is row)
    above = rows[max(index - 3, 0):index]
    require([entry["label"] for entry in above] == ["PF L1", "PF L2", "PF L3"] and all("note" in entry
            for entry in above), "Carlo Gavazzi power factor rows changed")
    sign = " ".join(entry["note"] for entry in above).rstrip(".")
    require(re.fullmatch(r"Negative values correspond to [^.]+, positive values? correspond to [^.]+", sign),
            f"Carlo Gavazzi power factor sign note changed: {sign!r}")
    return f"Vendor: {sign}."


def phase_sequence(parts, table):
    part, row, address = find(parts, table, "Phase sequence", "INT16", 1)
    text = cell(part, row, centred=True)
    match = re.fullmatch(r'(?:The )?[Vv]alue "?([-–]?\d)"? corresponds? to (L1-L3-L2) sequence, (?:the )?value '
                         r'"?(\d)"? corresponds? to (L1-L2-) ?(L3) sequence\b.*meaningful only in.*', text)
    require(match, f"Carlo Gavazzi phase sequence: unexpected Notes cell {text!r}")
    reverse, forward = int(match.group(1).replace("–", "-")), int(match.group(3))
    return {"id": "phase_sequence", "address": address, "type": "i16",
            "enum": {"values": [{"value": reverse, "name": slug(match.group(2)), "label": match.group(2)},
                                {"value": forward, "name": "l1_l2_l3", "label": "L1-L2-L3"}]},
            "description": "Meaningful only in a 3-phase system.", "aliases": ["Phase sequence"],
            "source": source(row)}


def version_codes(parts, table, ranges):
    points = []
    for label, point_id, start in (("Version code", "firmware_version_code", 'Value=0: Version "A"'),
                                   ("Revision code", "firmware_revision_code", "Value=0: Revision")):
        part, row, address = find(parts, table, label)
        note = cell(part, row)
        require(note.startswith(start), f"Carlo Gavazzi {label}: unexpected Notes cell {note!r}")
        points.append({"id": point_id, "address": address, "type": "u16", "description": f"Vendor: {note}",
                       "stability": "constant", "aliases": [label], "source": source(row)})
        isolate(row, address, ranges)
    return points


def digital_inputs(parts, table, text, ranges):
    part, row, address = find(parts, table, "Digital input status")
    note = cell(part, row)
    bits = re.findall(r"bit(\d)=input status (Ch\d)", note)
    require(bits and " ".join(f"bit{bit}=input status {channel}" for bit, channel in bits) == note,
            f"Carlo Gavazzi digital input status: unexpected Notes cell {note!r}")
    require("bit=0 input close" in text and "bit=1 input open" in text,
            "Carlo Gavazzi digital input status: polarity statement missing")
    isolate(row, address, ranges)
    return {"id": "digital_input_status", "address": address, "type": "u16",
            "flags": {"flags": [{"bit": int(bit), "name": f"{channel.lower()}_open",
                                 "label": f"input status {channel}",
                                 "description": "bit=0 input close, bit=1 input open"} for bit, channel in bits]},
            "aliases": ["Digital input status"], "source": source(row)}


def packed_version(parts, table, ranges):
    """EM24-IS: major and minor in the nibbles of the high byte, revision in the low byte."""
    part, row, address = find(parts, table, "Version and revision code")
    note = cell(part, row)
    match = re.fullmatch(r"Data format: MSB: Bit (\d)\.\.(\d) = Minor Bit (\d)\.\.(\d) = Major "
                         r"\(e\.g\. ([01]{8})b / ([0-9A-F]{2})h / (\d+)d = (\d)\.(\d)\) LSB: Revision", note)
    require(match, f"Carlo Gavazzi version and revision code: unexpected Notes cell {note!r}")
    minor_low, minor_high, major_low, major_high = (int(match.group(index)) for index in range(1, 5))
    example = int(match.group(5), 2)
    require(example == int(match.group(6), 16) == int(match.group(7)), "Carlo Gavazzi version example disagrees")
    masks = {"firmware_major": ((1 << (major_high - major_low + 1)) - 1) << major_low,
             "firmware_minor": ((1 << (minor_high - minor_low + 1)) - 1) << minor_low}
    require(((example & masks["firmware_major"]) >> major_low, (example & masks["firmware_minor"]) >> minor_low)
            == (int(match.group(8)), int(match.group(9))), "Carlo Gavazzi version example does not decode")
    isolate(row, address, ranges)
    layout = {"firmware_major": masks["firmware_major"] << 8, "firmware_minor": masks["firmware_minor"] << 8,
              "firmware_revision": 0x00FF}
    return [{"id": point_id, "address": address, "type": "u16", "mask": mask, "stability": "constant",
             "aliases": ["Version and revision code"], "source": source(row)} for point_id, mask in layout.items()]


def item_codes(part):
    """(complete item number, identification code) pairs of the EM300/ET300 item table."""
    lines = text_lines(part["words"], BASE)
    start = [index for index, (_, text) in enumerate(lines)
             if text == "Complete item number CG identification code"]
    require(len(start) == 1, "Carlo Gavazzi item table header missing")
    items, pending = [], ""
    for _, text in lines[start[0] + 1:]:
        if not pending and not ITEM.fullmatch(text):
            break
        code = re.fullmatch(r"(.+) (\d{3})", text)
        if code:
            items.append((f"{pending} {code.group(1)}".strip(), int(code.group(2))))
            pending = ""
        else:
            # The item of the engineering sample takes two lines; the code is on the second.
            require(not pending, f"Carlo Gavazzi item table: no code for {pending!r}")
            pending = text
    require(items and not pending, "Carlo Gavazzi item table is empty or cut off")
    return items


def item_enum(part, model):
    values = {}
    for item, code in item_codes(part):
        match = ITEM.fullmatch(item)
        require(match, f"Carlo Gavazzi item table: unexpected item {item!r}")
        if match.group(1) != model:
            continue
        sample = "ENGINEERING SAMPLE ONLY (with MSW-LSW word order)" in item
        name = slug(f"{model} {match.group(2)}") + ("_engineering_sample" if sample else "")
        label = f"{model}-DIN {match.group(2)}" + (" engineering sample" if sample else "")
        entry = values.setdefault(code, {"value": code, "name": name, "label": label, "description": []})
        require(entry["name"] == name, f"Carlo Gavazzi item table: code {code} names two kinds of item")
        entry["description"].append(item)
    require(values, f"Carlo Gavazzi item table: no {model} items")
    return [{**entry, "description": "; ".join(entry["description"])} for entry in values.values()]


def read_limit(text):
    """The request limit when the prose and the frame tables give the same number, else None."""
    prose = set(re.findall(r"possible to read maximum (\d+) registers? \(words?\) with a single request", text))
    frames = set(re.findall(r"Quantity of registers \(N word\) 2 bytes 1 to [0-9A-F]+h \(1 to (\d+)\)", text))
    require(len(prose) == 1 and len(frames) == 1, "Carlo Gavazzi read limit statements changed")
    return int(prose.pop()) if prose == frames else None


def extract(data, selector):
    require(selector in SELECTORS, f"Unknown Carlo Gavazzi selector {selector!r}")
    family, scope = SELECTORS[selector]
    spec = FAMILIES[family]
    layout = pdf_pages(data, 1, pdf_page_count(data))
    text = flat("\n".join(layout))
    cover = flat(layout[0])
    for fragment in spec["title"]:
        require(fragment in cover, f"Carlo Gavazzi document title lacks {fragment!r}")
    require(scope in text, f"Carlo Gavazzi document does not name the {selector} as expected")
    for statement in (
        '"Physical address": it is the "word address" value to be included in the communication frame',
        "The functions 03h and 04h have exactly the same effect and can be used indifferently.",
        "For all the formats the byte order (inside the single word) is MSB->LSB. In INT32, UINT32 and UINT64 "
        "formats, the word order is LSW-> MSW.",
        spec["overflow"],
    ):
        require(statement in text, f"Carlo Gavazzi statement missing: {statement[:60]}")
    parts = read_tables(page_words(data))
    ranges = []
    points = measurements(parts, spec, selector, spec["overflow"] == FULL_OVERFLOW)
    if family != "em100":
        points.append(phase_sequence(parts, spec["table"]))
    if "firmware" in spec:
        points += version_codes(parts, spec["firmware"], ranges)

    if family == "em210":
        require("new variables available only from FW revision A.5" in text
                and "added THD variables, (calculated) neutral current" in text,
                "Carlo Gavazzi EM210 firmware note for the neutral current missing")
        neutral = next(point for point in points if point["id"] == "neutral_current")
        neutral["description"] = "Calculated. Available from firmware revision A.5."
        points.append(coded(parts, "2.6-1", "Programming lock (trimmer", "programming_lock",
                            lambda note: enum_values(note, "programming lock"), ranges))
        require("*For special version see ID table." in text, "Carlo Gavazzi EM210 identification footnote missing")

        def standard(note):
            match = re.fullmatch(r"Value=(\d+)\*: (EM210 standard)", note)
            require(match, f"Carlo Gavazzi EM210 identification code: unexpected Notes cell {note!r}")
            return [{"value": int(match.group(1)), "name": slug(match.group(2)), "label": match.group(2)}]
        points.append(coded(parts, "2.7-1", "Carlo Gavazzi Controls", "identification_code", standard, ranges,
                            description="Special versions use other codes (vendor ID table).",
                            stability="constant"))
    elif family in ("em24-din", "em24-is"):
        points.append(digital_inputs(parts, "2.4-1", text, ranges))
        points.append(coded(parts, "2.7-1", "Front selector status", "front_selector_status",
                            lambda note: enum_values(note, "front selector status"), ranges))
        if family == "em24-din":
            points.append(coded(parts, "2.5-1", "Current tariff", "current_tariff",
                                lambda note: enum_values(note, "current tariff"), ranges))

            def inputs(note):
                pairs = re.findall(r"Value=(\d+): EM24-DIN (AV\d) input product code", note)
                require(pairs and " ".join(f"Value={value}: EM24-DIN {option} input product code"
                                           for value, option in pairs) == note,
                        f"Carlo Gavazzi EM24-DIN identification code: unexpected Notes cell {note!r}")
                options = {}
                for value, option in pairs:
                    options.setdefault(int(value), []).append(option)
                return [{"value": value, "name": slug(" ".join(names)) + "_input",
                         "label": f"EM24-DIN {', '.join(names)} input"} for value, names in options.items()]
        else:
            points += packed_version(parts, "2.6-1", ranges)

            def inputs(note):
                values = enum_values(note, "EM24-IS identification code")
                require(all(re.fullmatch(r"EM24DINAV\d3XISSF[AB]", value["label"]) for value in values),
                        f"Carlo Gavazzi EM24-IS identification code: unexpected Notes cell {note!r}")
                return values
        points.append(coded(parts, "2.8-1", "Carlo Gavazzi Controls", "identification_code", inputs, ranges,
                            stability="constant"))
    elif family == "em300":
        model = selector.upper()
        part, row, address = find(parts, "2.8-1", "Carlo Gavazzi Controls")
        require(cell(part, row) == "See table 2.8-2", "Carlo Gavazzi EM300 identification row changed")
        points.append({"id": "identification_code", "address": address, "type": "u16",
                       "enum": {"values": item_enum(part, model)}, "stability": "constant",
                       "aliases": [full_label(part, row)], "source": source(row)})
        isolate(row, address, ranges)

    points.sort(key=lambda point: (point["address"], -point.get("mask", 0)))
    constraints = {}
    limit = read_limit(text)
    if limit:
        constraints["maxReadRegisters"] = limit
    if ranges:
        constraints["ranges"] = sorted(ranges, key=lambda item: item["start"])
    return {"points": points, "constraints": constraints} if constraints else {"points": points}
