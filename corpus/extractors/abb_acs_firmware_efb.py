"""ABB ACS580, ACH580 and ACS880 firmware manuals (PDF): embedded fieldbus interface (EFB), Modbus RTU.

The selector is the drive: "acs580", "ach580" or "acs880". The ACS580 and ACH580 manuals share one
layout; the ACS880 manual has another. The ACH580 manual prints a thumb index in the page margins,
so its text is taken from the page body only (see body_pages). The points hold for the EFB defaults
that the manual documents and the extractor requires: 58.25 Control profile = ABB Drives, 58.33
Addressing mode = Mode 0, 58.34 Word order = LO-HI, and the default holding register table (status
word and actual value 1 in the fourth and fifth register).

Address base. Section "Register addressing" states that the address field of a request is 16 bits,
which addresses 65536 holding registers, and that the manual writes them as 6-digit numbers from
400001 to 465536. A range of exactly 2^16 numbers for a 16-bit address field puts 400001 at address
0. The set-up table agrees: it gives the top of the range, 465536, as 65535. Both are parsed.

Parameter registers. Parameter 58.33 gives, for Mode 0, register = 400000 + 100 x group + index for
16-bit values and 420000 + 200 x group + 2 x index for 32-bit values, each with a worked example
that is recomputed here. Parameter 58.34 gives the register order of 32-bit values (LO-HI: low
order word first) and the byte order inside a register (high order byte first).

Scaling. The 16-bit and 32-bit "fieldbus equivalents" (FbEq) come from the parameter tables. Many
16-bit scalings refer to another parameter (20000 = the value of 46.01); those are read as 32-bit
values, whose scaling is a plain power of ten.

Signs. The manuals state the integer type only for the fieldbus actual values ("signed integers")
and, in the ACS880 manual, per parameter (uint16, int16, real32 ...). They do not state how a
parameter with a negative range is encoded as a 16-bit or 32-bit integer. A parameter is therefore
mapped only when its type is stated or when its documented range starts at zero and, scaled, stays
below 2^15 or 2^31 (so signed and unsigned readings agree) or needs every bit (so it is unsigned).
"""
from bisect import bisect_right
from decimal import Decimal
import re
import subprocess

from sourcelib import CorpusError, pdf_page_count, pdf_pages, require

