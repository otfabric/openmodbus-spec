"""Schneider Electric Altivar communication-parameter workbooks (XLSX): status and actual values.

The selector names the workbook: atv320 (NVE41316), atv340 (NVE61728) or atv600 (EAV64332).
Cells are read as cached values only. The "Logic address" column gives the address used in Modbus
messaging, in hexadecimal and decimal (Instructions sheet); both forms must agree. The table comes from
the drive's Modbus serial link manual, pinned as evidence: its list of supported Modbus functions has
Read Holding Registers (3) as the only read function, and the manual names the workbook as a related
document. The same request table gives the register limit per read. The ATV600 workbook names no drive
model; the ATV600 programming manual, pinned as evidence, names the models and the workbook.
"""
import re

from sourcelib import pdf_page_count, pdf_pages, require, xlsx_rows

WORKBOOKS = {
    "atv320": ("NVE41316", "V3.5", "ATV320 - Communication Parameters"),
    "atv340": ("NVE61728", "v4.6", "ATV340 - Communication Parameters"),
    "atv600": ("EAV64332", "V4.6", "ATV600 - Communication Parameters"),
}
# selector: (evidence id, manual reference on the title page, manual title on the title page)
MANUALS = {
    "atv320": ("schneider-electric-atv320-modbus-manual", "NVE41308", "Modbus Serial Link Manual"),
    "atv340": ("schneider-electric-atv340-modbus-manual", "NVE61654", "Modbus Serial Line Manual"),
    "atv600": ("schneider-electric-atv600-modbus-manual", "EAV64325", "Modbus Serial Link Manual (Embedded)"),
}
# selector: (evidence id, manual reference, model the contract describes) where the workbook names no model
SCOPE = {"atv600": ("schneider-electric-atv600-programming-manual", "EAV64318", "ATV630")}
FUNCTION_ROW = re.compile(r"^\s+(\S.*?)\s+(\d\d)\s+([0-9A-F]{2}) hex\s+(\S.*?)(?:\s{2,}|$)")
HEADER = {"A": "Code", "B": "Name", "C": "Logic address", "F": "Link", "H": "Access", "I": "Type",
          "J": "Units", "L": "Range"}
TYPES = {"INT (Signed16)": "i16", "UINT (Unsigned16)": "u16", "WORD (BitString16)": "u16",
         "WORD (Enumeration)": "u16"}
UNITS = {"Hz": "Hz", "rpm": "/min", "A": "A", "V": "V", "%": "%", "Wh": "W.h", "kWh": "kW.h",
         "MWh": "MW.h", "GWh": "GW.h", "TWh": "TW.h"}
EXPONENTS = {"1": 0, "0.1": -1, "0.01": -2, "0.001": -3}

