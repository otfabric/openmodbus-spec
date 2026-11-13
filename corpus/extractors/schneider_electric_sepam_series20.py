"""Schneider Electric Sepam series 20 user's manual (PDF), Modbus chapter.

The selector is the application, "s20", "t20" or "m20". Word addresses in the tables are
hexadecimal PDU addresses: the test-zone frames read the table address 0C00 as 0C00 on the
wire. Format 16 NS is an unsigned 16-bit word with b0 the least significant bit, 16 S is
two's complement, and the format B example puts TS1 in bit 0 of word 0101. Applicability per
application comes from the application columns of the selection table and of the remote
annunciation (TS) tables. Those columns only line up by position on the page, so they are
read from word boxes ("pdftotext -bbox"), which sourcelib does not provide.
"""
from decimal import Decimal
from html import unescape
import re
import subprocess

from sourcelib import CorpusError, pdf_page_count, pdf_pages, require

MODELS = {"s20": "S20", "t20": "T20", "m20": "M20"}
COLUMNS = {"S20", "S24", "T20", "T24", "M20", "B21", "B22"}
STATUS_WORDS = (1, 17, 33, 49)

# Measurement zone row -> (point id, selection-table row that states its applicability)
PHASE = "Phase current I1, I2, I3 RMS, residual current I0"
TRIP = "Tripping current TripI1, TripI2, TripI3, TripI0"
MEASUREMENTS = {
    "I1 phase current (gain x 1)": ("current_a", PHASE),
    "I2 phase current (gain x 1)": ("current_b", PHASE),
    "I3 phase current (gain x 1)": ("current_c", PHASE),
    "I0 residual current (gain x 1)": ("residual_current", PHASE),
    "Itrip1 tripping current": ("trip_current_1", TRIP),
    "Itrip2 tripping current": ("trip_current_2", TRIP),
    "Itrip3 tripping current": ("trip_current_3", TRIP),
    "Itrip0 tripping current": ("trip_current_0", TRIP),
    "Cumulative breaking current": ("cumulative_breaking_current", "Cumulative breaking current"),
    "Number of operations": ("number_of_operations", "Number of operations, operating time, charging time"),
    "Running hours counter": ("running_hours", "Running hours counter/operating time"),
    "Thermal capacity used": ("thermal_capacity_used", "Thermal capacity used"),
    "Operating time before overload tripping": ("time_before_overload_trip",
                                                "Remaining operating time before overload tripping"),
    "Starting time / overload": ("starting_time", "Starting current and time"),
    "Starting current overload": ("starting_current", "Starting current and time"),
    "Temperatures 1 to 8": ("temperatures", "Temperature"),
}
UNITS = {"A": "A", "(kA)2": "kA2", "": None, "hr": "h", "%": "%", "min": "min", "sec": "s", "°C": "Cel"}
FORMATS = {"16NS": "u16", "16S": "i16"}

# Sepam check-word (format X): bit -> (flag name, label as printed)
CHECK_WORD = {
    4: ("tripping_by_protection", "remote indication of tripping by protection function"),
    6: ("setting_group_b", "setting group B in service"),
    7: ("setting_group_a", "setting group A in service"),
    8: ("partial_fault", "partial fault in Sepam"),
    9: ("major_fault", "major fault in Sepam"),
    10: ("local_setting_mode", "Sepam in local setting mode"),
    11: ("slan_monitoring_active", "S-LAN communication monitoring active"),
    12: ("time_not_correct", "Sepam time not correct"),
    13: ("not_synchronous", "Sepam not synchronous"),
    14: ("data_loss", "Sepam in “data loss” status"),
    15: ("event_present", "event present"),
}

WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
PAGE = re.compile(r"<page [^>]*>(.*?)</page>", re.DOTALL)
STATUS_ROW = re.compile(r"^(Sepam check-word|TS(\d+)-TS(\d+))\s{2,}([0-9A-F]{3})\s+([0-9A-F]{4})\s+R\s+.*\s(X|B)$")
MEASURE_ROW = re.compile(r"^(\S(?:\S| (?=\S))*)\s{2,}(\S+)\s+R\s+3/4\s+(16NS|16S|-)\s+(\S.*?)$")
TS_HEADING = re.compile(r"Address word (0[0-9A-F]{3}): TS(\d+) to TS(\d+) \(bit address ([0-9A-F]{3})0 to \4F\)")
CHECK_BIT = re.compile(r"\bb bit (\d+)(?:-(\d+))?\s+(.+?)(?= b bit | Other bits reserved)")
LINE = 3.0  # word boxes whose tops are this close share a line
ALIGN = 3.0  # a mark belongs to the column whose header starts this close to it


