"""Schneider Electric Altivar 61 and Altivar 71 communication-parameter workbooks (XLSX): status and actual values.

The selector names the workbook: atv61 or atv71 (attachments of Schneider FAQ FA225538). These older
workbooks keep their explanatory note in a drawing on the Instructions sheet and name neither the drive
nor a document number. Cells are read as cached values only. The "Logic address" column gives the address
for Modbus messaging in hexadecimal and decimal (explanatory note); both forms must agree.

Two documents are pinned as evidence for each drive:

- its Communication parameters manual. The title page names the drive and the software version, the manual
  says that all parameters are grouped in an Excel file supplied as an appendix, and it describes the
  monitoring parameters one by one. Every selected parameter that the manual describes must have the same
  logic address, type and access there. The manual also gives the unit where the workbook refers to
  another manual (motor current). Both documents give the order of the two registers of a 32-bit
  parameter: the workbook marks the addresses (lsb) and (msb), the manual says "low order" and "high order".
- a Modbus manual whose title page names the drive: the Altivar 71 Integrated Modbus manual for atv71, the
  Altivar 61/71 Modbus TCP/IP Ethernet card manual for atv61 (the Integrated Modbus manual names only the
  Altivar 71). Its table of Modbus functions must have Read Holding Registers (3) as the only read function
  and gives the register limit per read. The Integrated Modbus manual also carries a worked request frame
  in which the logic address is the address field.
"""
import re
from xml.etree import ElementTree

from sourcelib import pdf_page_count, pdf_pages, require, xlsx_rows, zip_member, zip_names

# selector: drive name, (evidence id, manual number, software version) of the Communication parameters
# manual, (evidence id, kind) of the Modbus manual
DRIVES = {
    "atv61": ("Altivar 61", ("schneider-electric-atv61-comm-manual", "1760661", "Software V5.8"),
              ("schneider-electric-atv61-71-ethernet-manual", "ethernet")),
    "atv71": ("Altivar 71", ("schneider-electric-atv71-comm-manual", "1755861", "Software V5.7"),
              ("schneider-electric-atv71-modbus-manual", "integrated")),
}
# kind: (title page phrases, sentence that introduces the function table)
MODBUS_MANUALS = {
    "integrated": (("Altivar 71", "Integrated Modbus", "1755863"),
                   "The following table indicates which Modbus functions are managed by the Altivar 71"),
    "ethernet": (("Altivar 61/71", "Modbus TCP/IP", "Ethernet card", "VW3 A3 310", "1755879"),
                 "List of Modbus functions supported"),
}
HEADER = {"A": "Code", "B": "Name", "C": "Logic address", "E": "INTERBUS index", "G": "Link", "I": "Access",
          "J": "Type", "K": "Units", "M": "Range"}
NOTE = ("Logic address: Address for the Modbus messaging (RS485 and Ethernet TCI/IP) and the PKW indexed periodic "
        "variables (Fipio, Profibus DP), in decimal and hexadecimal (preceded by 16#) format.")
DEFERRED = "Refer to programming manual"
# workbook type: (contract type, type in the Communication parameters manual)
TYPES = {"INT (Signed16)": ("i16", "INT"), "UINT (Unsigned16)": ("u16", "UINT"), "UDINT": ("u32", "UDINT"),
         "WORD (BitString16)": ("u16", "WORD (bit register)"), "WORD (Enumeration)": ("u16", "WORD (listing)")}
UNITS = {"Hz": "Hz", "rpm": "/min", "A": "A", "V": "V", "%": "%"}
EXPONENTS = {"1": 0, "0.1": -1, "0.01": -2, "0.001": -3}
SCALED = re.compile(r"(1|0\.1|0\.01|0\.001) ?(\S+)")