EFB = "Fieldbus control through the embedded fieldbus interface (EFB)"
MANUALS = {
    "acs580": {
        "identity": ("ACS580standardcontrolprogram", "3AXD50000016097RevJ"),
        "layout": "split",  # FbEq16 in chapter Parameters, FbEq32 in chapter Additional parameter data
        "status_names": {4: "OFF_2_STATUS", 5: "OFF_3_STATUS"},
        "registers16": {
            "01.18": ("inverter_energy_gwh", "Inverter GWh counter", "GWh", "GW.h"),
            "01.19": ("inverter_energy_mwh", "Inverter MWh counter", "MWh", "MW.h"),
            "01.20": ("inverter_energy_kwh", "Inverter kWh counter", "kWh", "kW.h"),
            "04.01": ("tripping_fault", "Tripping fault", "", None),
            "05.01": ("on_time_counter", "On-time counter", "days", "d"),
        },
        "registers32": {
            "01.07": ("motor_current", "Motor current", "A", "A"),
            "01.11": ("dc_voltage", "DC voltage", "V", "V"),
            "01.13": ("output_voltage", "Output voltage", "V", "V"),
            "01.61": ("abs_motor_speed", "Abs motor speed used", "rpm", "/min"),
            "01.63": ("abs_output_frequency", "Abs output frequency", "Hz", "Hz"),
            "01.64": ("abs_motor_torque", "Abs motor torque", "%", "%"),
            "01.65": ("abs_output_power", "Abs output power", "kW", None),
            "05.03": ("hours_run", "Hours run", "h", "h"),
            "46.01": ("speed_scaling", "Speed scaling", "rpm", "/min"),
            "46.02": ("frequency_scaling", "Frequency scaling", "Hz", "Hz"),
        },
        "drive_status": {0: "Enabled", 1: "Inhibited", 2: "DC charged", 3: "Ready to start",
                         4: "Following reference", 5: "Started", 6: "Modulating", 7: "Limiting",
                         8: "Local control", 9: "Network control", 10: "Ext1 active", 11: "Ext2 active",
                         13: "Start request", 14: "Running"},
    },
    "ach580": {
        "identity": ("ACH580HVACcontrolprogram", "3AXD50000027537RevJ"),
        "efb": "Modbus RTU control through the embedded fieldbus interface (EFB)",
        "layout": "split",
        "body": (23, 396),  # the outer page margins carry a thumb index of chapter numbers
        "registers16": {
            "01.18": ("inverter_energy_gwh", "Inverter GWh counter", "GWh", "GW.h"),
            "01.19": ("inverter_energy_mwh", "Inverter MWh counter", "MWh", "MW.h"),
            "01.20": ("inverter_energy_kwh", "Inverter kWh counter", "kWh", "kW.h"),
            "04.01": ("tripping_fault", "Tripping fault", "", None),
            "05.01": ("on_time_counter", "On-time counter", "day", "d"),
        },
    },
    "acs880": {
        "identity": ("ACS880primarycontrolprogramforZCUorBCUcontrolunit(AINL)", "3AUA0000085967RevZ"),
        "layout": "merged",  # one parameter listing with "Def / Type" and "FbEq 16b / 32b"
        "status_names": {4: "OFF_2_STA", 5: "OFF_3_STA"},
        "registers16": {
            "01.18": ("motoring_energy_gwh", "Inverter GWh motoring", "GWh", "GW.h"),
            "01.19": ("motoring_energy_mwh", "Inverter MWh motoring", "MWh", "MW.h"),
            "01.20": ("motoring_energy_kwh", "Inverter kWh motoring", "kWh", "kW.h"),
            "04.01": ("tripping_fault", "Tripping fault", "", None),
            "05.01": ("on_time_counter", "On-time counter", "d", "d"),
        },
        "registers32": {
            "01.07": ("motor_current", "Motor current", "A", "A"),
            "01.11": ("dc_voltage", "DC voltage", "V", "V"),
            "01.13": ("output_voltage", "Output voltage", "V", "V"),
            "01.61": ("abs_motor_speed", "Abs motor speed used", "rpm", "/min"),
            "01.63": ("abs_output_frequency", "Abs output frequency", "Hz", "Hz"),
            "01.64": ("abs_motor_torque", "Abs motor torque", "%", "%"),
            "01.66": ("abs_output_power_percent", "Abs output power % motor nom", "%", "%"),
            "46.01": ("speed_scaling", "Speed scaling", "rpm", "/min"),
            "46.02": ("frequency_scaling", "Frequency scaling", "Hz", "Hz"),
        },
        "drive_status": {0: "Enabled", 1: "Inhibited", 2: "DC charged", 3: "Ready to start",
                         4: "Following reference", 5: "Started", 6: "Modulating", 7: "Limiting",
                         8: "Local control", 9: "Network control", 10: "Ext1 active", 11: "Ext2 active",
                         13: "Start request"},
    },
}
# Status word of the ABB Drives profile: the bits both manuals define the same way.
STATUS_WORD = {0: "RDY_ON", 1: "RDY_RUN", 2: "RDY_REF", 3: "TRIPPED", 4: None, 5: None, 6: "SWC_ON_INHIB",
               7: "ALARM", 8: "AT_SETPOINT", 9: "REMOTE", 10: "ABOVE_LIMIT"}
STATUS_END = "USER_0"  # the first bit after them, which ends the last parsed row
DESCRIPTIONS = {
    "abs_output_power": "Vendor unit: kW. Absolute value of 01.14 Output power, whose unit parameter 96.16 "
                        "Unit selection selects.",
    "tripping_fault": "Code of the first active fault, the one that caused the trip.",
    "speed_scaling": "The speed that the value 20000 stands for in 16-bit fieldbus values.",
    "frequency_scaling": "The frequency that the value 20000 stands for in 16-bit fieldbus values.",
}
INTEGER_TYPES = {"uint16": ("u16", 1), "int16": ("i16", 1), "uint32": ("u32", 2), "int32": ("i32", 2)}
PARAMETER_TYPES = {*INTEGER_TYPES, "real32"}
COLUMN_HEADERS = {"No. Name/Value Description Def/FbEq16", "No. Name Type Range Unit FbEq32",
                  "No. Name / Range / Description Def / Type", "Selection FbEq 16b / 32b",
                  "Bit Name Value STATE/Description"}
PARAMETER_ROW = re.compile(r"\s{0,3}(\d\d\.\d\d\d?)\s+[A-Za-z]")
DECIMAL = r"-?\d+(?:\.\d+)?"
HEX_RANGE = re.compile(r"([0-9A-F]{4})h?…([0-9A-F]{4})h")
EQUIVALENT = re.compile(r"(\d+)\s*=\s*(\d+)\s*([^\s/=]*)")


