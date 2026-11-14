"""ABB Relion 615 series Modbus point list manuals (PDF): REF615 Ver. 3.0, REM615 Ver. 2.0 and RET615 ANSI
Ver. 5.0 FP1.

The selector is the model slug, "ref615", "rem615" or "ret615". Each source pins, as evidence, the 615 series
Modbus communication protocol manual that its point list names under related documentation: 1MRS756468 for
REF615 and REM615, the ANSI edition 1MAC057386-MB for RET615. From that manual the extractor requires the
statements the mapping depends on: listings use PLC addresses that start from 1 and the traffic carries the
PLC address minus one (section 2.1.4), so the PDU address is the listed number minus one; every register value
is the value multiplied by a configurable scaleFactor plus a configurable Offset (3.4.5); per-unit values use
scale factor 1000 by default; 32-bit registers are high word first by default; and bit address 16 is register 1,
bit 0, the rule bit = 16 x register + bit that every indication row must satisfy.

The manual states the default scaleFactor but not the default Offset. Only the RET615 point list states that
the offset is 0 by default, so only RET615 maps measurand registers (dividing by the default scale factor).
REF615 and REM615 map only indication bits (3.4.4 digital input data, read as bits or as packed bits in
registers), which the measurand scaling of 3.4.5 does not cover.

REF615 and REM615 list full IEC 61850 names per row, under group headings that name the standard configurations
a group depends on. The RET615 ANSI list gives the logical device and node on a group line and only the data
object and attribute (".Pos.stVal.Close") on each row; the extractor joins them. Rows are selected by IEC 61850
name; addresses, types and scales come from the parsed rows.
"""
from decimal import Decimal
import re

from sourcelib import CorpusError, pdf_page_count, pdf_pages, require

MODELS = {
    "ref615": {
        "layout": "iec",
        "heading": "Point list for REF615 Ver. 3.0 FE01-08",
        "document": "1MRS756581",
        "manual": "abb-615-modbus-protocol-manual",
    },
    "rem615": {
        "layout": "iec",
        "heading": "Point list for REM615 Ver.2.0 ME03",
        "document": "1MRS756877",
        "manual": "abb-615-modbus-protocol-manual",
    },
    "ret615": {
        "layout": "ansi",
        "heading": "RET615 ANSI Modbus Point List Manual",
        "document": "1MAC203705-MB",
        "manual": "abb-615-ansi-modbus-protocol-manual",
    },
}

# Statements of the 615 series Modbus communication protocol manual (IEC and ANSI editions alike), matched
# against whitespace-normalised text.
MANUAL_STATEMENTS = (
    r"PLC addressing starts from address 1 and regular Modbus data addressing starts from 0\.",
    r"The regular Modbus addressing, that is the PLC address decremented by one, is shown when analyzing the "
    r"Modbus traffic on the physical network\.",
    r"Listings and references to the Modbus data in this documentation follow the PLC addressing scheme\. "
    r"Addresses start from 1\.",
    r"The addressing of the application data in the documentation and tools follows the so-\s?called "
    r"Modbus-PLC addressing principle, where the base address 1 is used\.",
    r"there always exists a scaleFactor and an offset parameter for each Modbus register value\.",
    r"The formula for calculating the Modbus register value is: Modbus value = \( IEC 61850 ?Value × "
    r"scaleFactor \) \+ Offset",
    r"Most vendors, including this relay, use the order high-low \(high word on lower address\) as default\.",
)
PER_UNIT_SCALE = r"As a default, this protection relay shows per-unit values multiplied with the scaleFactor (\d+)\."
BIT_ADDRESS = r"The bit address (\d+) is the same as register (\d+), bit (\d+)\."
PER_UNIT_RANGES = ("[xIn]", "[xUn]")

# Column explanations of the point lists themselves.
BASE_STATEMENTS = {
    "iec": (
        r"Bit addr Bit \(1X and 0X\) PLC address, base address = 1",
        r"Reg\.bit(?: addr)? Register PLC address \(3X and 4X\) and bit within register \(0\.\.15\)",
    ),
    "ansi": (
        r"BitA Default 0X and 1X bit address for the data\.",
        r"RegA Default 3X and 4X register\.bit \(00-15\) address for the data\.",
        r"RegA Default 3X and 4X register address for the data\.",
        r"Type Type of the register\. The alternatives are u16, u32 \(unsigned 16 and 32 bits integer\) or "
        r"i16, i32 \(signed 16 and 32 bit integer\)\.",
        r"Scale Scale factor as default\. Also, an adjustable offset value exists that is set to 0 by default\.",
        r"Values The value range of the original IEC 61850 value, that is, before scaling\.",
    ),
}

