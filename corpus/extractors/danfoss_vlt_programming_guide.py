"""Danfoss VLT HVAC Drive FC 102 Programming Guide (PDF).

The selector is the model ("FC 102"). The guide describes every parameter in a block headed by its
number and name, with its range, conversion index and data type; the selected data readouts (group
16-**) are read from those blocks.

The guide does not describe the Modbus RTU register mapping: it refers to the "VLT HVAC Drive FC 102
Design Guide, RS485 Installation and setup", pinned as evidence "danfoss-fc102-design-guide"
(MG11BB22). The extractor parses and requires from its bytes: Modbus RTU over the built-in RS-485
interface; a parameter is translated to Modbus as (10 x parameter number); holding register 40001 is
addressed as register 0000; the request examples "read 3-03, register 03030" with register address
3029 and "write 1-00, register 1000" with address bytes 03 E7 (999); and the conversion factor of each
conversion index used (table 7.8).

Only 16-bit parameters are mapped. The design guide stores int32 and uint32 parameters in two registers
but does not say which register holds the high-order word, and it does not say where an uint8 value sits
in its register. Data type V2 (16-03 Status Word) is not defined in either document.

The FC 202 and FC 301/302 programming guides are not mapped. Their design guides state the
(10 x parameter number) rule and that holding register 40001 is addressed as register 0000, but give no
request example, so whether "holding register 3120" is the PDU address or a register number is open.
The maintainer did not accept the Modbus RTU Operating Instructions (MG92B102, 2011), which are written
for the FC Series as a whole and not for these models, as evidence for them.
"""
from decimal import Decimal
import html
import re
import subprocess

from sourcelib import pdf_page_count, pdf_pages, require

DESIGN_GUIDE = "danfoss-fc102-design-guide"
TYPES = {"Int16": "i16", "Uint16": "u16"}
UNITS = {"V": "V", "Hz": "Hz", "%": "%"}

# (group, number): (point id, parameter name, data type, conversion index, range, unit in the range, UCUM unit)
SELECTED = {
    (16, 2): ("reference_percent", "Reference %", "Int16", -1, ("-200", "200"), "%", "%"),
    (16, 12): ("motor_voltage", "Motor Voltage", "Uint16", -1, ("0", "6000"), "V", "V"),
    (16, 13): ("output_frequency", "Frequency", "Uint16", -1, ("0", "6500"), "Hz", "Hz"),
    (16, 30): ("dc_link_voltage", "DC Link Voltage", "Uint16", 0, ("0", "10000"), "V", "V"),
    (16, 60): ("digital_input", "Digital Input", "Uint16", 0, ("0", "65535"), None, None),
}
DESCRIPTIONS = {
    "digital_input": "Signal states of the digital inputs as a bit pattern; see the guide for the terminal of "
                     "each bit.",
}
BLOCK = re.compile(r"Default value: (?P<default>.+?) Parameter type: Range, (?P<low>-?[\d.]+) - (?P<high>-?[\d.]+)"
                   r" ?(?P<unit>\S+?)? (?:Setup: All setups? )?Conversion index: (?P<index>-?\d+) "
                   r"Data type: (?P<type>\w+) ")
IDENTITY = ["VLT HVAC Drive FC 102", "AU430028034214en-000101 / 130R0318", "Supported software versions: 7.3X"]
SCOPE = r"This programming guide can be used for all FC 102 drives"
POINTER = [r"Communication according to the Modbus RTU protocol as described in the VLT® HVAC Drive FC 102 De-",
           r"sign Guide, RS485 Installation and setup\."]
# Design guide statements, matched on single text lines (the pages have two columns).
DG_STATEMENTS = [r"MG11BB22 - VLT® is a registered Danfoss trademark", r"VLT® HVAC Drive Design Guide",
                 r"RTU format over the built-in RS-485 interface\.",
                 r"Holding register 40001 is addressed as register 0000 in the",
                 r"01000-01990\s+100 parameter group \(parameters 100 through 199\)",
                 r"Read holding registers\s+3\b"]
DG_RULE = r"as \(10 x parameter number\) DECIMAL\."
READ_EXAMPLE = r"Example: Read (\d+)-(\d\d) Maximum Reference, register (\d+)\."
WRITE_EXAMPLE = r"Example: Write to (\d+)-(\d\d) Configuration Mode, register (\d+)\."
START_HIGH = r"Starting Address HI\s+([0-9A-F]{2}) \(Register address (\d+)\)"
START_LOW = r"Starting Address LO\s+([0-9A-F]{2}) \(Register address (\d+)\)"
WRITE_HIGH = r"Register Address HI\s+([0-9A-F]{2}) \(Register address (\d+)\)"
WRITE_LOW = r"Register Address LO\s+([0-9A-F]{2}) \(Register address (\d+)\)"
CONVERSION_CAPTION = "Table 7.8 Conversion Table"
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="[\d.]+">([^<]*)</word>')


def text_of(data):
    return pdf_pages(data, 1, pdf_page_count(data))


def one(pattern, text, what):
    matches = re.findall(pattern, text)
    require(len(matches) == 1, f"{what}: expected once, found {len(matches)} times")
    return matches[0]


def register_example(text, example, high, low, what, check_bytes=True):
    """A request example: parameter, its register number and the address bytes sent for it."""
    group, number, register = one(example, text, what)
    (high_byte, high_address), (low_byte, low_address) = one(high, text, what), one(low, text, what)
    require(int(register) == 10 * (int(group) * 100 + int(number)), f"{what}: register is not 10 x parameter number")
    require(int(high_address) == int(low_address) == int(register) - 1, f"{what}: address is not register - 1")
    if check_bytes:
        require(int(high_byte + low_byte, 16) == int(register) - 1, f"{what}: address bytes disagree")