# code: (point id, workbook type, workbook unit, described in the Communication parameters manual)
SELECTED = {
    "ETA": ("status_word", "WORD (BitString16)", "-", True),
    "HMIS": ("drive_state", "WORD (Enumeration)", "-", False),
    "RFR": ("output_frequency", "INT (Signed16)", "0.1 Hz", True),
    "RFRD": ("output_speed", "INT (Signed16)", "1 rpm", True),
    "LCR": ("motor_current", "UINT (Unsigned16)", DEFERRED, True),
    "UOP": ("motor_voltage", "UINT (Unsigned16)", "1 V", True),
    "OPR": ("motor_power", "INT (Signed16)", "1 %", True),
    "ULN": ("mains_voltage", "UINT (Unsigned16)", "0.1 V", True),
    "THD": ("drive_thermal_state", "UINT (Unsigned16)", "1 %", True),
    "THR": ("motor_thermal_state", "UINT (Unsigned16)", "1 %", True),
    "LFT": ("last_fault", "WORD (Enumeration)", "-", True),
    "SPAL": ("acceleration_delta_speed", "UDINT", "1 rpm", True),
}
# Workbook access of the selected parameters. SPAL is a CiA402 setting (R/W); this contract only reads it.
ACCESS = {"SPAL": "R/W"}
# ETA bits, CiA402 profile: bit -> (flag name, phrase the workbook text must contain)
ETA_FLAGS = {
    0: ("ready_to_switch_on", "Ready to switch on"),
    1: ("switched_on", "Switched on"),
    2: ("operation_enabled", "Operation enabled"),
    3: ("fault", "= 1: Fault"),
    4: ("voltage_enabled", "Voltage enabled"),
    6: ("switch_on_disabled", "Switched on disabled"),
    7: ("warning", "= 1: Alarm"),
    9: ("remote", "= 1: Command or reference via the network"),
    10: ("target_reached", "= 1: The reference has been reached"),
    11: ("internal_limit_active", "Internal limit active"),
    14: ("stop_key", "= 1: Stop triggered by the STOP key"),
    15: ("reverse_rotation", "= 1: Reverse rotation at output"),
}
RESERVED_ETA_BITS = {8: "Reserved (= 0)", 12: "Reserved (= 0)", 13: "Reserved (= 0)"}
IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)*")
BLOCK = re.compile(r"(\w+) Parameter name: ")
FUNCTION = re.compile(r"(\d+) = 16#([0-9A-F]{2}) (\S.*)")
DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def flat(text):
    return " ".join(text.split())


def sheet(data, name):
    return list(xlsx_rows(data, name))


def check_workbook(data, selector):
    """The explanatory note is a drawing: it must define the logic address and the access codes."""
    drawings = [name for name in zip_names(data) if re.fullmatch(r"xl/drawings/drawing\d+\.xml", name)]
    require(len(drawings) == 1, f"Schneider {selector}: expected one drawing, found {drawings}")
    root = ElementTree.fromstring(zip_member(data, drawings[0]))
    texts = {flat("".join(run.text or "" for run in paragraph.iter(f"{DRAWING}t")))
             for paragraph in root.iter(f"{DRAWING}p")}
    require("EXPLANATORY NOTE" in texts and NOTE in texts, f"Schneider {selector}: logic address definition missing")
    require("R: Read only" in texts and "INT: Signed integer" in texts and "UINT: Unsigned integer" in texts,
            f"Schneider {selector}: access or type definition missing")


def parameter_rows(data, selector):
    rows = sheet(data, "Parameters")
    require(rows and rows[0][0] == 1, "Schneider Parameters sheet: header row missing")
    header = rows[0][1]
    require(all(header.get(column) == text for column, text in HEADER.items()),
            f"Schneider {selector}: unexpected Parameters header {header}")
    found = {}
    for number, row in rows[1:]:
        code = row.get("A")
        if code in SELECTED:
            require(code not in found, f"Schneider {selector}: duplicate parameter {code}")
            found[code] = (number, row)
    missing = SELECTED.keys() - found.keys()
    require(not missing, f"Schneider {selector}: missing parameters {sorted(missing)}")
    return found