# RET615 measurand registers: IEC 61850 name -> (point id, expected type, expected value-range unit, unit)
REGISTERS = {
    "LD0.CMMXU1.A.phsA.instCVal.mag": ("hv_current_a", "u16", "[xIn]", None),
    "LD0.CMMXU1.A.phsB.instCVal.mag": ("hv_current_b", "u16", "[xIn]", None),
    "LD0.CMMXU1.A.phsC.instCVal.mag": ("hv_current_c", "u16", "[xIn]", None),
    "LD0.CMMXU2.A.phsA.instCVal.mag": ("mv_current_a", "u16", "[xIn]", None),
    "LD0.CMMXU2.A.phsB.instCVal.mag": ("mv_current_b", "u16", "[xIn]", None),
    "LD0.CMMXU2.A.phsC.instCVal.mag": ("mv_current_c", "u16", "[xIn]", None),
    "LD0.TR2PTDF1.DifAClc.phsA.mag": ("differential_current_a", "u16", "[xIn]", None),
    "LD0.TR2PTDF1.DifAClc.phsB.mag": ("differential_current_b", "u16", "[xIn]", None),
    "LD0.TR2PTDF1.DifAClc.phsC.mag": ("differential_current_c", "u16", "[xIn]", None),
    "LD0.T2PTTR1.Tmp.mag": ("protected_object_temperature", "i16", "[C]", "Cel"),
    "LD0.TPOSYLTC1.TapPos.valWTr.posVal": ("tap_position", "i16", None, None),
    "CTRL.CBCSWI1.OpCntRs.stVal": ("cb_operation_counter", "u16", None, None),
    "LD0.LPHD1.PhyHealth2.stVal": ("internal_fault_code", "u16", None, None),
}

DIFFERENTIAL = "differential current of the transformer differential protection (87T) in multiples of the " \
               "rated current In."
DESCRIPTIONS = {
    "hv_current_a": "Phase A current on the high-voltage side (IA (1)) in multiples of the rated current In.",
    "hv_current_b": "Phase B current on the high-voltage side (IB (1)) in multiples of the rated current In.",
    "hv_current_c": "Phase C current on the high-voltage side (IC (1)) in multiples of the rated current In.",
    "mv_current_a": "Phase A current on the medium-voltage side (IA (2)) in multiples of the rated current In.",
    "mv_current_b": "Phase B current on the medium-voltage side (IB (2)) in multiples of the rated current In.",
    "mv_current_c": "Phase C current on the medium-voltage side (IC (2)) in multiples of the rated current In.",
    "differential_current_a": f"Phase A {DIFFERENTIAL}",
    "differential_current_b": f"Phase B {DIFFERENTIAL}",
    "differential_current_c": f"Phase C {DIFFERENTIAL}",
    "protected_object_temperature": "Object temperature of the thermal overload protection with two time "
                                    "constants (49T), range -100.0...9999.9; the point list writes the unit as "
                                    "[C]. It gives scale 1, so the register carries whole degrees only.",
    "tap_position": "Tap changer position (84T), range -64...63.",
    "internal_fault_code": "Latest internal fault code of the physical device; codes are in the product manuals.",
}

