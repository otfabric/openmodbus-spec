"""Schneider Electric iEM3000 and PM3200 series user manuals (PDF): 16-bit setup and status registers.

The selector is the model as the manual names it ("iEM3155", "PM3250"). Both manuals print the
Modbus register list as tables with an "Address" column (hexadecimal, "the data used in the Modbus
frame") and a "Register" column (decimal, "register = address + 1"). The extractor requires both
statements, "use function 3 (Read)" for reading and the sentence or chapter title that names the
Modbus models, and it requires address + 1 = register on every row it maps. A row applies to a
model by its action column (PM3200), or by the model list in the section heading and the row's
"Not applicable for ..." note (iEM3000).

Neither manual states the register order of its Float32, UInt32 and Int64 values or how UTF8
characters are packed into registers, so only single-register UInt16 and Bitmap rows are mapped.
The measurements and energies, which are all Float32 or Int64, are left out.

A table cell holds several lines and the row's address is centred on them, which a text layout
does not show. Rows are therefore read from word boxes ("pdftotext -bbox", which sourcelib does
not provide): the description lines of a row are the run of lines whose middle is the row's
address. A cell that continues on the next page is joined to its row.
"""
from html import unescape
import re
import subprocess

from sourcelib import require

PAGE = re.compile(r"<page [^>]*>(.*?)</page>", re.DOTALL)
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
ANCHOR = re.compile(r"0x[0-9A-F]{3,4}")
ACTIONS = {"R", "R/W", "R/WC", "W", "—"}
TYPES = {"UInt16", "Int16", "UInt32", "Int64", "UTF8", "Float32", "Bitmap", "DATETIME"}
UNITS = {"—": None, "Hz": "Hz", "V": "V", "A": "A", "Millisecond": "ms", "Minute": "min"}
BODY = 8.0        # table text is 7.5 pt high; footers, captions and headings are larger
HEADING = 14.0    # section headings are 15 pt high
SAME_LINE = 2.2   # word tops on one line differ by up to 1.4 pt (the dash sits higher); see parse_region
HEADER_ROWS = 16.0   # "WC)" and the model names sit up to 14 pt below the header line; rows start 21 pt below
CAPTION = 36.0    # a table's caption sits up to 30 pt above its header line, the row before it 50 pt and more
MIRROR = 2.5      # a row's lines are centred on its address to within this many points
WRAP = 10.7       # a wrapped line follows 8.8 pt below, a new paragraph 12.8 pt or more
COLUMN_GAP = 3.0  # description text starts right of the "Units" heading

STATEMENTS = {
    "address": "Address: A 16-bit register address in hexadecimal. The address is the data used in the Modbus "
               "frame.",
    "register": "Register: A 16-bit register number in decimal (register = address + 1).",
    "read": "To read different parameters from the meter, use function 3 (Read).",
    "function": "3 0x03 Read Holding Registers",
}
CLOCK_FIELDS = {"Year": "clock_year", "Month": "clock_month", "Weekday": None, "Day": "clock_day",
                "Hour": "clock_hour", "Minute": "clock_minute", "Millisecond": None}
BAUD = {"9600": "baud_9600", "19200": "baud_19200", "38400": "baud_38400"}
PARITY = {"Even": "even", "Odd": "odd", "None": "none"}