def conversion_factors(data, page):
    """Conversion index -> factor from the word boxes of table 7.8 (index and factor columns)."""
    result = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), "-bbox", "-enc", "UTF-8", "-", "-"],
                            input=data, capture_output=True, check=True, timeout=60)
    words = [(float(x), float(y), html.unescape(text)) for x, y, text in WORD.findall(result.stdout.decode("utf-8"))]
    columns = {}
    for (x, y, text), (_, next_y, following) in zip(words, words[1:]):
        if text == "Conversion" and following in ("index", "factor") and abs(next_y - y) < 1:
            require(following not in columns, f"Danfoss {DESIGN_GUIDE}: conversion table header found twice")
            columns[following] = x
    require(set(columns) == {"index", "factor"}, f"Danfoss {DESIGN_GUIDE}: conversion table header not found")
    indexes = [(y, text) for x, y, text in words if abs(x - columns["index"]) < 3 and re.fullmatch(r"-?\d+", text)]
    factors = [(y, text) for x, y, text in words if abs(x - columns["factor"]) < 3 and re.fullmatch(r"[\d.]+", text)]
    table = {}
    for y, index in indexes:
        row = [factor for factor_y, factor in factors if abs(factor_y - y) < 1]
        if len(row) == 1:
            table[int(index)] = Decimal(row[0])
    return table


def check_design_guide(data):
    """Require MG11BB22's statements about the FC 102 built-in RS-485 Modbus RTU; return its conversion table."""
    pages = text_of(data)
    text = "\n".join(pages)
    what = f"Danfoss {DESIGN_GUIDE}"
    for pattern in DG_STATEMENTS:
        require(re.search(pattern, text), f"{what}: statement {pattern!r} not found")
    one(DG_RULE, text, f"{what} parameter rule")
    # MG11BB22 prints the low address byte of the read example as "05" (0x0B05 is not 3029); the decimal
    # address it states and the write example agree with register - 1.
    register_example(text, READ_EXAMPLE, START_HIGH, START_LOW, f"{what} read example", check_bytes=False)
    register_example(text, WRITE_EXAMPLE, WRITE_HIGH, WRITE_LOW, f"{what} write example")
    table_pages = [number for number, page in enumerate(pages, 1) if CONVERSION_CAPTION in page]
    require(len(table_pages) == 1, f"{what}: conversion table not found once")
    return conversion_factors(data, table_pages[0])


def parameter_blocks(pages):
    """(page number, flattened attribute block) per selected parameter, found by its heading line."""
    headings = {f"{group}-{number:02d} {entry[1]}": (group, number) for (group, number), entry in SELECTED.items()}
    blocks = {}
    for page_number, page in enumerate(pages, 1):
        lines = page.splitlines()
        for index, line in enumerate(lines):
            key = headings.get(" ".join(line.split()))
            if key is None:
                continue
            require(key not in blocks, f"Danfoss parameter {key[0]}-{key[1]:02d}: heading found twice")
            blocks[key] = (page_number, " ".join(" ".join(lines[index + 1:index + 17]).split()))
    missing = sorted(set(SELECTED) - set(blocks))
    require(not missing, f"Danfoss programming guide: parameters not found: {missing}")
    return blocks


def extract(data, selector, evidence=None):
    require(selector == "FC 102", f"Danfoss: unknown model {selector!r}")
    require(evidence and DESIGN_GUIDE in evidence, f"Danfoss {selector}: evidence document missing")
    factors = check_design_guide(evidence[DESIGN_GUIDE])

    pages = text_of(data)
    front = " ".join("\n".join(pages[:16]).split())
    for marker in IDENTITY:
        require(marker in front, f"Danfoss {selector}: guide identity {marker!r} not found")
    require(re.search(SCOPE, front), f"Danfoss {selector}: scope statement not found")
    for pattern in POINTER:
        require(re.search(pattern, "\n".join(pages)),
                f"Danfoss {selector}: the guide no longer refers to the design guide for Modbus RTU")

    points = []
    for (group, number), (page_number, block) in sorted(parameter_blocks(pages).items()):
        point_id, name, kind, index, span, range_unit, unit = SELECTED[(group, number)]
        label = f"{group}-{number:02d}"
        match = BLOCK.match(block)
        require(match, f"Danfoss {selector} parameter {label}: cannot read attributes from {block[:120]!r}")
        require(match["type"] == kind and int(match["index"]) == index,
                f"Danfoss {selector} parameter {label}: unexpected data type or conversion index")
        require((match["low"], match["high"]) == span and match["unit"] == range_unit,
                f"Danfoss {selector} parameter {label}: unexpected range {match['low']} - {match['high']} "
                f"{match['unit']}")
        require(factors.get(index) == Decimal(10) ** index,
                f"Danfoss {selector} parameter {label}: design guide gives no factor 10^{index} for index {index}")
        pnu = group * 100 + number
        point = {"id": point_id, "label": name, "aliases": [label], "address": 10 * pnu - 1, "type": TYPES[kind]}
        if index:
            point["conversion"] = {"exponent10": index}
        if unit:
            require(UNITS[range_unit] == unit, f"Danfoss {selector} parameter {label}: unit table disagrees")
            point["unit"] = unit
        if point_id in DESCRIPTIONS:
            point["description"] = DESCRIPTIONS[point_id]
        point["source"] = {"address": label, "page": page_number,
                           "reference": f"Parameter {label} {name}, PNU {pnu}, {kind}, conversion index {index}"}
        points.append(point)
    return points