# Indication words: (point id, description, models, MCD copies on the odd bits, flags), each flag
# (flag name, IEC 61850 name, table title, label). A table title or label of None is not checked; RET615 scopes
# rows by table title because the same name can appear in a momentary and a momentary-plus-MCD table.
MCD_NOTE = "each odd bit is the change-detect (MCD) copy of the bit below it."
CB_TABLE = r"CTRL\.CBCSWI1 Circuit breaker \(1\) mom\. position"
FLAG_WORDS = (
    ("protection_conditioning", f"Momentary start, operate and master trip bits; {MCD_NOTE}",
     {"ref615", "rem615"}, True, (
         ("start", "LD0.LEDPTRC1.Str.general", None, None),
         ("operate", "LD0.LEDPTRC1.Op.general", None, None),
         ("master_trip_1_input", "LD0.TRPPTRC1.Op.general", None, None),
         ("master_trip_1_output", "LD0.TRPPTRC1.Tr.general", None, None),
         ("master_trip_2_input", "LD0.TRPPTRC2.Op.general", None, None),
         ("master_trip_2_output", "LD0.TRPPTRC2.Tr.general", None, None),
     )),
    ("protection_conditioning", f"Momentary global pickup, global trip and master trip bits; {MCD_NOTE}",
     {"ret615"}, True, (
         ("pickup", "LD0.LEDPTRC1.Str.general", None, "Global pickup"),
         ("trip", "LD0.LEDPTRC1.Op.general", None, "Global trip"),
         ("master_trip_1_input", "LD0.TRPPTRC1.Op.general", None, "Op. input signal"),
         ("master_trip_1_output", "LD0.TRPPTRC1.Tr.general", None, "Trip output signal"),
         ("master_trip_2_input", "LD0.TRPPTRC2.Op.general", None, "Op. input signal"),
         ("master_trip_2_output", "LD0.TRPPTRC2.Tr.general", None, "Trip output signal"),
     )),
    ("limit_supervision", "Momentary high alarm and high warning bits of the phase current and residual "
     f"current limit supervision; {MCD_NOTE}", {"ref615", "rem615"}, True, (
         ("phase_current_high_alarm", "LD0.CMMXU1.HiAlm.stVal", None, None),
         ("phase_current_high_warning", "LD0.CMMXU1.HiWrn.stVal", None, None),
         ("residual_current_high_alarm", "LD0.RESCMMXU1.HiAlm.stVal", None, None),
         ("residual_current_high_warning", "LD0.RESCMMXU1.HiWrn.stVal", None, None),
     )),
    ("cb_position", "Momentary circuit breaker position bits (close, open, faulty or intermediate).",
     {"ref615", "rem615", "ret615"}, False, (
         ("closed", "CTRL.CBCSWI1.Pos.stVal.Close", CB_TABLE, None),
         ("open", "CTRL.CBCSWI1.Pos.stVal.Open", CB_TABLE, None),
         ("faulty_or_intermediate", "CTRL.CBCSWI1.Pos.stVal.Fault", CB_TABLE, None),
     )),
    ("cb_condition_monitoring", "Momentary circuit breaker condition monitoring alarm and lockout bits.",
     {"ref615", "rem615"}, False, (
         ("open_travel_time_alarm", "LD0.SSCBR1.OpnAlm.stVal", None, None),
         ("close_travel_time_alarm", "LD0.SSCBR1.ClsAlm.stVal", None, None),
         ("spring_charging_time_alarm", "LD0.SSCBR1.SprChaAlm.stVal", None, None),
         ("operations_alarm", "LD0.SSCBR1.OpNumAlm.stVal", None, None),
         ("operations_lockout", "LD0.SSCBR1.OpNumLO.stVal", None, None),
         ("inactivity_alarm", "LD0.SSCBR1.LonTmAlm.stVal", None, None),
         ("pressure_alarm", "LD0.SSCBR1.PresAlm.stVal", None, None),
         ("pressure_lockout", "LD0.SSCBR1.PresLO.stVal", None, None),
         ("iyt_alarm", "LD0.SSCBR1.APwrAlm.stVal", None, None),
         ("iyt_lockout", "LD0.SSCBR1.APwrLO.stVal", None, None),
         ("cb_life_alarm", "LD0.SSCBR1.CBLifAlm.stVal", None, None),
     )),
    ("differential_protection", f"Momentary trip bits of the transformer differential protection (87T); {MCD_NOTE}",
     {"ret615"}, True, (
         ("trip", "LD0.TR2PTDF1.Op.general", None, "General trip"),
         ("trip_phase_a", "LD0.TR2PTDF1.Op.phsA", None, "phsA trip"),
         ("trip_phase_b", "LD0.TR2PTDF1.Op.phsB", None, "phsB trip"),
         ("trip_phase_c", "LD0.TR2PTDF1.Op.phsC", None, "phsC trip"),
     )),
)
# Single indication bits read through a mask: (point id, models, IEC 61850 name, label)
MASK_BITS = (
    ("trip_circuit_1_alarm", {"ref615", "rem615"}, "LD0.TCSSCBR1.CirAlm.stVal", None),
    ("trip_circuit_2_alarm", {"ref615", "rem615"}, "LD0.TCSSCBR2.CirAlm.stVal", None),
    ("trip_circuit_1_alarm", {"ret615"}, "LD0.TCSSCBR1.CircAlm.stVal", "Supervision alarm"),
    ("trip_circuit_2_alarm", {"ret615"}, "LD0.TCSSCBR2.CircAlm.stVal", "Supervision alarm"),
)
DISCRETE_BITS = (
    ("cb_closed_input", {"ref615", "rem615", "ret615"}, "CTRL.CBCSWI1.Pos.stVal.Close", CB_TABLE),
)
# RET615 supported functions (table 2) behind the points: code, ANSI designation, rows for configurations B, F.
SUPPORTED = (
    (r"CMMXU", r"IA, IB, IC \(1\)", "1HV"),
    (r"", r"IA, IB, IC \(2\)", "1MV"),
    (r"TR2PTDF", r"87T", "1"),
    (r"T2PTTR", r"49T \(1\)", "1HV"),
    (r"TPOSYLTC", r"84T", "1"),
    (r"CBXCBR1", r"52 \(1\)", "1HV"),
    (r"TCSSCBR", r"TCM", "2"),
    (r"TRPPTRC", r"86/94", "2"),
)