def logic_addresses(text, code):
    """One address, or one per profile: {annotation or None: address}. Hex and decimal must agree."""
    pairs = re.findall(r"16#([0-9A-F]{4}) = (\d+)(?: \((\w+)\))?", text or "")
    rebuilt = " ".join(f"16#{high} = {number}" + (f" ({note})" if note else "") for high, number, note in pairs)
    require(pairs and rebuilt == text, f"Schneider {code}: unrecognised logic address {text!r}")
    for high, number, _ in pairs:
        require(int(high, 16) == int(number), f"Schneider {code}: hex and decimal addresses differ")
    addresses = {note or None: int(number) for _, number, note in pairs}
    require(len(addresses) == len(pairs), f"Schneider {code}: ambiguous logic address {text!r}")
    return addresses


def enumeration(data, list_id):
    values, active, first, last = [], False, None, None
    for number, row in sheet(data, "Enumerations"):
        if "A" in row:
            active = row["A"] == list_id
        if not active:
            continue
        first = first or number
        last = number
        match = re.fullmatch(r"\[(.+)\] \(([A-Za-z][A-Za-z0-9]*)\)", row.get("C", ""))
        require(re.fullmatch(r"\d+", row.get("B", "")) and match,
                f"Schneider enumeration {list_id}: unrecognised row {number}")
        name = match.group(2).lower()
        require(IDENTIFIER.fullmatch(name), f"Schneider enumeration {list_id}: bad name {name!r}")
        value = {"value": int(row["B"]), "name": name, "label": match.group(1)}
        if row.get("D"):
            value["description"] = row["D"]
        values.append(value)
    require(values, f"Schneider enumeration {list_id} missing")
    require(len({value["value"] for value in values}) == len(values), f"Schneider {list_id}: duplicate value")
    require(len({value["name"] for value in values}) == len(values), f"Schneider {list_id}: duplicate name")
    return values, f"Enumerations!A{first}:D{last}"


def register_bits(data, code, profile=None):
    """Bit texts of one Registers block. A block starts at a row whose column A lists the codes it covers
    and ends before the next such row; `profile` selects the part under that column B heading."""
    rows = sheet(data, "Registers")
    starts = [index for index, (_, row) in enumerate(rows) if code in row.get("A", "").split()]
    require(len(starts) == 1, f"Schneider Registers sheet: expected one block for {code}")
    block = [rows[starts[0]]]
    for entry in rows[starts[0] + 1:]:
        if "A" in entry[1]:
            break
        block.append(entry)
    if profile is not None:
        headings = [index for index, (_, row) in enumerate(block) if row.get("B", "").startswith("Possible values")]
        chosen = [index for index in headings if block[index][1]["B"] == profile]
        require(len(chosen) == 1, f"Schneider Registers {code}: profile {profile!r} not found once")
        later = [index for index in headings if index > chosen[0]]
        block = block[chosen[0]:later[0] if later else len(block)]
    bits, rows_of, current = {}, {}, None
    for number, row in block:
        match = re.fullmatch(r"bit (\d+) ?:", row.get("C", ""))
        if match:
            current = int(match.group(1))
            require(current not in bits, f"Schneider Registers {code}: bit {current} listed twice")
            bits[current], rows_of[current] = [], [number, number]
        else:
            require("C" not in row, f"Schneider Registers {code}: unrecognised bit label in row {number}")
        if current is not None and row.get("D"):
            bits[current].append(row["D"].replace("= 0: '", "= 0: ").replace("= 1: '", "= 1: "))
            rows_of[current][1] = number
    require(sorted(bits) == list(range(16)), f"Schneider Registers {code}: unexpected bit list {sorted(bits)}")
    return bits, rows_of, f"Registers!A{block[0][0]}:D{block[-1][0]}"