def body_pages(data, count, left, right):
    """Layout text of every page, limited to the body between two x positions (PDF points).

    The ACH580 manual prints a thumb index of chapter numbers in the outer margins, which a
    plain layout extraction mixes into the table rows. Word boxes are stable across Poppler
    versions: every word outside the body must be such a number, or the extraction fails.
    """
    boxes = subprocess.run(["pdftotext", "-f", "1", "-l", str(count), "-bbox", "-", "-"], input=data,
                           capture_output=True, check=True, timeout=120).stdout.decode("utf-8")
    sizes = set(re.findall(r'<page width="([\d.]+)" height="([\d.]+)">', boxes))
    require(len(sizes) == 1, f"ABB manual: pages of {len(sizes)} sizes")
    width, height = (float(value) for value in sizes.pop())
    require(0 < left < right < width, "ABB manual: body limits are outside the page")
    for x_min, x_max, word in re.findall(r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)" yMax="[\d.]+">'
                                         r'([^<]*)</word>', boxes):
        inside = left <= float(x_min) and float(x_max) <= right
        outside = float(x_max) < left or float(x_min) > right
        require(inside or outside and re.fullmatch(r"\d{1,2}", word),
                f"ABB manual: word {word!r} at x {x_min}…{x_max} is not body text or a thumb index number")
    result = subprocess.run(["pdftotext", "-f", "1", "-l", str(count), "-enc", "UTF-8", "-layout", "-x", str(left),
                             "-y", "0", "-W", str(right - left), "-H", str(int(height)), "-", "-"],
                            input=data, capture_output=True, check=True, timeout=120)
    pages = result.stdout.decode("utf-8").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    require(len(pages) == count, f"ABB manual: got {len(pages)} of {count} pages")
    return pages


class Chapter:
    """The lines of one chapter, found by the running header of its pages."""

    def __init__(self, pages, title):
        header = re.compile(rf"(?:\d+ )?{re.escape(title)}(?: \d+)?")
        self.title, self.lines, self.starts, parts, length = title, [], [], [], 0
        for number, page in pages:
            lines = [line for line in page.splitlines() if line.strip()]
            if not lines or not header.fullmatch(" ".join(lines[0].split())):
                continue
            for line in lines[1:]:
                text = " ".join(line.split())
                if text in COLUMN_HEADERS:  # repeated on every page of a table
                    continue
                self.lines.append((number, line))
                self.starts.append(length)
                parts.append(text)
                length += len(text) + 1
        require(self.lines, f"ABB manual: chapter {title!r} not found")
        self.text = " ".join(parts)

    def page(self, offset):
        return self.lines[bisect_right(self.starts, offset) - 1][0]

    def one(self, pattern, what):
        """The only match of a statement in the chapter's whitespace-normalised text."""
        matches = list(re.finditer(pattern, self.text))
        require(len(matches) == 1, f"ABB {self.title}: {what}: {len(matches)} matches")
        return matches[0]

    def blocks(self, number):
        """Line ranges that start with a row of this parameter and end before the next parameter row."""
        rows = [(index, match.group(1)) for index, (_, line) in enumerate(self.lines)
                if (match := PARAMETER_ROW.match(line))]
        ends = [index for index, _ in rows[1:]] + [len(self.lines)]
        return [self.lines[start:end] for (start, found), end in zip(rows, ends) if found == number]


def block_text(block):
    return " ".join(" ".join(line.split()) for _, line in block)


def squeezed(text):
    """Text without spaces and hyphens, to compare statements that the manual breaks inside words."""
    return re.sub(r"[\s-]+", "", text)


def consume(tokens, target, got):
    """Take the leading tokens that continue `target` after `got`: (new got, tokens left)."""
    for index, token in enumerate(tokens):
        piece = token if target.startswith(got + token) else token.rstrip("-")
        if got == target or not piece or not target.startswith(got + piece):
            return got, tokens[index:]
        got += piece
    return got, []


def name_lines(tokens_by_line, name):
    """How many leading lines spell `name` down the first column (a name may wrap, also inside a word)."""
    target, got = name.replace(" ", ""), ""
    for count, tokens in enumerate(tokens_by_line, start=1):
        before = got
        got, _ = consume(tokens, target, got)
        if got == target:
            return count
        if got == before:
            return 0
    return 0