# A group heading is a single indented phrase between the table rows; it names the standard
# configurations ("all variants", "variants FE05,06", "(FE08)", "FE02,04,05,06") when the group depends on
# them. Running page-margin text ("REF615" on the left, "Modbus data mappings" on the right) is not part of it.
HEADING = re.compile(r"^ {40,125}([A-Z](?:\S| (?=\S))*)(?: {10,}\S.*)?\s*$", re.MULTILINE)
MARGIN = re.compile(r"^[ \t]*(?:Point List Manual|REF615|REM615)(?=\s)", re.MULTILINE)
CONFIGURATION = re.compile(r"(?i)all variants|FE\d\d(?:[,.]\d\d)*|\(FE[\d,–-]+\)")
# Headings for every standard configuration; "optional in all variants" is not one of them.
ALL_VARIANTS = re.compile(r"(?i)(?:, all variants|\(all variants\))$")
INDICATION_ROW = re.compile(
    r"^\s*(?:Point List Manual\s+|REF615\s+|REM615\s+)?(\d{4})\s+(\d{3})\.(\d{2})\s+(?:(\d)\s+)?"
    r"((?:LD0|CTRL|DR)\.\S+)\s+(.*)$",
    re.MULTILINE,
)
# RET615 ANSI layout: a group line holds the logical device and node, each row the rest of the name.
ANSI_TABLE = re.compile(r"^\s*Table (\d+):\s+(\S.*?)\s*$")
ANSI_GROUP = re.compile(r"^[\s:]+((?:LD0|CTRL|DR)\.[A-Za-z0-9]+)(?:\s{2,}\S.*)?$")
ANSI_REGISTER_ROW = re.compile(r"^\s*(\d{3,4})\s+(u16|i16|u32|i32)\s+(\d+)\s+(\.\S+)(?:\s{2,}(.*?))?\s*$")
ANSI_INDICATION_START = re.compile(r"^\s*\d{4}\s+\d{3}\.\d{2}\b")
ANSI_INDICATION_ROW = re.compile(r"^\s*(\d{4})\s+(\d{3})\.(\d{2})\s+(\.\S+|< ?reserved ?>)(?:\s{2,}(.*?))?\s*$")


def normalised(pages):
    return re.sub(r"\s+", " ", "\n".join(pages))


def table_pages(pages, start, stop):
    """(page index, text) for a table from its heading up to the next table heading `stop`."""
    first = [index for index, page in enumerate(pages) if re.search(start, page)]
    require(len(first) == 1, f"ABB point list: table heading {start!r} found {len(first)} times")
    result = []
    for index in range(first[0], len(pages)):
        text = pages[index]
        if index == first[0]:
            text = text[re.search(start, text).start():]
        end = re.search(stop, text)
        result.append((index, text[:end.start()] if end else text))
        if end:
            return result
    raise CorpusError(f"ABB point list: no {stop!r} after {start!r}")