def eta_flags(data):
    bits, _, reference = register_bits(data, "ETA", "Possible values in CiA402 profile")
    for bit, text in RESERVED_ETA_BITS.items():
        require(bits[bit] == [text], f"Schneider ETA bit {bit}: expected {text!r}, found {bits[bit]}")
    flags = []
    for bit, (name, phrase) in sorted(ETA_FLAGS.items()):
        text = " ".join(bits[bit])
        require(phrase in text, f"Schneider ETA bit {bit}: expected {phrase!r} in {text!r}")
        flag = {"bit": bit, "name": name, "label": bits[bit][0]}
        if text != bits[bit][0]:
            flag["description"] = text
        flags.append(flag)
    return flags, reference


def frequency_unit_note(data):
    """CMI bit 9 selects the unit of the output frequency (rFr)."""
    bits, rows_of, _ = register_bits(data, "CMI")
    text = " ".join(bits[9])
    require("output frequency (rFr) unit" in text and "= 0: 0.1 Hz" in text
            and "32767 corresponds to [Max frequency] (tFr)" in text,
            f"Schneider CMI bit 9: unexpected text {text!r}")
    first, last = rows_of[9]
    return ("0.1 Hz while bit 9 of the extended control word CMI is 0. With CMI bit 9 at 1 the drive "
            "reports a standardised value where 32767 corresponds to [Max frequency] (tFr); this "
            "contract does not describe that mode."), f"Registers!C{first}:D{last}"


def evidence_pages(evidence, evidence_id, selector):
    require(evidence and evidence_id in evidence, f"Schneider {selector}: evidence {evidence_id} not supplied")
    data = evidence[evidence_id]
    return pdf_pages(data, 1, pdf_page_count(data))


def manual_blocks(evidence, selector):
    """Parameter descriptions of the Communication parameters manual: lower-case code -> block texts.

    A description starts with the parameter code followed by "Parameter name:" and runs to the next one.
    The text is whitespace-normalised, so the parsing does not depend on column positions."""
    name, (evidence_id, number, software), _ = DRIVES[selector]
    pages = evidence_pages(evidence, evidence_id, selector)
    cover = flat(pages[0])
    require(all(phrase in cover for phrase in (name, "Communication parameters", software, number)),
            f"Schneider {selector}: unexpected Communication parameters manual {cover[:120]!r}")
    text = flat(" ".join(pages))
    require(re.search(r"Logic address: Address for (?:the )?Modbus messaging \(RS485 and Ethernet TCI/IP\)", text),
            f"Schneider {selector}: manual does not define the logic address")
    require("All the parameters are grouped together in an Excel file supplied as an appendix" in text,
            f"Schneider {selector}: manual does not mention the parameter workbook")
    starts = list(BLOCK.finditer(text))
    blocks = {}
    for match, end in zip(starts, [*(later.start() for later in starts[1:]), len(text)]):
        blocks.setdefault(match.group(1).lower(), []).append(text[match.start():end])
    return blocks


def manual_parameter(blocks, selector, code):
    """Logic addresses, type, access and unit text of one parameter in the Communication parameters manual."""
    found = blocks.get(code.lower(), [])
    require(len(found) == 1, f"Schneider {selector}: manual describes {code} {len(found)} times")
    match = re.search(r"Logic address: (.*?) CANopen index:", found[0])
    require(match, f"Schneider {selector}: manual gives no logic address for {code}")
    pairs = re.findall(r"(\d+) = 16#([0-9A-F]+)", match.group(1))
    require(pairs and all(int(number) == int(high, 16) for number, high in pairs),
            f"Schneider {selector}: manual logic address of {code} unreadable or inconsistent")
    kind = re.search(r"Type: (WORD \(bit register\)|WORD \(listing\)|UDINT|UINT|INT)(?= |$)", match.group(1))
    access = re.search(r"Read/write: (\S+)", found[0])
    require(kind and access, f"Schneider {selector}: manual gives no type or access for {code}")
    unit = re.search(r"Unit: (.+?) DeviceNet path:", found[0])
    order = re.search(r"32-bit word \(low order: (\d+), high order: (\d+)\)", found[0])
    return ({int(number) for number, _ in pairs}, kind.group(1), access.group(1), unit.group(1) if unit else None,
            (int(order.group(1)), int(order.group(2))) if order else None)