# (section heading, row label): (point id, type, vendor unit, kind, names)
#   kind "plain": the raw value; "enum": "N = label" lines; "flags": "BitN = label" lines;
#   "clock": the four-register date and time row, one point per bit field.
IEM3000 = {
    ("System", "Present Firmware Version (DLF format): X.Y.ZTT"): ("firmware_version", "UInt16", "—", "plain", None),
    ("System", "Date/Time"): ("clock", "UInt16", "—", "clock", None),
    ("System", "Diagnostics error status"): ("diagnostics_error_status", "Bitmap", "—", "flags", "Code"),
    ("Meter Setup and Status", "Number of Phases"): ("number_of_phases", "UInt16", "—", "plain", None),
    ("Meter Setup and Status", "Power System"): ("power_system", "UInt16", "—", "enum", {
        "1PH2W L-N": "single_phase_2_wire_l_n", "1PH2W L-L": "single_phase_2_wire_l_l",
        "1PH3W L-L with N": "single_phase_3_wire_l_l_n", "3PH3W": "three_phase_3_wire",
        "3PH4W": "three_phase_4_wire", "1PH4W multi L with N": "single_phase_4_wire_multi_l_n"}),
    ("Meter Setup and Status", "Nominal Frequency"): ("nominal_frequency", "UInt16", "Hz", "plain", None),
    ("Meter Setup and Status", "VT Secondary"): ("vt_secondary", "UInt16", "V", "plain", None),
    ("Meter Setup and Status", "CT Primary"): ("ct_primary", "UInt16", "A", "plain", None),
    ("Meter Setup and Status", "CT Secondary"): ("ct_secondary", "UInt16", "A", "plain", None),
    ("Communication", "Address"): ("modbus_address", "UInt16", "—", "plain", None),
    ("Communication", "Baud Rate"): ("baud_rate", "UInt16", "—", "enum", BAUD),
    ("Communication", "Parity"): ("parity", "UInt16", "—", "enum", PARITY),
    ("Digital Input", "Digital Input Control Mode"): ("digital_input_control_mode", "UInt16", "—", "enum", {
        "Normal (Input Status)": "input_status", "Multi Tariff Control": "multi_tariff_control",
        "Input Metering": "input_metering", "All Energy Reset": "all_energy_reset"}),
    ("Digital Output", "Digital Output Control Mode Status"): (
        "digital_output_control_mode", "UInt16", "—", "enum", {
            "Alarm": "alarm", "Pulse (kWh)": "pulse_kwh", "Pulse (kVARh)": "pulse_kvarh", "Disable": "disabled"}),
    ("Meter Data", "Multi Tariffs Energy Active Rate"): ("active_tariff", "UInt16", "—", "plain", None),
    ("Overload Alarm", "Activated Status"): ("overload_alarm_status", "Bitmap", "—", "enum", {
        "Alarm is inactive": "inactive", "Alarm is active": "active"}),
}
PM3200 = {
    ("System", "Present Firmware Version (DLF format): X.Y.ZTT"): ("firmware_version", "UInt16", "—", "plain", None),
    ("System", "Present Language Version (DLF format): X.Y.ZTT"): ("language_version", "UInt16", "—", "plain", None),
    ("System", "Date/Time"): ("clock", "UInt16", "—", "clock", None),
    ("Energy Pulse Output Setup", "Energy Pulse Duration"): (
        "energy_pulse_duration", "UInt16", "Millisecond", "plain", None),
    ("Communications", "Address"): ("modbus_address", "UInt16", "—", "plain", None),
    ("Communications", "Baud Rate"): ("baud_rate", "UInt16", "—", "enum", BAUD),
    ("Communications", "Parity"): ("parity", "UInt16", "—", "enum", PARITY),
    ("Digital Inputs", "Digital Input 1 Control Mode"): ("digital_input_1_control_mode", "UInt16", "—", "enum", {
        "Normal (Input Status)": "input_status", "Multi-tariff Control": "multi_tariff_control",
        "Input Metering": "input_metering",
        "Energy Reset (Partial Energy, Energy by Tariff, Phase Energy)": "energy_reset"}),
    ("Digital Outputs", "Digital Output 1 Control Mode Status"): (
        "digital_output_1_control_mode", "UInt16", "—", "enum", {
            "Alarm": "alarm", "Energy": "energy", "Disable": "disabled"}),
    ("Basic Meter Data", "Active Tariff (Only modifiable in case of COM Control Mode Enabled)"): (
        "active_tariff", "UInt16", "—", "plain", None),
    ("Demand", "Demand Method"): ("demand_method", "UInt16", "—", "enum", {
        "Timed Interval Sliding Block": "sliding_block", "Timed Interval Fixed Block": "fixed_block"}),
    ("Demand", "Demand Interval Duration"): ("demand_interval", "UInt16", "Minute", "plain", None),
}
# identity: text of the title page and the page footers; scope: the sentence or chapter title that names the
# Modbus models; columns: the per-model action columns of the register tables, in order
DOCUMENTS = {
    "iem3000": {"identity": ("DOCA0005EN-16", "iEM3100 / iEM3200 / iEM3300 series"),
                "scope": r"Modbus RTU protocol is available on ((?:iEM\d{4} / )+iEM\d{4}) meter models\.",
                "columns": None, "models": ("iEM3155", "iEM3255", "iEM3355"), "rows": IEM3000},
    "pm3200": {"identity": ("DOCA0006EN-09", "PM3200 series"),
               "scope": r"Communication using Modbus \(((?:PM\d{4} / )+PM\d{4})\)",
               "columns": ("PM3250", "PM3255"), "models": ("PM3250", "PM3255"), "rows": PM3200},
}