def pdf_words(data, page):
    """Word boxes (x0, y0, x1, y1, text) of one PDF page."""
    command = ["pdftotext", "-f", str(page), "-l", str(page), "-bbox", "-enc", "UTF-8", "-", "-"]
    result = subprocess.run(command, input=data, capture_output=True, check=True, timeout=120)
    pages = PAGE.findall(result.stdout.decode("utf-8"))
    require(len(pages) == 1, f"Sepam PDF page {page}: got {len(pages)} pages")
    return [(float(x0), float(y0), float(x1), float(y1), unescape(text))
            for x0, y0, x1, y1, text in WORD.findall(pages[0])]


def lines_of(words):
    """Word boxes grouped into lines, top to bottom, each line left to right."""
    lines = []
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        if lines and abs(word[1] - lines[-1][0]) <= LINE:
            lines[-1][1].append(word)
        else:
            lines.append((word[1], [word]))
    return [(y, sorted(line, key=lambda w: w[0])) for y, line in lines]


def header_columns(line):
    """{application: xMin} from a header line that names every application column."""
    columns = {}
    for word in line:
        name = re.fullmatch(r"(S20|S24|T20|T24|M20|B21|B22)(?:\(\d\))?", word[4])
        if name:
            require(name.group(1) not in columns, f"Sepam: column {name.group(1)} twice in a header")
            columns[name.group(1)] = word[0]
    require(set(columns) == COLUMNS, f"Sepam: header columns {sorted(columns)}")
    return columns


def marks(line, columns):
    """{application: mark} for the b/v marks of one line, matched to a column by xMin."""
    found = {}
    for word in line:
        if word[2] < min(columns.values()) - ALIGN:
            continue
        if re.fullmatch(r"\(\d\)|\d", word[4]):
            continue  # footnote calls and function counts
        if word[4] not in ("b", "v"):
            raise CorpusError(f"Sepam: unexpected word {word[4]!r} in the application columns")
        near = [name for name, x in columns.items() if abs(word[0] - x) <= ALIGN]
        require(len(near) == 1, f"Sepam: mark at x={word[0]:.1f} matches columns {near}")
        require(near[0] not in found, f"Sepam: two marks in column {near[0]}")
        found[near[0]] = word[4]
    return found


def selection_table(data, pages):
    """({row label: {application: mark}}, page) from the selection table."""
    numbers = [n for n, page in enumerate(pages, start=1)
               if "Selection table" in page and re.search(r"Protections\s+ANSI code\s+S20", page)]
    require(len(numbers) == 1, f"Sepam: selection table found on {len(numbers)} pages")
    lines = lines_of(pdf_words(data, numbers[0]))
    headers = [(y, line) for y, line in lines
               if any(word[4] == "ANSI" for word in line) and any(word[4] == "S20" for word in line)]
    require(len(headers) == 1, "Sepam: selection table header not found once")
    top, header = headers[0]
    columns = header_columns(header)
    left = min(columns.values()) - ALIGN
    rows = {}
    for y, line in lines:
        if y <= top + LINE:
            continue
        if line[0][4] == "b" and line[0][2] < left:
            break  # the legend "b Standard, v according to parameter setting ..." ends the table
        label = " ".join(word[4] for word in line if word[2] < left)
        found = marks(line, columns)
        if label and found:
            require(label not in rows, f"Sepam: selection row {label!r} twice")
            rows[label] = found
    return rows, numbers[0]


def ts_tables(data, pages):
    """TS rows {number: (label, {application: mark}, page)} and the check-word bit 4 row."""
    numbers = [n for n, page in enumerate(pages, start=1) if TS_HEADING.search(page)]
    require(numbers, "Sepam: remote annunciation tables not found")
    entries = {}
    check_bit = None
    for number in numbers:
        columns = None
        row = None
        for y, line in lines_of(pdf_words(data, number)):
            texts = [word[4] for word in line]
            if "Use" in texts and "S20" in texts:
                columns = header_columns(line)
                use = next(word[0] for word in line if word[4] == "Use")
                ts_x = next((word[0] for word in line if word[4] == "TS"), None)
                row = None
                continue
            if columns is None:
                continue
            left = min(columns.values()) - ALIGN
            label_words = [word for word in line if word[2] < left]
            first = line[0]
            if ts_x is not None and re.fullmatch(r"\d{1,2}", first[4]) and abs(first[0] - ts_x) <= 6 \
                    and len(label_words) > 1:
                ts = int(first[4])
                require(ts not in entries, f"Sepam: TS{ts} listed twice")
                row = [" ".join(word[4] for word in label_words[1:]), marks(line, columns), number, y]
                entries[ts] = row
            elif texts[:2] == ["Bit", "4"] and ts_x is None:
                require(check_bit is None, "Sepam: check-word bit 4 row twice")
                check_bit = (" ".join(word[4] for word in label_words[2:]), marks(line, columns), number)
                row = None
            elif row and label_words and len(label_words) == len(line) and abs(label_words[0][0] - use) <= 6 \
                    and y - row[3] < 14:
                row[0] += " " + " ".join(word[4] for word in label_words)  # wrapped label
                row[3] = y
            else:
                row = None
    require(sorted(entries) == list(range(1, 65)), f"Sepam: TS rows {sorted(entries)} are not TS1 to TS64")
    require(check_bit is not None, "Sepam: check-word bit 4 applicability row missing")
    return {ts: (label, found, page) for ts, (label, found, page, _) in entries.items()}, check_bit