def function_rows(page, heading):
    """Rows "<code> = 16#<hex> <names and limit>" that follow the heading on its page: code -> rest."""
    rows = {}
    for line in page.split(heading, 1)[1].splitlines():
        match = FUNCTION.fullmatch(flat(line))
        if not match:
            continue
        code = int(match.group(1))
        require(int(match.group(2), 16) == code, f"Schneider Modbus manual: function {code} hex code disagrees")
        require(code not in rows, f"Schneider Modbus manual: function {code} listed twice")
        rows[code] = match.group(3)
    return rows


def read_function(evidence, selector):
    """Check the pinned Modbus manual: function 3 is the only read function; return the register limit."""
    evidence_id, kind = DRIVES[selector][2]
    phrases, heading = MODBUS_MANUALS[kind]
    pages = evidence_pages(evidence, evidence_id, selector)
    cover = flat(pages[0])
    require(all(phrase in cover for phrase in phrases),
            f"Schneider {selector}: unexpected Modbus manual {cover[:120]!r}")
    tables = [page for page in pages if heading in page and FUNCTION.search(flat(page.split(heading, 1)[1]))]
    require(len(tables) == 1, f"Schneider {selector}: expected one table of Modbus functions, found {len(tables)}")
    rows = function_rows(tables[0], heading)
    match = re.fullmatch(r"Read Holding Registers Read N output words (?:NO )?(\d+) words max\.", rows.get(3, ""))
    require(match, f"Schneider {selector}: function 3 row {rows.get(3)!r}")
    require(not {1, 2, 4} & rows.keys() and {6, 16, 23} <= rows.keys(),
            f"Schneider {selector}: unexpected function list {sorted(rows)}")
    text = flat(tables[0])
    if kind == "integrated":
        require("This function can be used to read the ATV 71 parameters, regardless of type." in text,
                f"Schneider {selector}: function 3 scope statement missing")
        example = re.search(r"Use function 3 to read 4 words W3 102 to W3 105 \(16#([0-9A-F]{4}) to "
                            r"16#([0-9A-F]{4})\) on slave 2", text)
        frame = re.search(r"Request 02 03 ([0-9A-F]{4}) 0004 [0-9A-F]{4} Response", text)
        require(example and frame and int(example.group(1), 16) == 3102 and int(example.group(2), 16) == 3105
                and frame.group(1) == example.group(1),
                f"Schneider {selector}: worked request frame does not carry the logic address")
    else:
        servers = flat(" ".join(pages))
        require(re.search(r"Unit ID Modbus TCP server Accessible parameters 0 Variable speed drive", servers),
                f"Schneider {selector}: Modbus TCP server table does not list the drive")
    return int(match.group(1))


def spaceless(text):
    return "".join(text.split())