def pages_of_words(data):
    """Per page, the words as (xMin, yMin, xMax, yMax, text)."""
    result = subprocess.run(["pdftotext", "-bbox", "-enc", "UTF-8", "-", "-"], input=data, capture_output=True,
                            check=True, timeout=180)
    pages = []
    for body in PAGE.findall(result.stdout.decode("utf-8")):
        pages.append([(float(x0), float(y0), float(x1), float(y1), unescape(text))
                      for x0, y0, x1, y1, text in WORD.findall(body) if unescape(text).strip()])
    require(pages, "Schneider manual: no pages")
    return pages


def lines_of(words):
    """Group words into lines by their top edge: [(y of the first word, [words left to right])], top to bottom."""
    lines, previous = [], None
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        if previous is not None and word[1] - previous <= SAME_LINE:
            lines[-1][1].append(word)
        else:
            lines.append((word[1], [word]))
        previous = word[1]
    return [(y, sorted(row)) for y, row in lines]


def text_of(words):
    return " ".join(word[4] for word in words)


def check_statements(pages, document, model):
    """The conventions the mapping depends on and the model scope, as running text of the manual."""
    running = " ".join(text_of(row) for words in pages for _, row in lines_of(words))
    for marker in document["identity"]:
        require(marker in running, f"Schneider manual: identity {marker!r} not found")
    for key, statement in STATEMENTS.items():
        require(statement in running, f"Schneider manual: statement {key!r} not found")
    scopes = {scope for scope in re.findall(document["scope"], running)}
    require(len(scopes) == 1, "Schneider manual: Modbus model scope not found once")
    require(model in scopes.pop().split(" / "), f"Schneider manual: {model} is not among the Modbus models")


def page_events(words):
    """One page as ("heading", text) and ("table", region) events from top to bottom."""
    marks = []
    for y, row in lines_of(words):
        texts = [word[4] for word in row]
        if max(word[3] - word[1] for word in row) >= HEADING:
            marks.append((y, "heading", text_of(row)))
        elif "Address" in texts and "Description" in texts and "Units" in texts:
            marks.append((y, "header", row))
    events = []
    for index, (y, kind, payload) in enumerate(marks):
        if kind == "heading":
            events.append(("heading", payload))
            continue
        end = float("inf")
        if index + 1 < len(marks):
            end = marks[index + 1][0] - (CAPTION if marks[index + 1][1] == "header" else 0)
        table = [word for word in words if word[3] - word[1] < BODY and y < word[1] < end]
        events.append(("table", {
            "header": payload, "top": y,
            "extra": [word for word in table if word[1] <= y + HEADER_ROWS],
            "words": [word for word in table if word[1] > y + HEADER_ROWS]}))
    return events