def slug(label):
    text = re.sub(r"\s*\(\d\)$", "", label).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def evidence(flat):
    require("Sepam series 20 User’s manual" in flat and "PCRED301005EN/14" in flat,
            "Sepam: title or document reference PCRED301005EN/14 missing")
    require(re.search(r"Test zone 0C00 0C0F", flat) and "Transmission 01 03 0C00 0001 875A" in flat,
            "Sepam: test-zone frame example missing")
    require("The address of bit i (0 y i y F) of address word J is then (J x 16) + i." in flat,
            "Sepam: bit address rule missing")
    require(re.search(r"Format 16 NS All information is encoded in a 16-bit word, in absolute value \(unsigned\), "
                      r"binary format\. The zero bit \(b0\) is the least significant bit in the word\.", flat)
            and "The information is encoded in a 16-bit word as a complement of 2." in flat,
            "Sepam: 16 NS / 16 S format statements missing")
    require(re.search(r"Examples F E D C B A 9 8 7 6 5 4 3 2 1 0", flat) and
            re.search(r"TS1 to Word address 0101 TS16 " + " ".join(str(n) for n in range(16, 0, -1)) +
                      r" Bit address 101x", flat),
            "Sepam: format B example (TS1 = bit 0 of word 0101) missing")


def zones(pages):
    """Status rows {"check" or first TS: (word, bit address, format, page)} and measurement rows."""
    status = {}
    measured = {}
    zone = None
    for number, page in enumerate(pages, start=1):
        for line in page.splitlines():
            text = line.strip()
            if text == "Measurement zone":
                zone = "pending"
            elif zone == "pending" and text:
                require(re.fullmatch(r"\(.* types\)", text), f"Sepam: measurement zone scope {text!r}")
                zone = text
            row = STATUS_ROW.match(text)
            if row:
                key = "check" if row.group(1) == "Sepam check-word" else int(row.group(2))
                require(key not in status, f"Sepam: status row {row.group(1)} twice")
                status[key] = (int(row.group(4), 16), int(row.group(5), 16), row.group(6), number)
            row = MEASURE_ROW.match(text)
            if row and row.group(1) in MEASUREMENTS:
                require(zone not in (None, "pending"), f"Sepam: {row.group(1)} outside a measurement zone")
                require(row.group(1) not in measured, f"Sepam: measurement {row.group(1)!r} twice")
                measured[row.group(1)] = (row.groups()[1:], number, zone)
    require(set(measured) == set(MEASUREMENTS), f"Sepam: measurements missing {set(MEASUREMENTS) - set(measured)}")
    require(set(status) == {"check", *STATUS_WORDS}, f"Sepam: status rows {sorted(status, key=str)}")
    return status, measured


def check_word(pages, status):
    numbers = [n for n, page in enumerate(pages, start=1) if "Format X: Sepam check-word" in page]
    require(len(numbers) == 1, "Sepam: format X section not found once")
    section = re.sub(r"\s+", " ", pages[numbers[0] - 1].split("Format X: Sepam check-word", 1)[1])
    bits = {int(match.group(1)): match.group(3).strip() for match in CHECK_BIT.finditer(section)
            if match.group(2) is None}
    require(bits == {bit: label for bit, (_, label) in CHECK_WORD.items()}, f"Sepam: check-word bits {bits}")
    require(re.search(r"\bb bit 3-0 mapping number", section), "Sepam: check-word mapping number bits missing")
    address, bit_address, fmt, _ = status["check"]
    require(fmt == "X" and bit_address == address * 16, "Sepam: check-word status row")
    return {
        "id": "check_word",
        "address": address,
        "type": "u16",
        "flags": {"flags": [{"bit": bit, "name": name, "label": label}
                            for bit, (name, label) in sorted(CHECK_WORD.items())]},
        "aliases": ["Sepam check-word"],
        "description": "Format X. Bits 3-0 carry the mapping number and the other bits are reserved "
                       "(undetermined values). Changes of bits 6, 7, 8, 10, 12, 13 and 14 are time-tagged events.",
        "source": {"address": f"{address:04X}", "page": numbers[0], "reference": "Format X: Sepam check-word"},
    }