def parameter(chapter, number, name, wanted=None):
    """The single block of rows of this parameter (and, if given, satisfying `wanted`)."""
    found = []
    for block in chapter.blocks(number):
        tokens = [line.split() for _, line in block]
        if name_lines([tokens[0][1:], *tokens[1:4]], name) and (wanted is None or wanted(block)):
            found.append(block)
    require(len(found) == 1, f"ABB {chapter.title}: parameter {number} {name}: {len(found)} usable rows")
    return found[0]


def scale(raw, eng, what):
    """Power of ten for `raw = eng` (100 = 1 gives -2)."""
    ratio = (Decimal(eng) / Decimal(raw)).normalize()
    sign, digits, exponent = ratio.as_tuple()
    require(sign == 0 and digits == (1,), f"ABB {what}: scaling {raw} = {eng} is not a power of ten")
    return exponent


def numeric_range(tokens):
    """(low, high, tokens after the range) from the first cells of a range row, or None."""
    if not tokens:
        return None
    hexadecimal = HEX_RANGE.fullmatch(tokens[0])
    if hexadecimal:
        return Decimal(int(hexadecimal.group(1), 16)), Decimal(int(hexadecimal.group(2), 16)), tokens[1:]
    joined = re.fullmatch(rf"({DECIMAL})…({DECIMAL})(%?)", tokens[0])
    if joined:
        rest = ([joined.group(3)] if joined.group(3) else []) + tokens[1:]
        return Decimal(joined.group(1)), Decimal(joined.group(2)), rest
    if len(tokens) >= 3 and tokens[1] == "..." and all(re.fullmatch(DECIMAL, tokens[i]) for i in (0, 2)):
        return Decimal(tokens[0]), Decimal(tokens[2]), tokens[3:]
    return None


def integer_type(low, high, exponent, registers, stated, what):
    """The point type, from the stated parameter type or from a range that leaves no sign question."""
    if stated in INTEGER_TYPES:
        kind, width = INTEGER_TYPES[stated]
        require(width == registers, f"ABB {what}: a {stated} parameter read as {registers} register(s)")
        return kind
    require(low >= 0, f"ABB {what}: the range starts below zero and the manual does not state the encoding")
    top = high.scaleb(-exponent)
    require(top == top.to_integral_value() and top < 1 << (16 * registers),
            f"ABB {what}: range {low}…{high} does not fit {registers} register(s)")
    return "u16" if registers == 1 else "u32"


def equivalent(text, what):
    match = EQUIVALENT.fullmatch(text.strip())
    require(match, f"ABB {what}: unexpected fieldbus equivalent {text!r}")
    return int(match.group(1)), int(match.group(2)), match.group(3)


def has_range_row(block):
    return any(numeric_range(line.split()) for _, line in block[1:])


def listing_row(chapter, number, name, layout, registers):
    """Range, fieldbus equivalent and stated type of a parameter in the parameter listing."""
    what = f"{number} {name}"
    block = parameter(chapter, number, name, has_range_row)
    index = next(i for i, (_, line) in enumerate(block) if i and numeric_range(line.split()))
    page, line = block[index]
    low, high, _ = numeric_range(line.split())
    stated = None
    if layout == "merged":
        types = [tokens[-1] for tokens in (text.split() for _, text in block[:index]) if tokens[-1] in PARAMETER_TYPES]
        require(len(types) == 1, f"ABB {what}: {len(types)} parameter types before the range row")
        stated = types[0]
        tail = re.search(r"(?:(-|\d+\s*=\s*\d+\s*[^\s/=]*)\s*/\s*)?(\d+\s*=\s*\d+\s*[^\s/=]*)$", line.rstrip())
        require(tail, f"ABB {what}: no fieldbus equivalents on the range row")
        both = tail.group(1) is None
        text = tail.group(2) if both or registers == 2 else tail.group(1)
        require(text != "-", f"ABB {what}: no fixed 16-bit scaling")
        raw, eng, unit = equivalent(text, what)
        if registers == 2 and not unit and not both and index + 1 < len(block):
            unit = block[index + 1][1].split()[-1]  # the unit wrapped to the next line of the cell
    else:
        require(registers == 1, f"ABB {what}: the parameter listing gives 16-bit scalings only")
        tail = re.search(r"(?:^|\s)(\d+\s*=\s*\d+\s*[^\s/=]*)$", line.rstrip())
        require(tail, f"ABB {what}: no fixed 16-bit scaling on the range row")
        raw, eng, unit = equivalent(tail.group(1), what)
    return {"low": low, "high": high, "raw": raw, "eng": eng, "unit": unit, "stated": stated, "page": page,
            "block": block}