def heading_before(table, position, index):
    """The configuration heading that precedes a row, searching back through the table's pages."""
    for page_index, page in reversed(table):
        if page_index > index:
            continue
        text = page[:position] if page_index == index else page
        headings = HEADING.findall(MARGIN.sub(lambda match: " " * len(match.group(0)), text))
        if headings:
            return headings[-1] if CONFIGURATION.search(headings[-1]) else None
    return None


def conversion(scale):
    value = Decimal(scale)
    require(value > 0, f"ABB scale {scale} is not positive")
    exponent = -value.log10()
    require(exponent == exponent.to_integral_value(), f"ABB scale {scale} is not a power of ten")
    exponent = int(exponent)
    return {"exponent10": exponent} if exponent else None


def protocol_manual(selector, model, evidence, text):
    """Check the pinned protocol manual and return its default per-unit scale factor."""
    require(model["manual"] in (evidence or {}),
            f"ABB {selector}: protocol manual {model['manual']} is not pinned as evidence")
    data = evidence[model["manual"]]
    manual = normalised(pdf_pages(data, 1, pdf_page_count(data)))
    document = re.match(r"\W*RELION® PROTECTION AND CONTROL 615 series (?:ANSI )?Modbus Communication Protocol "
                        r"Manual Document ID: (\S+) Issued: \S+ Revision: [A-Z] Product version: ", manual)
    require(document, f"ABB {selector}: evidence is not a 615 series Modbus communication protocol manual")
    named = re.findall(r"Related documentation (?:Name of the document Document ID )?"
                       r"Modbus Communication Protocol Manual (\S+)", text)
    require(named == [document.group(1)],
            f"ABB {selector}: point list names protocol manual {named}, evidence is {document.group(1)}")
    version = re.search(r"Product version: (\d+\.\d+(?: FP\d+)?) ", text)
    require(version, f"ABB {selector}: point list product version missing")
    require(re.search(rf"[A-Z]/\d{{4}}-\d{{2}}[-–]\d{{2}} {re.escape(version.group(1))} "
                      r"(?:First release|Content updated)", manual),
            f"ABB {selector}: protocol manual revision history does not cover product version {version.group(1)}")
    for statement in MANUAL_STATEMENTS:
        require(re.search(statement, manual), f"ABB {selector}: protocol manual statement missing: {statement}")
    bit = re.findall(BIT_ADDRESS, manual)
    require(len(bit) == 1 and int(bit[0][0]) == 16 * int(bit[0][1]) + int(bit[0][2]),
            f"ABB {selector}: protocol manual bit address rule missing or not bit = 16 x register + bit: {bit}")
    per_unit = re.findall(PER_UNIT_SCALE, manual)
    require(len(per_unit) == 1, f"ABB {selector}: protocol manual default per-unit scale factor missing")
    return per_unit[0]


def iec_indications(pages):
    """REF615 and REM615: one indication table with full IEC 61850 names and configuration headings."""
    indications = table_pages(pages, r"Table 3:\s+Indications", r"Table [45]:\s+(Indications in|Controls)")
    bits = []
    for index, page in indications:
        for match in INDICATION_ROW.finditer(page):
            bit_address, register, bit, _, name, rest = match.groups()
            # Rows for different standard configurations can share a position (REF615 199.00 onwards
            # is synchrocheck in FE08 and X130 inputs in FE01-07), so keep every row.
            bits.append({"bit_address": int(bit_address), "register": int(register), "bit": int(bit),
                         "name": name, "rest": rest, "mcd": "MCD" in rest, "page": index + 1,
                         "table": "Table 3 Indications", "title": None,
                         "heading": heading_before(indications, match.start(), index)})
    return {}, bits


def ansi_lines(pages, start, stop):
    """(page number, table number, table title, group, line) for the lines of a RET615 section."""
    group, table = None, (None, None)
    for index, page in table_pages(pages, start, stop):
        for line in page.splitlines():
            heading = ANSI_TABLE.match(line)
            if heading:
                group, table = None, heading.groups()
                continue
            member = ANSI_GROUP.match(line)
            if member:
                group = member.group(1)
                continue
            yield index + 1, table, group, line