# code: (point id, workbook type, workbook unit, allowed access)
COMMON = {
    "ETA": ("status_word", "WORD (BitString16)", "-", "R"),
    "HMIS": ("drive_state", "WORD (Enumeration)", "-", "R"),
    "RFR": ("output_frequency", "INT (Signed16)", "0.1 Hz", "R"),
    "RFRD": ("output_speed", "INT (Signed16)", "1 rpm", "R"),
    "OTR": ("motor_torque", "INT (Signed16)", "0.1 %", "R"),
    "UOP": ("motor_voltage", "UINT (Unsigned16)", "1 V", "R"),
    "OPR": ("motor_power", "INT (Signed16)", "1 %", "R"),
    "ULN": ("mains_voltage", "UINT (Unsigned16)", "0.1 V", "R"),
    "THD": ("drive_thermal_state", "UINT (Unsigned16)", "1 %", "R"),
    "LFT": ("last_fault", "WORD (Enumeration)", "-", "R"),
}
CURRENT = {"LCR": ("motor_current", "UINT (Unsigned16)", "0.1 A", "R")}
# Input energy is split over five registers, one per decade of 1000 (range 0 ... 999 each).
# The counters are resettable (R/WS); this contract only reads them.
ENERGY = {
    "VBUS": ("dc_bus_voltage", "UINT (Unsigned16)", "0.1 V", "R"),
    "IC0": ("input_energy_wh", "UINT (Unsigned16)", "1 Wh", "R/WS"),
    "IC1": ("input_energy_kwh", "UINT (Unsigned16)", "1 kWh", "R/WS"),
    "IC2": ("input_energy_mwh", "UINT (Unsigned16)", "1 MWh", "R/WS"),
    "IC3": ("input_energy_gwh", "UINT (Unsigned16)", "1 GWh", "R/WS"),
    "IC4": ("input_energy_twh", "UINT (Unsigned16)", "1 TWh", "R/WS"),
}
SELECTED = {
    "atv320": {**COMMON, **CURRENT},
    "atv340": {**COMMON, **ENERGY},
    "atv600": {**COMMON, **ENERGY},
}
# ETA bits, CiA402 profile: bit -> (flag name, phrase the workbook text must contain)
ETA_FLAGS = {
    0: ("ready_to_switch_on", '"Ready to switch on"'),
    1: ("switched_on", '"Switched on"'),
    2: ("operation_enabled", '"Operation enabled"'),
    3: ("fault", "Fault detection"),
    4: ("voltage_enabled", '"Voltage enabled"'),
    6: ("switch_on_disabled", '"Switched on disabled"'),
    7: ("warning", "= 1: Warning active"),
    9: ("remote", "= 1: Command or reference via fieldbus"),
    10: ("target_reached", "= 1: The reference has been reached"),
    11: ("internal_limit_active", '"Internal limit active"'),
    14: ("stop_key", "= 1: Stop triggered by the STOP key"),
    15: ("reverse_rotation", "= 1: Reverse rotation at output"),
}
IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)*")


def sheet(data, name):
    return list(xlsx_rows(data, name))


def check_workbook(data, selector):
    code, version, title = WORKBOOKS[selector]
    rows = dict(sheet(data, "Instructions"))
    require(rows[1].get("A") == code and rows[1].get("C") == version and rows[1].get("D") == title,
            f"Schneider {selector}: unexpected workbook identity {rows[1]}")
    texts = [row.get("A", "") for row in rows.values()]
    require("Logic address:" in texts and "Addresses for Modbus, Profibus, Profinet and Ethernet TCP" in texts,
            f"Schneider {selector}: logic address definition missing")
    require("Address for the messaging are in decimal and hexadecimal (preceded by 16#) format." in texts,
            f"Schneider {selector}: address format statement missing")
    require("R/W: Read and write" in texts, f"Schneider {selector}: access definition missing")


def parameter_rows(data, selector):
    rows = sheet(data, "Parameters")
    require(rows and rows[0][0] == 1, "Schneider Parameters sheet: header row missing")
    header = rows[0][1]
    require(all(header.get(column) == text for column, text in HEADER.items()),
            f"Schneider {selector}: unexpected Parameters header {header}")
    found = {}
    for number, row in rows[1:]:
        code = row.get("A")
        if code in SELECTED[selector]:
            require(code not in found, f"Schneider {selector}: duplicate parameter {code}")
            found[code] = (number, row)
    missing = SELECTED[selector].keys() - found.keys()
    require(not missing, f"Schneider {selector}: missing parameters {sorted(missing)}")
    return found


def logic_address(text, code):
    match = re.fullmatch(r"16#([0-9A-F]{4}) = (\d+)", text or "")
    require(match, f"Schneider {code}: unrecognised logic address {text!r}")
    require(int(match.group(1), 16) == int(match.group(2)), f"Schneider {code}: hex and decimal addresses differ")
    return int(match.group(2))


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