def additional_row(chapter, number, name):
    """Range, unit and 32-bit fieldbus equivalent from the one-line rows of Additional parameter data."""
    what = f"{number} {name}"
    words = name.split()
    rows = []
    for page, line in chapter.lines:
        tokens = line.split()
        if tokens[:1] == [number] and tokens[1:1 + len(words)] == words:
            rows.append((page, tokens[1 + len(words):]))
    require(len(rows) == 1, f"ABB {chapter.title}: {what}: {len(rows)} rows")
    page, tokens = rows[0]
    if tokens and tokens[0] in ("Real", "List", "PB", "Data"):
        tokens = tokens[1:]
    parsed = numeric_range(tokens)
    require(parsed, f"ABB {what}: unexpected range in {tokens}")
    low, high, rest = parsed
    units = [token for token in rest if not token[0].isdigit() and token != "="]
    start = next((i for i, token in enumerate(rest) if token[0].isdigit()), None)
    require(start is not None and units[:start] == rest[:start], f"ABB {what}: unexpected row tail {rest}")
    raw, eng, unit = equivalent(" ".join(rest[start:]), what)
    require(set(rest[:start]) <= {unit, "-"}, f"ABB {what}: unit column {rest[:start]} is not {unit!r}")
    return {"low": low, "high": high, "raw": raw, "eng": eng, "unit": unit, "stated": None, "page": page}


def addressing(efb, parameters):
    """Reference base and the Mode 0 register formulas, each checked against the manual's own example."""
    count = int(efb.one(r"The address field of Modbus requests for accessing holding registers is 16 bits\. This "
                        r"allows the Modbus protocol to support addressing of (\d+) holding registers\.",
                        "address field statement").group(1))
    first, last = (int(value) for value in efb.one(
        r"One of these methods is to use 6-digit decimal addresses from (\d{6}) to (\d{6})\. This manual uses "
        r"6-digit decimal addressing to represent Modbus holding register addresses\.",
        "6-digit notation statement").group(1, 2))
    require(count == 1 << 16 == last - first + 1, "ABB register addressing: the 6-digit range is not 65536 registers")
    setup = efb.one(r"holding registers in the (\d{6})…(\d{6}) \((\d+)…(\d+)\) Modbus register range",
                    "set-up table register range")
    require(int(setup.group(2)) == last and int(setup.group(4)) == (1 << 16) - 1,
            "ABB set-up table: the top of the register range is not 465536 (65535)")
    efb.one(r"03h Read Holding Registers Reads the binary contents of holding re(?:- )?gisters \(4X "
            r"references\)\.", "function code 03h")

    mode = parameters.one(
        r"Mode 0 16-bit values \(groups 1…(\d+), indexes 1…(\d+)\): (?:0 )?Register address = (\d+) \+ (\d+) × "
        r"parameter group \+ parameter index\. For example, parameter (\d+)\.(\d+) would be mapped to register "
        r"\d+ \+ \d+ \+ \d+ = (\d+)\. 32-bit values \(groups 1…(\d+), indexes 1…(\d+)\): Register address = (\d+) "
        r"\+ (\d+) × parameter group \+ (\d+) × parameter index\. For example, parameter (\d+)\.(\d+) would be "
        r"mapped to register \d+ \+ \d+ \+ \d+ = (\d+)\.", "58.33 Mode 0 formulas")
    values = [int(value) for value in mode.groups()]
    narrow = {"groups": values[0], "indexes": values[1], "base": values[2], "group": values[3], "index": 1}
    wide = {"groups": values[7], "indexes": values[8], "base": values[9], "group": values[10], "index": values[11]}
    require(register(narrow, values[4], values[5]) == values[6]
            and register(wide, values[12], values[13]) == values[14],
            "ABB 58.33: the worked examples disagree with the formulas")
    return first, narrow, wide


def register(formula, group, index):
    require(1 <= group <= formula["groups"] and 1 <= index <= formula["indexes"],
            f"ABB parameter {group}.{index} is outside the Mode 0 range")
    return formula["base"] + formula["group"] * group + formula["index"] * index


def default_of(parameters, number, name, value, layout):
    """Require the default printed at the end of the parameter's first row(s); return the block."""
    block = parameter(parameters, number, name)
    words = value.split()
    for _, line in block:
        tokens = line.split()
        if layout == "merged" and tokens[-2:-1] == ["/"] and tokens[-1] in PARAMETER_TYPES:
            tokens = tokens[:-2]
        taken = next((size for size in range(len(words), 0, -1) if tokens[-size:] == words[:size]), 0)
        require(taken, f"ABB {number} {name}: default is not {value!r}: {' '.join(tokens)!r}")
        words = words[taken:]
        if not words:
            return block
    raise CorpusError(f"ABB {number} {name}: default is not {value!r}")