def parse_region(region, columns, where):
    """Rows of one table: the fixed cells of each address and the description lines centred on it.

    Returns (leading description lines, which continue the last row of the previous page, rows).
    """
    header = {word[4]: word for word in region["header"]}
    boundary = header["Units"][2] + COLUMN_GAP
    address_x = header["Address"][0]
    if columns:
        names = sorted(word for word in region["extra"] if word[4] in columns)
        require([word[4] for word in names] == list(columns), f"{where}: action columns are not {columns}")
    # Fixed cells and description text are grouped into lines separately: a note may start 2 pt below
    # the row's address line, while lines within either group are more than 4 pt apart.
    rows = []
    for y, left in lines_of([word for word in region["words"] if word[0] < boundary]):
        if ANCHOR.fullmatch(left[0][4]):
            rows.append({"cells": list(left)})
        elif left[0][0] >= address_x + 2 * BODY:
            # cells on a line of their own: the middle line of an address range, a wrapped unit
            require(rows, f"{where}: cells without an address at y={y:.0f}")
            rows[-1]["cells"] += left
        # anything else is a sub-heading row that spans the table
    description = lines_of([word for word in region["words"] if word[0] >= boundary])
    merged = []
    for row in rows:
        if merged and merged[-1].get("open"):
            merged[-1]["cells"] += row["cells"]
            merged[-1]["open"] = False
        else:
            row["open"] = "–" in [word[4] for word in row["cells"]]
            merged.append(row)
    for row in merged:
        require(not row["open"], f"{where}: address range without an end")
        tops = [word[1] for word in row["cells"] if ANCHOR.fullmatch(word[4])]
        row["centre"] = sum(tops) / len(tops)

    def assign(lead):
        index, spans = lead, []
        for row in merged:
            if index >= len(description) or description[index][0] > row["centre"] + MIRROR:
                return None
            target = 2 * row["centre"] - description[index][0]
            last = [i for i in range(index, len(description)) if abs(description[i][0] - target) <= MIRROR]
            if len(last) != 1:
                return None
            spans.append((index, last[0] + 1))
            index = last[0] + 1
        return spans if index == len(description) else None

    first_centre = merged[0]["centre"] if merged else float("inf")
    leads = [lead for lead in range(len(description) + 1)
             if all(y < first_centre for y, _ in description[:lead]) and assign(lead) is not None]
    require(len(leads) == 1, f"{where}: {len(leads)} ways to attach the description lines to the rows")
    for row, (start, end) in zip(merged, assign(leads[0])):
        row["lines"] = description[start:end]
    return description[:leads[0]], merged


def paragraphs(lines):
    """Join wrapped lines; a paragraph starts where the line gap is that of a new paragraph."""
    result, previous = [], None
    for y, words in lines:
        if previous is not None and y - previous < WRAP:
            result[-1] += " " + text_of(words)
        else:
            result.append(text_of(words))
        previous = y
    return result


def register_rows(pages, document):
    """Every row of the sections that hold selected rows: {(section, label): row}."""
    sections = {section for section, _ in document["rows"]}
    found, section, last_row, started, done = [], None, None, False, False
    for number, words in enumerate(pages, start=1):
        continued = True
        for kind, payload in page_events(words):
            if kind == "heading":
                if payload == "Modbus register list":
                    require(not started, "Schneider manual: two 'Modbus register list' headings")
                    started = True
                elif started and payload == "Read Device Identification":
                    done = True
                    break
                section, last_row, continued = payload, None, False
                continue
            if not started or section is None or section.split(" (")[0] not in sections:
                last_row, continued = None, False
                continue
            where = f"Schneider manual p.{number}, {section}"
            lead, rows = parse_region(payload, document["columns"], where)
            if lead:
                require(continued and last_row is not None, f"{where}: description lines without a row")
                last_row["lines"] = last_row["lines"] + [(y + 10000.0, line) for y, line in lead]
            for row in rows:
                row.update(page=number, section=section)
                last_row = row
                found.append(row)
            continued = False
        if done:
            break
    require(started and done, "Schneider manual: the Modbus register list was not found")
    labelled = {}
    for row in found:
        row["paragraphs"] = paragraphs(row["lines"])
        require(row["paragraphs"], f"Schneider manual p.{row['page']}: row without a description")
        key = (row["section"].split(" (")[0], row["paragraphs"][0].rstrip(":"))
        require(key not in labelled or key not in document["rows"], f"Schneider manual: two rows labelled {key}")
        labelled[key] = row
    return labelled