def register_bits(data, start, end):
    """Bit texts of one Registers block: from the row matching start to the row before end."""
    rows = sheet(data, "Registers")
    starts = [index for index, (_, row) in enumerate(rows) if start(row)]
    require(len(starts) == 1, "Schneider Registers sheet: expected one matching bit block")
    bits, rows_of, current, last = {}, {}, None, None
    for number, row in rows[starts[0]:]:
        if number != rows[starts[0]][0] and end(row):
            break
        last = number
        match = re.fullmatch(r"Bit (\d+)", row.get("C", ""))
        if match:
            current = int(match.group(1))
            require(current not in bits, f"Schneider Registers: bit {current} listed twice")
            bits[current], rows_of[current] = [], [number, number]
        if current is not None and row.get("D"):
            bits[current].append(re.sub(rf"^Bit {current}: ", "", row["D"]))
            rows_of[current][1] = number
    require(sorted(bits) == list(range(16)), f"Schneider Registers: unexpected bit list {sorted(bits)}")
    return bits, rows_of, f"Registers!A{rows[starts[0]][0]}:D{last}"


def eta_flags(data):
    bits, _, reference = register_bits(
        data,
        lambda row: row.get("A") == "ETA" and row.get("B", "").startswith("Possible values in CiA402 profile"),
        lambda row: row.get("A") == "ETI" and row.get("C") == "Bit 0")
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
    bits, rows_of, _ = register_bits(
        data,
        lambda row: row.get("A") == "CMI" and row.get("C") == "Bit 0",
        lambda row: row.get("A") == "CMD")
    text = " ".join(bits[9])
    require("output frequency (rFr) unit" in text and "= 0: 0.1 Hz" in text
            and "32767 corresponds to [Max frequency] (tFr)" in text,
            f"Schneider CMI bit 9: unexpected text {text!r}")
    first, last = rows_of[9]
    return ("0.1 Hz while bit 9 of the extended control word CMI is 0. With CMI bit 9 at 1 the drive "
            "reports a standardised value where 32767 corresponds to [Max frequency] (tFr); this "
            "contract does not describe that mode."), f"Registers!C{first}:D{last}"


def flat(text):
    return " ".join(text.split())


def function_table(page):
    """Rows of one "Supported Modbus Functions" table: code -> (name, description)."""
    lines = page.split("The drive supports the following Modbus functions:", 1)[1].splitlines()
    rows = {}
    for index, line in enumerate(lines):
        match = FUNCTION_ROW.match(line)
        if not match:
            continue
        name, code, description = match.group(1), int(match.group(2)), match.group(4)
        require(int(match.group(3), 16) == code, f"Schneider Modbus manual: function {code} hex code disagrees")
        following = lines[index + 1].split() if index + 1 < len(lines) else []
        if name.startswith("Read Holding") and not name.endswith("Registers"):
            require(following[:1] == ["Registers"], "Schneider Modbus manual: function 3 name cut off")
            name += " Registers"
        require(code not in rows, f"Schneider Modbus manual: function {code} listed twice")
        rows[code] = (name, description)
    return rows


def read_function(evidence, selector):
    """Check the pinned Modbus manual: function 3 is the only read function; return the register limit."""
    evidence_id, reference, title = MANUALS[selector]
    require(evidence and evidence_id in evidence, f"Schneider {selector}: evidence {evidence_id} not supplied")
    data = evidence[evidence_id]
    pages = pdf_pages(data, 1, pdf_page_count(data))
    cover = flat(pages[0])
    require(reference in cover and title in cover, f"Schneider {selector}: unexpected manual {cover[:120]!r}")
    workbook = WORKBOOKS[selector][0]
    require(any(re.search(rf"Communication Parameters\s+{workbook}\b", page) for page in pages),
            f"Schneider {selector}: manual does not list workbook {workbook}")
    tables = [function_table(page) for page in pages if "The drive supports the following Modbus functions:" in page]
    require(tables, f"Schneider {selector}: supported Modbus functions table missing")
    for rows in tables:
        require(rows.get(3) == ("Read Holding Registers", "Read N output words"),
                f"Schneider {selector}: function 3 row {rows.get(3)!r}")
        require(not {1, 2, 4} & rows.keys() and {6, 16, 23} <= rows.keys(),
                f"Schneider {selector}: unexpected function list {sorted(rows)}")
    limits = set()
    for page in pages:
        text = flat(page)
        for match in re.finditer(r"Read Holding Registers Request Function code 1 byte 03 hex Starting address "
                                 r"2 bytes 0000 hex\.\.\.FFFF hex Quantity of registers 2 bytes 1\.\.\.(\d+) "
                                 r"\(([0-9A-F]+) hex\)", text):
            require(int(match.group(1)) == int(match.group(2), 16), f"Schneider {selector}: register limit disagrees")
            limits.add(int(match.group(1)))
    require(len(limits) == 1, f"Schneider {selector}: register limits {sorted(limits)}")
    return limits.pop()