def selections(block, names, what):
    """Values of the named selections of a list parameter: {name: (value, description)}."""
    found, current = {}, None
    for _, line in block[1:]:
        tokens = line.split()
        name = next((name for name in names if tokens[:len(name.split())] == name.split()), None)
        if name:
            require(name not in found and re.fullmatch(r"\d+", tokens[-1]), f"ABB {what}: unexpected row {line!r}")
            found[name] = [int(tokens[-1]), tokens[len(name.split()):-1]]
            current = name
        elif current:
            found[current][1] += tokens
    require(list(found) == list(names), f"ABB {what}: selections {list(found)}")
    return {name: (value, " ".join(words)) for name, (value, words) in found.items()}


def word_order(parameters, layout):
    block = default_of(parameters, "58.34", "Word order", "LO-HI", layout)
    require("For each register, the first byte contains the high order byte and the second byte contains the low "
            "order byte." in block_text(block), "ABB 58.34: byte order statement missing")
    found = selections(block, ("HI-LO", "LO-HI"), "58.34 Word order")
    require(found["HI-LO"][1] == "The first register contains the high order word, the second contains the low "
                                 "order word."
            and found["LO-HI"][1] == "The first register contains the low order word, the second contains the high "
                                     "order word.", "ABB 58.34: unexpected word order descriptions")
    return found, block[0][0]


def identifier(text):
    name = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    require(re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name), f"ABB: cannot name {text!r}")
    return name


def bit_rows(lines, prefix):
    """Indexes of table rows that start with a bit number: [(line index, bit, tokens after the bit)]."""
    rows = []
    for index, (_, line) in enumerate(lines):
        tokens = line.split()
        match = re.fullmatch(rf"{prefix}(\d+)", tokens[0])
        if match and int(match.group(1)) <= 31:
            rows.append((index, int(match.group(1)), tokens[1:]))
    return rows


def prose(tokens):
    """Cell text without line-break hyphens, page references and the final full stop."""
    text = re.sub(r"(?<=[a-z])- (?=[a-z])", "", " ".join(tokens))
    return re.sub(r"\s*\(page \d+\)", "", text).rstrip(".")


def status_word(efb, names, layout):
    """Flags of the ABB Drives profile status word, from the table in the EFB chapter."""
    heading, following = (("Status word", "State transition diagram") if layout == "merged" else
                          ("Status Word for the ABB Drives profile", "Status Word for the DCU Profile"))
    titles = [re.sub(r"^\W+", "", " ".join(line.split())) for _, line in efb.lines]  # headings carry a bullet glyph
    require(titles.count(heading) == 1 and titles.count(following) == 1 and
            titles.index(heading) < titles.index(following), "ABB status word table not found")
    lines = [(page, line.split()) for page, line in efb.lines[titles.index(heading) + 1:titles.index(following)]]
    expected = {**STATUS_WORD, **names, max(STATUS_WORD) + 1: STATUS_END}
    starts = {}
    for bit, vendor in expected.items():
        found = [index for index, (_, tokens) in enumerate(lines) if tokens[0] == str(bit)
                 and name_lines([tokens[1:], *(after for _, after in lines[index + 1:index + 2])], vendor)]
        require(len(found) == 1, f"ABB status word bit {bit} {vendor}: {len(found)} rows")
        starts[bit] = found[0]
    require(list(starts.values()) == sorted(starts.values()), "ABB status word: bit rows are out of order")
    flags = []
    for bit, vendor in expected.items():
        if vendor == STATUS_END:
            continue
        target, got, texts, value = vendor, "", {"1": [], "0": []}, None
        for position, (_, tokens) in enumerate(lines[starts[bit]:starts[bit + 1]]):
            got, tokens = consume(tokens[1:] if position == 0 else tokens, target, got)
            if tokens[:1] == ["1"] and value is None or tokens[:1] == ["0"] and value == "1":
                value, tokens = tokens[0], tokens[1:]
            require(value is not None or not tokens, f"ABB status word bit {bit} {vendor}: unexpected row {tokens}")
            if value:
                texts[value] += tokens
        one, zero = (prose(texts[key]) for key in ("1", "0"))
        require(got == target and one, f"ABB status word bit {bit} {vendor}: no state for value 1")
        flags.append({"bit": bit, "name": vendor.lower(), "label": vendor,
                      "description": f"1: {one}; 0: {zero}" if zero not in ("", "–", "-") else f"1: {one}"})
    return flags, heading