def extract(data, selector, evidence=None):
    require(selector in DRIVES, f"Unknown Schneider workbook selector {selector!r}")
    check_workbook(data, selector)
    limit = read_function(evidence, selector)
    blocks = manual_blocks(evidence, selector)
    points = []
    for code, (number, row) in parameter_rows(data, selector).items():
        point_id, kind, units, described = SELECTED[code]
        allowed = ACCESS.get(code, "R")
        require(row.get("J") == kind and row.get("K") == units and row.get("I") == allowed,
                f"Schneider {code}: unexpected type, units or access {row}")
        addresses = logic_addresses(row.get("C"), code)
        contract_type, manual_type = TYPES[kind]
        manual_unit = manual_order = None
        if described:
            manual_addresses, found_type, access, manual_unit, manual_order = manual_parameter(blocks, selector, code)
            require(manual_addresses == set(addresses.values()) and found_type == manual_type and access == allowed,
                    f"Schneider {selector} {code}: workbook and Communication parameters manual disagree "
                    f"({sorted(manual_addresses)}, {found_type}, {access})")
        else:
            require(code.lower() not in blocks, f"Schneider {selector}: manual now describes {code}; cross-check it")
        if kind == "WORD (BitString16)":
            require(code == "ETA" and set(addresses) == {"speed", "frequency"},
                    f"Schneider {code}: unexpected bit register or addresses {addresses}")
            address = addresses["frequency"]
        elif kind == "UDINT":
            require(set(addresses) == {"lsb", "msb"} and addresses["msb"] == addresses["lsb"] + 1
                    and manual_order == (addresses["lsb"], addresses["msb"]),
                    f"Schneider {selector} {code}: 32-bit register order not stated as expected "
                    f"({addresses}, {manual_order})")
            address = addresses["lsb"]
        else:
            require(set(addresses) == {None}, f"Schneider {code}: unexpected logic address {row.get('C')!r}")
            address = addresses[None]
        point = {"id": point_id, "label": row["B"], "aliases": [code], "address": address, "type": contract_type}
        if kind == "UDINT":
            point["wordOrder"] = "little"
        reference = f"Parameters!A{number}:M{number}"
        if kind == "WORD (BitString16)":
            flags, bit_reference = eta_flags(data)
            point["flags"] = {"flags": flags}
            point["description"] = ("Bit meanings for the CiA402 profile. Read here next to the output frequency; "
                                    f"the workbook lists the same word at {addresses['speed']}, next to the output "
                                    "speed.")
            reference += "; " + bit_reference
        if kind == "WORD (Enumeration)":
            require(row.get("G") == code, f"Schneider {code}: unexpected enumeration link {row.get('G')!r}")
            values, enum_reference = enumeration(data, row["G"])
            point["enum"] = {"values": values}
            reference += "; " + enum_reference
        elif kind != "WORD (BitString16)":
            if units == DEFERRED:
                require(manual_unit, f"Schneider {selector} {code}: no unit in the Communication parameters manual")
                match = SCALED.fullmatch(manual_unit)
            else:
                match = SCALED.fullmatch(units)
                expected = spaceless(units)
                require(manual_unit is None or spaceless(manual_unit) == expected
                        or (expected.startswith("1") and spaceless(manual_unit) == expected[1:])
                        or (code == "RFR" and spaceless(manual_unit).startswith(expected + "orstandardized")),
                        f"Schneider {selector} {code}: unit {units!r} differs from the manual's {manual_unit!r}")
            require(match and match.group(2) in UNITS, f"Schneider {code}: unrecognised units {units!r}")
            exponent = EXPONENTS[match.group(1)]
            if exponent:
                point["conversion"] = {"exponent10": exponent}
            point["unit"] = UNITS[match.group(2)]
            if units == DEFERRED:
                point["description"] = (f"The workbook gives no unit; {manual_unit} is the unit in the "
                                        f"{DRIVES[selector][0]} Communication parameters manual.")
            if code == "RFR":
                point["description"], note_reference = frequency_unit_note(data)
                reference += "; " + note_reference
            if kind == "UDINT":
                point["description"] = (f"Low-order word at {addresses['lsb']}, high-order word at "
                                        f"{addresses['msb']}. Workbook access {allowed}: the drive also accepts "
                                        "writes.")
            if code == "ULN":
                require(row.get("M") == "[No meas.] (----) ... 6553.5 V", f"Schneider ULN: unexpected range {row}")
                point["description"] = ("The workbook's range starts at [No meas.] (----); it does not give the "
                                        "register value that stands for it.")
        point["source"] = {"address": row["C"], "reference": reference}
        points.append(point)
    return {"points": sorted(points, key=lambda point: point["address"]),
            "constraints": {"maxReadRegisters": limit}}