def fixed_cells(row, columns, ref):
    """(addresses, registers, actions, size, type, unit) of a row, each cell checked for its shape."""
    cells = [word[4] for word in sorted(row["cells"], key=lambda w: (w[0], w[1]))]
    addresses = [int(cell, 16) for cell in cells if ANCHOR.fullmatch(cell)]
    rest = [cell for cell in cells if not ANCHOR.fullmatch(cell) and cell != "–"]
    count = len(addresses)
    require(count in (1, 2) and len(rest) >= count and all(cell.isdigit() for cell in rest[:count]),
            f"{ref}: address and register cells not found")
    registers = [int(cell) for cell in rest[:count]]
    rest = rest[count:]
    width = len(columns) if columns else 1
    require(len(rest) == width + 3, f"{ref}: expected action, size, type and unit cells, got {rest}")
    actions, (size, kind, unit) = rest[:width], rest[width:]
    require(all(action in ACTIONS for action in actions) and kind in TYPES, f"{ref}: unexpected cells {rest}")
    return addresses, registers, actions, size, kind, unit


def applies(row, document, model, actions):
    """Whether the manual lists the row for the model: its action column, the section's model list, the notes."""
    if document["columns"]:
        return actions[document["columns"].index(model)] != "—"
    scope = re.search(r"\(([^)]*)\)$", row["section"])
    if scope and model not in [name.strip() for name in scope.group(1).split("/")]:
        return False
    for paragraph in row["paragraphs"]:
        note = re.fullmatch(r"NOTE: Not applicable for (.+)", paragraph)
        if note and model in [name.strip() for name in note.group(1).split("/")]:
            return False
    return True


def base_point(point_id, register, address, row, label):
    return {"id": point_id, "address": address, "type": "u16", "aliases": [label],
            "source": {"address": f"0x{address:04X} (register {register})", "page": row["page"],
                       "reference": f"Modbus register list, {row['section']}"}}


def clock_points(row, addresses, registers, ref):
    """One point per bit field of the date and time registers, e.g. 'Reg. 1846: Month (b11:b8), ...'."""
    require(len(addresses) == 2 and registers[1] - registers[0] == 3, f"{ref}: not a four-register range")
    points, seen = [], []
    for paragraph in row["paragraphs"][1:]:
        match = re.fullmatch(r"Reg\. (\d+): (.+)", paragraph)
        require(match, f"{ref}: unexpected line {paragraph!r}")
        register = int(match.group(1))
        require(registers[0] <= register <= registers[1], f"{ref}: register {register} outside the row")
        seen.append(register)
        fields = re.findall(r"([A-Z][a-z]+)(?: \(b(\d+):b(\d+)\))?", match.group(2).split(" 0 – ")[0])
        require(fields, f"{ref}: no fields in {paragraph!r}")
        for name, high, low in fields:
            require(name in CLOCK_FIELDS, f"{ref}: unknown field {name!r}")
            if CLOCK_FIELDS[name] is None:
                continue
            require(high and 15 >= int(high) >= int(low), f"{ref}: field {name} has no bit range")
            address = addresses[0] + register - registers[0]
            point = base_point(CLOCK_FIELDS[name], register, address, row, f"Date/Time: {name}")
            point["source"]["address"] = (f"0x{addresses[0]:04X} – 0x{addresses[1]:04X} "
                                          f"(registers {registers[0]} – {registers[1]}), Reg. {register}")
            point["mask"] = ((1 << (int(high) + 1)) - 1) & ~((1 << int(low)) - 1)
            if name == "Year":
                era = re.search(r"\(year from (\d{4}) to \d{4}\)", match.group(2))
                require(era, f"{ref}: year base not stated")
                point["conversion"] = {"offset": int(era.group(1))}
            point["source"]["reference"] += f", Date/Time, {name} (b{high}:b{low})"
            points.append(point)
    require(seen == list(range(registers[0], registers[1] + 1)), f"{ref}: registers {seen} do not fill the row")
    return points