def drive_status(block, expected, layout):
    """Flags of 06.16 Drive status word 1 from the bit rows of its parameter block."""
    rows = bit_rows(block, "b" if layout == "merged" else "")
    flags = []
    for bit, vendor in sorted(expected.items()):
        found = [tokens for index, number, tokens in rows if number == bit
                 and name_lines([tokens, *(line.split() for _, line in block[index + 1:index + 2])], vendor)]
        require(len(found) == 1, f"ABB 06.16 bit {bit} {vendor}: {len(found)} rows")
        flags.append({"bit": bit, "name": identifier(vendor), "label": vendor})
    return flags


def error_code(efb, base):
    """The EFB error code register and its values."""
    heading = efb.one(r"Error code registers \(holding registers (\d{6})…(\d{6})\) These registers contain "
                      r"information about the last query\.", "error code registers")
    low, high = int(heading.group(1)), int(heading.group(2))
    row = efb.one(r"(\d{2,6}) Error Code Set when exception code 04h is generated \(see table above\)\.((?: • "
                  r"[0-9A-F]{2}h [^•]+?)+) (\d{2,6}) Failed Register", "error code row")
    printed = row.group(1)
    reference = int(printed) if len(printed) == 6 else low - low % 1000 + int(printed)
    require(low <= reference <= high and int(row.group(3)) == int(printed) + 1,
            f"ABB error code register {printed} is outside {low}…{high}")
    values = []
    for code, text in re.findall(r"• ([0-9A-F]{2})h ([^•]+)", row.group(2)):
        label, _, detail = (part.strip() for part in text.partition(":"))
        value = {"value": int(code, 16), "name": identifier(label), "label": label}
        if detail:
            value["description"] = detail
        values.append(value)
    require(len(values) >= 2 and values[0] == {"value": 0, "name": "no_error", "label": "No error"},
            "ABB error code register: unexpected values")
    return {
        "id": "efb_error_code", "address": reference - base, "type": "u16", "enum": {"values": values},
        "description": "Error of the last Modbus query that the drive answered with exception code 04h; cleared "
                       "when a query succeeds.",
        "aliases": ["Error Code"],
        "source": {"address": printed, "page": efb.page(row.start()),
                   "reference": f"Error code registers (holding registers {low}…{high})"},
    }