def ansi_tables(selector, pages, per_unit):
    """RET615 ANSI: tables per function, with group lines that hold the logical device and node."""
    text = normalised(pages)
    table2 = normalised(page for _, page in table_pages(pages, r"Table 2:\s+Supported functions",
                                                         r"\n2\.3\s+Indications"))
    for code, designation, count in SUPPORTED:
        require(re.search(rf"{code}\s*{designation} {count} {count} ", table2),
                f"ABB {selector}: table 2 does not list {code or designation} as {count} in configurations B and F")
    require("The point lists describe a superset of all data available through the standard configuration/s "
            "including the optional functionalities." in text, f"ABB {selector}: superset statement missing")

    found = {}
    for page_number, (number, _), group, line in ansi_lines(
            pages, r"Table 110:\s+Explanations of columns in register tables", r"\n2\.4\.2\s+Unmapped registers"):
        match = ANSI_REGISTER_ROW.match(line)
        if not match:
            continue
        reference, kind, scale, attribute, _ = match.groups()
        require(group, f"ABB {selector} {reference}: register row without a logical node group")
        name = group + attribute
        if name not in REGISTERS:
            continue
        point_id, expected_kind, range_unit, unit = REGISTERS[name]
        require(point_id not in found, f"ABB {selector}: duplicate row for {name}")
        require(kind == expected_kind, f"ABB {selector} {name}: type {kind}, expected {expected_kind}")
        if range_unit:
            require(range_unit in line, f"ABB {selector} {name}: value range unit {range_unit} missing")
        if range_unit in PER_UNIT_RANGES:
            require(scale == per_unit,
                    f"ABB {selector} {name}: per-unit scale {scale}, protocol manual default {per_unit}")
        point = {"id": point_id, "address": int(reference) - 1, "type": kind, "aliases": [name]}
        converted = conversion(scale)
        if converted:
            point["conversion"] = converted
        if unit:
            point["unit"] = unit
        if point_id in DESCRIPTIONS:
            point["description"] = DESCRIPTIONS[point_id]
        point["source"] = {"address": reference, "page": page_number, "reference": f"Table {number}, scale {scale}"}
        found[point_id] = point
    missing = {spec[0] for spec in REGISTERS.values()} - found.keys()
    require(not missing, f"ABB {selector}: missing register rows {sorted(missing)}")

    bits = []
    for page_number, (number, title), group, line in ansi_lines(
            pages, r"Table 3:\s+Explanations of the indications table columns",
            r"Table 110:\s+Explanations of columns in register tables"):
        if not ANSI_INDICATION_START.match(line):
            continue
        match = ANSI_INDICATION_ROW.match(line)
        require(match, f"ABB {selector}: unexpected indication row {line.strip()!r}")
        bit_address, register, bit, attribute, rest = match.groups()
        if "reserved" in attribute:
            continue
        require(group, f"ABB {selector} {bit_address}: indication row without a logical node group")
        bits.append({"bit_address": int(bit_address), "register": int(register), "bit": int(bit),
                     "name": group + attribute, "rest": rest or "", "mcd": attribute == ".mcd",
                     "page": page_number, "table": f"Table {number}", "title": title, "heading": None})
    return found, bits