def coded(row, kind, names, ref):
    """Parse 'N = label' (enum) or 'BitN = label' (flags) paragraphs of a row."""
    entries = []
    for paragraph in row["paragraphs"]:
        if paragraph.startswith("NOTE:"):
            continue
        if kind == "enum":
            match = re.fullmatch(r"(0x[0-9A-F]+|\d+) = (.+)", paragraph)
            if match:
                label = match.group(2)
                require(label in names, f"{ref}: unknown value label {label!r}")
                entries.append({"value": int(match.group(1), 0), "name": names[label], "label": label})
        else:
            match = re.fullmatch(r"Bit(\d+) = (.+)", paragraph)
            if match:
                label = match.group(2)
                require(re.fullmatch(rf"{names} \d+", label), f"{ref}: unknown flag label {label!r}")
                entries.append({"bit": int(match.group(1)), "name": label.lower().replace(" ", "_"),
                                "label": label})
    if kind == "enum":
        require(sorted(entry["label"] for entry in entries) == sorted(names),
                f"{ref}: values {[entry['label'] for entry in entries]} are not {sorted(names)}")
        return {"enum": {"values": entries}}
    require(entries and len({entry["bit"] for entry in entries}) == len(entries), f"{ref}: no flags")
    return {"flags": {"flags": entries}}


def extract(data, selector):
    matches = [document for document in DOCUMENTS.values() if selector in document["models"]]
    require(len(matches) == 1, f"Schneider manual: unknown model {selector!r}")
    document = matches[0]
    pages = pages_of_words(data)
    check_statements(pages, document, selector)
    rows = register_rows(pages, document)
    points = []
    for (section, label), (point_id, kind, vendor_unit, shape, names) in document["rows"].items():
        ref = f"Schneider manual, {section}, {label!r}"
        require((section, label) in rows, f"{ref}: row not found")
        row = rows[(section, label)]
        addresses, registers, actions, size, found_kind, unit = fixed_cells(row, document["columns"], ref)
        require(all(address + 1 == register for address, register in zip(addresses, registers)),
                f"{ref}: address {addresses} + 1 is not register {registers}")
        require(found_kind == kind and unit == vendor_unit, f"{ref}: type {found_kind} or unit {unit!r} unexpected")
        if not applies(row, document, selector, actions):
            continue
        action = actions[document["columns"].index(selector)] if document["columns"] else actions[0]
        require(action in ("R", "R/W", "R/WC"), f"{ref}: not readable")
        if shape == "clock":
            require(size == "1X4", f"{ref}: size {size!r} is not four single registers")
            points += clock_points(row, addresses, registers, ref)
            continue
        require(size == "1" and len(addresses) == 1, f"{ref}: not a single register")
        point = base_point(point_id, registers[0], addresses[0], row, label)
        if shape in ("enum", "flags"):
            point.update(coded(row, shape, names, ref))
        elif UNITS[vendor_unit]:
            point["unit"] = UNITS[vendor_unit]
        extra = [text for text in row["paragraphs"][1:] if not text.startswith("NOTE:")]
        if shape == "plain" and extra:
            point["description"] = "; ".join(extra)
        points.append(point)
    require(len(points) >= 6, f"Schneider manual: only {len(points)} points for {selector}")
    return sorted(points, key=lambda point: (point["address"], -point.get("mask", 0)))