def extract(data, selector):
    require(selector in MANUALS, f"Unknown ABB drive selector {selector!r}")
    manual = MANUALS[selector]
    if manual["layout"] == "split":  # the ACH580 selection is the ACS580 one, apart from the entries it overrides
        manual = {**MANUALS["acs580"], **manual}
    layout = manual["layout"]
    count = pdf_page_count(data)
    texts = body_pages(data, count, *manual["body"]) if "body" in manual else pdf_pages(data, 1, count)
    pages = list(enumerate(texts, start=1))
    front = re.sub(r"\s+", "", "".join(page for _, page in pages[:4]))
    for marker in manual["identity"]:
        require(marker in front, f"ABB manual: identity {marker!r} not found")
    efb = Chapter(pages, manual.get("efb", EFB))
    parameters = Chapter(pages, "Parameters")
    additional = Chapter(pages, "Additional parameter data") if layout == "split" else None

    base, narrow, wide = addressing(efb, parameters)
    default_of(parameters, "58.33", "Addressing mode", "Mode 0", layout)
    default_of(parameters, "58.25", "Control profile", "ABB Drives", layout)
    default_of(parameters, "58.104", "Data I/O 4", "SW 16bit", layout)
    default_of(parameters, "58.105", "Data I/O 5", "Act1 16bit", layout)
    orders, order_page = word_order(parameters, layout)
    efb.one(r"The table below shows the default Modbus holding register addresses for (?:the )?drive data",
            "default holding register table")
    efb.one(r"Fieldbus actual signals \(ACT1 and ACT2\) are 16-bit or 32-bit signed integers\.",
            "actual value type statement")
    act1_type = parameter(parameters, "58.28", "EFB act1 type")
    for number, name in (("46.01", "Speed scaling"), ("46.02", "Frequency scaling")):
        require(squeezed(f"caling is defined by parameter {number} {name}.") in squeezed(block_text(act1_type)),
                f"ABB 58.28: {name} is not the scaling of an actual value type")
        block = parameter(parameters, number, name, has_range_row)
        require(squeezed("The value of this parameter corresponds to 20000") in squeezed(block_text(block)),
                f"ABB {number} {name}: the value 20000 statement is missing")

    points = []
    word = efb.one(r"(\d{6}) (?:Default: )?Status Word \(SW(?: 16bit)?\)\.", "status word register")
    flags, heading = status_word(efb, manual["status_names"], layout)
    points.append({
        "id": "status_word", "address": int(word.group(1)) - base, "type": "u16", "flags": {"flags": flags},
        "description": "Status word of the ABB Drives profile, the default of 58.25 Control profile and of "
                       "58.104 Data I/O 4. Bits 0 to 10 are listed.",
        "aliases": ["Status Word (SW)"],
        "source": {"address": word.group(1), "page": efb.page(word.start()),
                   "reference": f"Modbus holding register addresses; {heading}"},
    })
    actual = efb.one(r"(\d{6}) (?:Default: )?Actual value 1 \((?:Act1 16bit|ACT1)\)\.", "actual value 1 register")
    points.append({
        "id": "actual_value_1", "address": int(actual.group(1)) - base, "type": "i16",
        "description": "Raw fieldbus actual value 1, a signed integer. Its type and scaling follow 58.28 EFB act1 "
                       "type: for speed and frequency, 20000 stands for the value of 46.01 Speed scaling or 46.02 "
                       "Frequency scaling.",
        "aliases": ["Actual value 1 (ACT1)"],
        "source": {"address": actual.group(1), "page": efb.page(actual.start()),
                   "reference": "Modbus holding register addresses"},
    })
    points.append(error_code(efb, base))

    def source(number, name, formula, page, where):
        group, index = (int(part) for part in number.split("."))
        reference = register(formula, group, index)
        return reference - base, {"address": str(reference), "page": page, "reference": f"{number} {name}, {where}"}

    def measurement(number, selection, registers, row, where):
        point_id, name, vendor_unit, unit = selection
        what = f"{number} {name}"
        require(row["unit"] == vendor_unit, f"ABB {what}: unit {row['unit']!r}, expected {vendor_unit!r}")
        exponent = scale(row["raw"], row["eng"], what)
        kind = integer_type(row["low"], row["high"], exponent, registers, row["stated"], what)
        address, origin = source(number, name, narrow if registers == 1 else wide, row["page"], where)
        point = {"id": point_id, "address": address, "type": kind}
        if registers == 2:
            point["wordOrder"] = "little"
        if exponent:
            point["conversion"] = {"exponent10": exponent}
        if unit:
            point["unit"] = unit
        if point_id in DESCRIPTIONS:
            point["description"] = DESCRIPTIONS[point_id]
        point["aliases"] = [what]
        point["source"] = origin
        return point

    for number, selection in manual["registers16"].items():
        row = listing_row(parameters, number, selection[1], layout, 1)
        points.append(measurement(number, selection, 1, row, "16-bit value (FbEq16), 58.33 Mode 0"))
    for number, selection in manual["registers32"].items():
        row = (listing_row(parameters, number, selection[1], layout, 2) if layout == "merged"
               else additional_row(additional, number, selection[1]))
        points.append(measurement(number, selection, 2, row, "32-bit value (FbEq32), 58.33 Mode 0"))

    status = listing_row(parameters, "06.16", "Drive status word 1", layout, 1)
    require((status["low"], status["high"], status["raw"], status["eng"]) == (0, 65535, 1, 1),
            "ABB 06.16: unexpected range or scaling")
    address, origin = source("06.16", "Drive status word 1", narrow, status["block"][0][0],
                             "16-bit value, 58.33 Mode 0")
    points.append({
        "id": "drive_status_word_1", "address": address, "type": "u16",
        "flags": {"flags": drive_status(status["block"], manual["drive_status"], layout)},
        "aliases": ["06.16 Drive status word 1"], "source": origin,
    })
    address, origin = source("58.34", "Word order", narrow, order_page, "16-bit value, 58.33 Mode 0")
    points.append({
        "id": "word_order", "address": address, "type": "u16",
        "enum": {"values": [{"value": value, "name": identifier(name), "label": name, "description": text}
                            for name, (value, text) in orders.items()]},
        "description": "Register order of 32-bit parameter values. The 32-bit points here assume LO-HI, the default.",
        "aliases": ["58.34 Word order"], "source": origin,
    })
    return sorted(points, key=lambda point: point["address"])