def measurement(label, row, number, zone, model, selection):
    point_id, applicability = MEASUREMENTS[label]
    raw_address, fmt, raw_unit = row
    require(re.search(rf"\b{model}\b", zone), f"Sepam {model}: measurement zone is {zone}")
    require(applicability in selection, f"Sepam: selection row {applicability!r} missing")
    mark = selection[applicability].get(model)
    require(mark in ("b", "v"), f"Sepam {model}: {label} is not available ({mark!r})")
    span = re.fullmatch(r"([0-9A-F]{3})(?:/([0-9A-F]{3}))?", raw_address)
    require(span, f"Sepam: {label} address {raw_address!r}")
    count = int(span.group(2), 16) - int(span.group(1), 16) + 1 if span.group(2) else 1
    numbered = re.search(r" 1 to (\d+)$", label)
    require(count == (int(numbered.group(1)) if numbered else 1), f"Sepam: {label} spans {count} words")
    require(fmt in FORMATS, f"Sepam: {label} format {fmt!r}")
    unit_match = re.fullmatch(r"(?:(\d+(?:\.\d+)?)\s*)?(.*)", raw_unit)
    scale, unit_text = Decimal(unit_match.group(1) or "1"), unit_match.group(2)
    require(unit_text in UNITS, f"Sepam: {label} unit {raw_unit!r}")
    exponent = scale.log10()
    require(exponent == exponent.to_integral_value(), f"Sepam: {label} step {scale} is not 10^n")
    point = {"id": point_id, "address": int(span.group(1), 16), "type": FORMATS[fmt]}
    if count > 1:
        point["count"] = count
    if int(exponent):
        point["conversion"] = {"exponent10": int(exponent)}
    if UNITS[unit_text]:
        point["unit"] = UNITS[unit_text]
    point["aliases"] = [label]
    if mark == "v":
        point["description"] = ("The selection table marks this value v: according to parameter setting and "
                                "the input/output module options.")
    point["source"] = {"address": raw_address, "page": number, "reference": "Measurement zone"}
    return point


def extract(data, selector):
    require(selector in MODELS, f"Unknown Sepam selector {selector!r}")
    model = MODELS[selector]
    pages = pdf_pages(data, 1, pdf_page_count(data))
    flat = re.sub(r"\s+", " ", "\n".join(pages))
    evidence(flat)
    status, measured = zones(pages)
    selection, _ = selection_table(data, pages)
    ts, (check_label, check_marks, _) = ts_tables(data, pages)
    require(check_label == "Tripping by protection function" and check_marks.get(model) == "b",
            f"Sepam {model}: check-word bit 4 is not marked for this application")
    headings = {int(match.group(2)): (int(match.group(1), 16), int(match.group(3)), int(match.group(4), 16))
                for match in TS_HEADING.finditer(flat)}

    points = [check_word(pages, status)]
    for first in STATUS_WORDS:
        address, bit_address, fmt, _ = status[first]
        require(fmt == "B" and bit_address == address * 16, f"Sepam: TS{first} status row")
        require(headings.get(first) == (address, first + 15, address),
                f"Sepam: TS{first} table heading does not match word {address:04X}")
        flags = []
        for number in range(first, first + 16):
            label, found, _ = ts[number]
            require(found.get(model) in (None, "b"), f"Sepam: TS{number} has mark {found.get(model)!r}")
            if found.get(model) == "b":
                flags.append({"bit": number - first, "name": slug(label), "label": f"TS{number} {label}"})
        if not flags:
            continue
        names = [flag["name"] for flag in flags]
        require(len(names) == len(set(names)), f"Sepam: TS{first} flag names repeat")
        points.append({
            "id": f"annunciation_ts{first}_ts{first + 15}",
            "address": address,
            "type": "u16",
            "flags": {"flags": flags},
            "aliases": [f"TS{first}-TS{first + 15}"],
            "description": "Remote annunciation bits pre-assigned to protection and control functions; only the "
                           f"TS marked for {model} are listed. Each TS transition is time-tagged in the event stack.",
            "source": {"address": f"{address:04X}", "page": ts[first][2],
                       "reference": f"Address word {address:04X}: TS{first} to TS{first + 15}"},
        })

    previous = None
    for label in MEASUREMENTS:
        row, number, zone = measured[label]
        applicability = MEASUREMENTS[label][1]
        require(applicability in selection, f"Sepam: selection row {applicability!r} missing")
        if model not in selection[applicability]:
            continue  # not available for this application: the zone then reads zero
        point = measurement(label, row, number, zone, model, selection)
        require(previous is None or point["address"] > previous, f"Sepam: {label} address out of table order")
        previous = point["address"]
        points.append(point)
    return sorted(points, key=lambda point: point["address"])