def extract(data, selector, evidence=None):
    require(selector in MODELS, f"Unknown ABB 615 selector {selector!r}")
    model = MODELS[selector]
    pages = pdf_pages(data, 1, pdf_page_count(data))
    text = normalised(pages)
    require(f"Document ID: {model['document']}" in text and model["heading"] in text,
            f"ABB {selector}: document ID or point list heading missing")
    per_unit = protocol_manual(selector, model, evidence, text)
    if model["layout"] == "iec":
        overview = normalised([next(page for page in pages if "Point list table columns" in page)])
    else:
        overview = text
    for statement in BASE_STATEMENTS[model["layout"]]:
        require(re.search(statement, overview), f"ABB {selector}: column statement missing: {statement}")
    if model["layout"] == "iec":
        found, bits = iec_indications(pages)
    else:
        found, bits = ansi_tables(selector, pages, per_unit)

    for row in bits:
        require(row["bit_address"] == 16 * row["register"] + row["bit"],
                f"ABB {selector} {row['bit_address']}: bit address and register.bit "
                f"{row['register']}.{row['bit']:02d} disagree")
    named = [row for row in bits if not row["mcd"]]

    def indication(name, table, label):
        """The single momentary row for a name, which must be alone at its register.bit position."""
        # REF615 and REM615 have a single indication table, so only RET615 rows are scoped by table title.
        scoped = table is not None and model["layout"] == "ansi"
        rows = [row for row in named if row["name"] == name and (not scoped or re.fullmatch(table, row["title"]))]
        require(len(rows) == 1, f"ABB {selector}: {name} found {len(rows)} times")
        row = rows[0]
        if label is not None:
            require(label in re.split(r"\s{2,}", row["rest"].strip()),
                    f"ABB {selector} {name}: description {label!r} missing in {row['rest']!r}")
        shared = [other["name"] for other in bits if (other["register"], other["bit"]) == (row["register"], row["bit"])]
        require(shared == [name], f"ABB {selector}: {row['register']}.{row['bit']:02d} is shared by {shared}")
        return row

    def mcd_copy(row):
        """Require the change-detect copy of a momentary row on the next bit."""
        node = ".".join(row["name"].split(".")[:2])
        copies = [other for other in bits if other["mcd"]
                  and (other["register"], other["bit"]) == (row["register"], row["bit"] + 1)]
        require(len(copies) == 1 and copies[0]["name"] in (row["name"], f"{node}.mcd"),
                f"ABB {selector} {row['name']}: no MCD copy on {row['register']}.{row['bit'] + 1:02d}")

    def configuration(point, rows):
        """Name the configuration heading when the rows depend on specific standard configurations."""
        headings = {row["heading"] for row in rows}
        if any(heading and not ALL_VARIANTS.search(heading) for heading in headings):
            require(len(headings) == 1, f"ABB {selector} {point['id']}: rows under different headings {headings}")
            point["description"] = f"{point.get('description', '')} Listed under '{headings.pop()}'.".strip()
        return point

    points = list(found.values())
    for point_id, description, models, mcd, flags in FLAG_WORDS:
        if selector not in models:
            continue
        rows = [(flag, name, indication(name, table, label)) for flag, name, table, label in flags]
        registers = {row["register"] for _, _, row in rows}
        require(len(registers) == 1, f"ABB {selector} {point_id}: flags span registers {sorted(registers)}")
        register = registers.pop()
        if mcd:
            for _, _, row in rows:
                mcd_copy(row)
        points.append(configuration({
            "id": point_id,
            "address": register - 1,
            "type": "u16",
            "flags": {"flags": [{"bit": row["bit"], "name": flag, "description": name} for flag, name, row in rows]},
            "description": description,
            "source": {"address": str(register), "page": min(row["page"] for _, _, row in rows),
                       "reference": ", ".join(sorted({row["table"] for _, _, row in rows}))},
        }, [row for _, _, row in rows]))
    for point_id, models, name, label in MASK_BITS:
        if selector not in models:
            continue
        row = indication(name, None, label)
        points.append(configuration({
            "id": point_id,
            "address": row["register"] - 1,
            "type": "u16",
            "mask": 1 << row["bit"],
            "aliases": [name],
            "source": {"address": f"{row['register']}.{row['bit']:02d}", "page": row["page"],
                       "reference": row["table"]},
        }, [row]))
    for point_id, models, name, table in DISCRETE_BITS:
        if selector not in models:
            continue
        row = indication(name, table, None)
        points.append(configuration({
            "id": point_id,
            "table": "discrete_input",
            "address": row["bit_address"] - 1,
            "type": "bool",
            "aliases": [name],
            "description": "Circuit breaker closed, read as a 1X bit; the same bit is mirrored in the indication "
                           "registers.",
            "source": {"address": str(row["bit_address"]), "page": row["page"],
                       "reference": f"{row['table']}, {'BitA' if model['layout'] == 'ansi' else 'Bit addr'}"},
        }, [row]))
    return sorted(points, key=lambda point: (point.get("table", ""), point["address"], point.get("mask", 0)))