def check_scope(evidence, selector):
    """The programming manual's validity note names the model; its related documents name the workbook."""
    if selector not in SCOPE:
        return
    evidence_id, reference, model = SCOPE[selector]
    require(evidence and evidence_id in evidence, f"Schneider {selector}: evidence {evidence_id} not supplied")
    text = flat("\n".join(pdf_pages(evidence[evidence_id], 1, 20)))
    require(f"Programming Manual {reference}" in text, f"Schneider {selector}: unexpected programming manual")
    match = re.search(r"This documentation is valid for the Altivar Process \(([^)]*)\) drives\.", text)
    require(match and model in [name.strip() for name in match.group(1).split(",")],
            f"Schneider {selector}: validity note does not name {model}")
    workbook = WORKBOOKS[selector][0]
    require(re.search(rf"Communication Parameters {workbook}\b", text),
            f"Schneider {selector}: programming manual does not list workbook {workbook}")


def extract(data, selector, evidence=None):
    require(selector in WORKBOOKS, f"Unknown Schneider workbook selector {selector!r}")
    check_workbook(data, selector)
    limit = read_function(evidence, selector)
    check_scope(evidence, selector)
    points = []
    for code, (number, row) in parameter_rows(data, selector).items():
        point_id, kind, units, access = SELECTED[selector][code]
        require(row.get("I") == kind and row.get("J") == units and row.get("H") == access,
                f"Schneider {code}: unexpected type, units or access {row}")
        address = logic_address(row.get("C"), code)
        point = {"id": point_id, "label": row["B"], "aliases": [code], "address": address,
                 "type": TYPES[kind]}
        reference = f"Parameters!A{number}:L{number}"
        if kind == "WORD (BitString16)":
            require(code == "ETA", f"Schneider {code}: no bit list selected")
            flags, bit_reference = eta_flags(data)
            point["flags"] = {"flags": flags}
            point["description"] = "Bit meanings for the CiA402 profile."
            reference += "; " + bit_reference
        elif kind == "WORD (Enumeration)":
            require(row.get("F") == code, f"Schneider {code}: unexpected enumeration link {row.get('F')!r}")
            values, enum_reference = enumeration(data, row["F"])
            point["enum"] = {"values": values}
            reference += "; " + enum_reference
        else:
            match = re.fullmatch(r"(1|0\.1|0\.01|0\.001) (\S+)", units)
            require(match and match.group(2) in UNITS, f"Schneider {code}: unrecognised units {units!r}")
            exponent = EXPONENTS[match.group(1)]
            if exponent:
                point["conversion"] = {"exponent10": exponent}
            point["unit"] = UNITS[match.group(2)]
            if code == "RFR":
                point["description"], note_reference = frequency_unit_note(data)
                reference += "; " + note_reference
            if access != "R":
                point["description"] = (f"Workbook access {access}: the drive also accepts writes. "
                                        "Input energy is split over IC0 to IC4, each 0 ... 999.")
        point["source"] = {"address": row["C"], "reference": reference}
        points.append(point)
    return {"points": sorted(points, key=lambda point: point["address"]),
            "constraints": {"maxReadRegisters": limit}}
