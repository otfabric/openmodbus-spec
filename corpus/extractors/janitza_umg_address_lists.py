"""Janitza UMG 509-PRO, UMG 604-PRO and UMG 96-PA Modbus address lists: selected measurements.

Selectors:

- "umg509-pro": "UMG 509-PRO Modbus-address and Formulary" (PDF, Dok. Nr. 1.059.004.2.o). Rows carry
  address, format, RD/WR, designation, unit and note.
- "umg604-pro": "UMG 604-PRO Modbus-address and Formulary" (PDF, Doc. no. 1.033.034.h, firmware 5.030
  or later). Rows carry address, format, designation, unit and remarks; there is no RD/WR column.
- "umg96-pa": the UMG 96-PA / UMG 96-PAMID+ archive (ZIP, firmware 3.54 or later). Rows are read from
  the English sheet of the workbook (Doc. No. 2.061.164.1.a); the conventions are read from the PDF
  in the same archive (Doc. no. 2.061.029.3.e), and every selected row must also stand in that PDF
  with the same address, type and access right.

Rows are selected by the vendor's designation (or, in the workbook, category and description) and
their address, format and unit are parsed. Each list states that the listed addresses return
big-endian data, defines its number formats, says that short values exclude the transformer ratios,
and lists the slave functions 03 Read Holding Registers, 04 Read Input Registers and the
holding-register writes 06 and 16. All of these are required.

None of the lists states the address base or the register table. For the UMG 509-PRO and the
UMG 96-PA both come from the device's user manual, pinned as evidence: its example "Reading the
voltage L1-N" sends function 03 "Read Holding Reg" with the start address bytes 4A 38 for the
list address 19000 and asks for two values. The extractor parses that request, requires that the
bytes equal the stated list address, and requires that the list's row at that address is the L1-N
voltage float. The UMG 604-PRO manual has no such example. Its list is read as zero-based because
it contains address 0, and as holding registers because rows marked "(r/w)" and "(r)" share it; both
rows are required.

Each manual also states the Modbus interfaces of the device (RS-485 Modbus RTU; for the UMG 509-PRO
and UMG 604-PRO also Modbus/TCP and Modbus RTU over Ethernet). The contracts' transports rest on
those statements, which are required; the UMG 604-PRO manual is pinned for them alone.
"""
import re

from sourcelib import pdf_page_count, pdf_pages, require, xlsx_rows, xlsx_sheets, zip_member, zip_names

STATEMENTS = {
    "big_endian": "The addresses described in this address list supply the data in the „Big-Endian“ format.",
    "little_endian_mirror": "If you require the data in the „Little-Endian“ format, you must add the value 32768 "
                            "to the address.",
    "short_unscaled": "Measured values in the short format do not take into account the set transformer ratio",
    "float_scaled": "Measured values in float or integer format take into account the corresponding transformer "
                    "factors!",
}
# Number formats as the lists' "Number formats" table defines them: name, size, start of the minimum.
FORMATS = {
    "short": (r"\bshort 16 bit -2", "i16"),
    "ushort": (r"\bushort 16 bit 0 ", "u16"),
    "int": (r"\bint 32 bit -2", "i32"),
    "uint": (r"\buint 32 bit 0 ", "u32"),
    "float": (r"\bfloat 32 bit IEEE 754", "f32"),
    "double": (r"\bdouble\.? 64 bit IEEE 754", "f64"),
}
# The slave function list, in document order.
FUNCTIONS = [
    "03 Read Holding Registers Reads the binary contents of holding registers (4X references) in the slave.",
    "04 Read Input Registers Reads the binary contents of input registers (3X references) in the slave.",
    "06 Preset Single Register Presets a value into a single holding register (4X reference).",
    "16 (10Hex) Preset Multiple Registers Presets values into a sequence of holding registers (4X references).",
]
SHORT_FACTORS = "short (x10) (x100) (x1000) The measured values have been multiplied by the specified factor in " \
                "order to make better use of the short number format. Values in x100 must therefore still be " \
                "divided by 100."
UNITS = {"V": "V", "A": "A", "W": "W", "VA": "V.A", "Hz": "Hz", "%": "%", "Wh": "W.h", "sec": "s", "°C": "Cel"}
NOT_UCUM = {"var": "Vendor unit: var."}
NO_UNIT = {"-", "n"}  # the 604-PRO list writes "-" or "n" (a number) where a value has no unit

QUOTE = "[\"“”„]"
EXAMPLE = re.compile(
    r"Example: Reading the voltage L1-N The voltage L1-N is stored in the (?:parameter and measured value list at|"
    r"measurement list under the) address (\d+)(?: in the FLOAT format\.|\. The voltage L1-N is in the FLOAT "
    rf"format\.) In this example 01 is assumed as the device address\. The {QUOTE}Query Message{QUOTE} then looks "
    rf"as follows: (.{{40,400}}?) The {QUOTE}response{QUOTE} of the device")
EXAMPLE_FIELDS = {
    "function": rf"Function 03 {QUOTE}Read Holding Reg{QUOTE}",
    "high": r"Start address Hi ([0-9A-F]{2})\b",
    "low": r"Start address Lo ([0-9A-F]{2})\b",
    "address": r"\b(\d+)dec = ([0-9A-F]{4})hex",
    "count_high": r"No\. of values Hi ([0-9A-F]{2})\b",
    "count_low": r"No\. of values Lo ([0-9A-F]{2})\b",
}

# The 19000 block every list calls "Frequently required readings" / "measured values":
# designation suffix -> (point id, unit, note per document layout)
FREQUENT_509 = {
    "_G_ULN[0]": ("voltage_l1_n", "V", "Voltage L1-N"),
    "_G_ULN[1]": ("voltage_l2_n", "V", "Voltage L2-N"),
    "_G_ULN[2]": ("voltage_l3_n", "V", "Voltage L3-N"),
    "_G_ULL[0]": ("voltage_l1_l2", "V", "Voltage L1-L2"),
    "_G_ILN[0]": ("current_l1", "A", "Apparent current, L1"),
    "_G_ILN[1]": ("current_l2", "A", "Apparent current, L2"),
    "_G_ILN[2]": ("current_l3", "A", "Apparent current, L3"),
    "_G_P_SUM3": ("active_power_total", "W", "Sum; Psum3=P1+P2+P3"),
    "_G_S_SUM3": ("apparent_power_total", "VA", "Sum; Ssum3=S1+S2+S3"),
    "_G_Q_SUM3": ("reactive_power_total", "var", "Sum; Qsum3=Q1+Q2+Q3"),
    "_G_FREQ": ("frequency", "Hz", "Measured frequency"),
    "_G_THD_ULN[0]": ("voltage_thd_l1_n", "%", "Harmonic, THD,U L1-N"),
    "_G_THD_ILN[0]": ("current_thd_l1", "%", "Harmonic, THD,I L1"),
}
FREQUENT_604 = {
    "_G_ULN[0]": ("voltage_l1_n", "V", "Voltage L1-N"),
    "_G_ULN[1]": ("voltage_l2_n", "V", "Voltage L2-N"),
    "_G_ULN[2]": ("voltage_l3_n", "V", "Voltage L3-N"),
    "_G_ULL[0]": ("voltage_l1_l2", "V", "Voltage L1-L2"),
    "_G_ILN[0]": ("current_l1", "A", "Apparent current, L1-N"),
    "_G_ILN[1]": ("current_l2", "A", "Apparent current, L2-N"),
    "_G_ILN[2]": ("current_l3", "A", "Apparent current, L3-N"),
    "_G_P_SUM3": ("active_power_total", "W", "Psum3=P1+P2+P3"),
    "_G_S_SUM3": ("apparent_power_total", "VA", "Sum; Ssum3=S1+S2+S3"),
    "_G_Q_SUM3": ("reactive_power_total", "var", "Qsum3=Q1+Q2+Q3 (fundamental comp.)"),
    "_G_FREQ": ("frequency", "Hz", "Measured frequency"),
    "_G_THD_ULN[0]": ("voltage_thd_l1_n", "%", "Harmonic, THD,U L1-N"),
    "_G_THD_ILN[0]": ("current_thd_l1", "%", "Harmonic, THD,I L1"),
}

# designation -> (point id, format, unit, note, extra)
# extra: {"enum": {raw: (name, vendor text)}} parses "0=..., 1=..." from the note;
#        {"flags": {bit: (name, vendor text)}} parses the "Bit n = ..." lines under the row;
#        {"description": text}.
ROWS_509 = {
    "_SYSTIME": ("system_time", "int", "sec", "time (UTC)", {}),
    "_WH_V[4]": ("active_energy_import", "float", "Wh", "Real energy L1..L3, consumed", {}),
    "_WH_Z[4]": ("active_energy_export", "float", "Wh", "Real energy L1..L3, delivered", {}),
    "_DIGIN_STAT[0]": ("digital_input_1", "short", None, "Status digital input, 0=not active, 1=active",
                       {"enum": {0: ("not_active", "not active"), 1: ("active", "active")}}),
    "_EVT_COUNT": ("event_counter", "uint", None, "Event counter", {}),
    **{name: (point_id, "float", unit, note, {}) for name, (point_id, unit, note) in FREQUENT_509.items()},
    # The unit column of this row reads "s"; a bit-coded status has no unit and none is emitted.
    "_COMP_DIFF_STATUS[0]": ("differential_current_1_alarm_status", "short", "s", "Alarm status for diff 1 with:",
                             {"flags": {0: ("warning", "Warning"), 1: ("overcurrent", "Overcurrent"),
                                        2: ("alarm", "Alarm"), 3: ("ct_not_connected", "CT not connected")},
                              "no_unit": True}),
    "_PF_TOTAL": ("power_factor_total", "float", None, "PF Total, PF_Total=P_Sum3/S_Sum3", {}),
}
ROWS_604 = {
    "_SYSTIME": ("system_time", "int", "sec", "Time (UTC)", {}),
    "_EXT_TEMPERATUR": ("temperature", "float", "°C", "Temperature", {}),
    "_WH_V[4]": ("active_energy_import", "float", "Wh", "Real Energy, Con., L1+L2+L3", {}),
    "_WH_Z[4]": ("active_energy_export", "float", "Wh", "Real Energy, Supply, L1+L2+L3", {}),
    "_DIGIN_STAT[0]": ("digital_input_1", "short", "n", "Digital input 1, Status (r)", {}),
    "_EVT_COUNT": ("event_counter", "uint", "n", "Event-Counter", {}),
    **{name: (point_id, "float", unit, note, {}) for name, (point_id, unit, note) in FREQUENT_604.items()},
    "_pf_total": ("power_factor_average", "float", "-", "Average, PF = (PF1+PF2+PF3)/3", {}),
}

# UMG 96-PA workbook: (category, description) -> (point id, type, unit, extra)
FREQUENT_96PA = "Frequently required measured values"
ROWS_96PA = {
    ("Other parameters", "Serial number"): ("serial_number", "uint", None, {}),
    ("Measured values", "Measured value (float): cos(ϕ) sum"): ("cos_phi_total", "float", None, {}),
    ("Energy values", "Active Energy sum, consumed"): ("active_energy_import", "double", "Wh", {}),
    ("Energy values", "Active Energy sum, delivered"): ("active_energy_export", "double", "Wh", {}),
    ("Measured values", "Measured value (short): voltage L1-N"): (
        "voltage_l1_n_secondary", "short (x10)", "V",
        {"description": "16-bit value without the voltage transformer ratio."}),
    ("Measured values", "Measured value (short): current L1"): (
        "current_l1_secondary", "short (x1000)", "A",
        {"description": "16-bit value without the current transformer ratio."}),
    (FREQUENT_96PA, "Voltage L1-N"): ("voltage_l1_n", "float", "V", {}),
    (FREQUENT_96PA, "Voltage L2-N"): ("voltage_l2_n", "float", "V", {}),
    (FREQUENT_96PA, "Voltage L3-N"): ("voltage_l3_n", "float", "V", {}),
    (FREQUENT_96PA, "Voltage L1-L2"): ("voltage_l1_l2", "float", "V", {}),
    (FREQUENT_96PA, "Current, L1"): ("current_l1", "float", "A", {}),
    (FREQUENT_96PA, "Current, L2"): ("current_l2", "float", "A", {}),
    (FREQUENT_96PA, "Current, L3"): ("current_l3", "float", "A", {}),
    (FREQUENT_96PA, "Sum, Psum3=P1+P2+P3"): ("active_power_total", "float", "W", {}),
    (FREQUENT_96PA, "Sum, Ssum3=S1+S2+S3"): ("apparent_power_total", "float", "VA", {}),
    (FREQUENT_96PA, "Sum, Qsum3=Q1+Q2+Q3"): ("reactive_power_total", "float", "var", {}),
    (FREQUENT_96PA, "Measured frequency"): ("frequency", "float", "Hz", {}),
    (FREQUENT_96PA, "Harmonic, THD,U L1-N"): ("voltage_thd_l1_n", "float", "%", {}),
    (FREQUENT_96PA, "Harmonic, THD,I L1"): ("current_thd_l1", "float", "%", {}),
    ("Other parameters", "Device type ID: UMG 96-PA=19, UMG 96-PA-MID+=30, UMG 96-PQ-L=32, UMG 96-PQ-L (IT)=34, "
                         "UMG 96-PQ-L-LP=38"): (
        "device_type", "ushort", None,
        {"named_values": {"UMG 96-PA": "umg_96_pa", "UMG 96-PA-MID+": "umg_96_pa_mid_plus",
                          "UMG 96-PQ-L": "umg_96_pq_l", "UMG 96-PQ-L (IT)": "umg_96_pq_l_it",
                          "UMG 96-PQ-L-LP": "umg_96_pq_l_lp"}}),
}

DOCUMENTS = {
    "umg509-pro": {
        "identity": [r"Power Analyser UMG 509-PRO\b", r"Modbus-address and Formulary",
                     r"Dok\. Nr\. 1\.059\.004\.2\.o"],
        "slave": "As a slave, the UMG 509-PRO supports the following modbus functions:",
        "row": re.compile(r"^\s*(\d{1,5})\s+(\S+)\s+(RD/WR|RD)\s+(_\S+)\s*(.*?)\s*$"),
        "header": r"^Address\s+Format\s+RD/WR\s+Designation\s+Unit\s+Note$",
        "rows": ROWS_509,
        "manual": ("janitza-umg509pro-manual", [r"\bUMG 509-PRO\b", r"Doc\. no\. ?: 2\.059\.011\.3\.a"],
                   [r"RS-485 interface \(Modbus RTU, slave, up to 921 kbps\)",
                    r"Modbus/TCP, Modbus RTU over Ethernet"]),
        "example_row": "_G_ULN[0]",
        "rule3": None,
    },
    "umg604-pro": {
        "identity": [r"Power Analyser UMG 604-PRO\b", r"Modbus-address and Formulary",
                     r"\(Firmware rel\. 5\.030 an higher\)", r"Doc\. no\. 1\.033\.034\.h"],
        "slave": "As a slave, the UMG604-PRO supports the following modbus functions:",
        "row": re.compile(r"^\s*(\d{1,5})\s+(\S+)\s+()(_\S+)\s*(.*?)\s*$"),
        "header": r"^Address\s+Format\s+Designation\s+Unit\s+Remarks$",
        "rows": ROWS_604,
        "manual": ("janitza-umg604pro-manual", [r"\bUMG 604-PRO\b", r"Doc\. no\. ?: 1\.033\.059\.7\.a"],
                   [r"RS-485 interface \(Modbus RTU, Modbus master\)",
                    r"RS232 interface .{0,80}?Protocol Modbus RTU/Server",
                    r"Modbus/TCP \(port 502\)", r"Modbus RTU over Ethernet \(port 8000\)"]),
        "example_row": None,
        # Rule 3: (address, format, designation, rest) rows the inference rests on.
        "rule3": [(0, "long64", "_REALTIME", "2 ns Time (UTC)"),
                  (9973, "short", "_DIGOUT_STAT[0]", "n Digital output 1, Status (r/w)"),
                  (9975, "short", "_DIGIN_STAT[0]", "n Digital input 1, Status (r)")],
    },
}
PA_PDF = r"[0-9a-z]+-mal-umg96pa-fw3-en\.pdf"
PA_XLSX = r"[0-9a-z]+-umg96pa-mal-de-en\.xlsx"
PA_SHEET = "Sheet1(EN)"
PA_HEADER = {"A": "Category", "B": "Sort order (Category)", "C": "Address", "D": "Type", "E": "Access Right",
             "F": "Description", "G": "Unit", "H": "Min", "I": "Max"}
PA_INFO = ["Doc. No.:", "2.061.164.1.a", "Device Name:", "UMG 96-PA / UMG 96-PA MID+", "Firmware-Version:", "3.54"]
PA_IDENTITY = [r"Power Analyser", r"\bUMG 96-PA\b", r"\bUMG 96-PAMID\+", r"Doc\. no\. 2\.061\.029\.3\.e",
               r"\(from firmware 3\.54\)", r"Modbus-address list and Formulary"]
PA_SLAVE = "The UMG 96-PA supports the following Modbus functions as a slave:"
PA_MANUAL = ("janitza-umg96pa-manual", [r"\bUMG 96-PA \(from firmware 3\.54\)", r"Doc no\. 2\.061\.059\.4\.a"],
             [r"RS-485 interface \(Modbus RTU, slave, up to 115 kbps\)"])
PA_ROW = re.compile(r"^\s*(\d{1,5})\s+(float|double|short|ushort|int|uint|long64|char|string)\s+(RD/WR|RD|WR)\b")
PA_FACTOR = re.compile(r"^(short|ushort) \(x(10|100|1000)\)$")


def flat(text):
    """Text with zero-width spaces removed and whitespace collapsed."""
    return " ".join(text.replace("​", "").split())


def check_statements(text, slave, formats, name):
    """Require the conventions the selection relies on; text is the front matter in reading order."""
    for key, statement in STATEMENTS.items():
        require(statement in text, f"Janitza {name}: statement {key} not found")
    for kind in sorted(formats):
        require(re.search(FORMATS[kind][0], text), f"Janitza {name}: number format {kind!r} not defined")
    position = text.find(slave)
    require(position >= 0, f"Janitza {name}: slave Modbus function list not found")
    for function in FUNCTIONS:
        found = text.find(function, position)
        require(0 <= found - position < 2500, f"Janitza {name}: slave function {function[:24]!r} not listed")
        position = found + len(function)


def manual_text(evidence, manual, name):
    """The manual's text in reading order, after checking its identity and its interface statements."""
    manual_id, identity, interfaces = manual
    require(evidence and manual_id in evidence, f"Janitza {name}: evidence document {manual_id} missing")
    data = evidence[manual_id]
    text = flat(" ".join(pdf_pages(data, 1, pdf_page_count(data), layout=False)))
    for pattern in identity:
        require(re.search(pattern, text), f"Janitza {name}: manual identity {pattern!r} not found")
    for pattern in interfaces:
        require(re.search(pattern, text), f"Janitza {name}: manual interface statement {pattern!r} not found")
    return text


def request_example(text, name):
    """Parse the request frame of the manual's example; return (list address, registers asked for)."""
    examples = EXAMPLE.findall(text)
    require(len(examples) == 1, f"Janitza {name}: expected one 'Reading the voltage L1-N' example in the manual")
    stated, table = examples[0]
    fields = {}
    for key, pattern in EXAMPLE_FIELDS.items():
        matches = re.findall(pattern, table)
        require(matches, f"Janitza {name}: manual example lacks {key}")
        fields[key] = matches[0]
    decimal, hexadecimal = fields["address"]
    wire = int(fields["high"] + fields["low"], 16)
    require(wire == int(hexadecimal, 16) == int(decimal) == int(stated),
            f"Janitza {name}: the manual's request does not carry the list address unchanged")
    return wire, int(fields["count_high"] + fields["count_low"], 16)


def unit_fields(vendor_unit, point, extra):
    notes = [extra["description"]] if "description" in extra else []
    if vendor_unit in UNITS and not extra.get("no_unit"):
        point["unit"] = UNITS[vendor_unit]
    elif vendor_unit in NOT_UCUM:
        notes.append(NOT_UCUM[vendor_unit])
    else:
        require(vendor_unit is None or vendor_unit in NO_UNIT or extra.get("no_unit"),
                f"Janitza {point['id']}: unknown unit {vendor_unit!r}")
    if notes:
        point["description"] = " ".join(notes)


def parse_enum(note, expected, point_id):
    found = {int(raw): text.strip() for raw, text in re.findall(r"(\d+)=([^,]+)", note)}
    require(found == {raw: text for raw, (_, text) in expected.items()}, f"Janitza {point_id}: unexpected value list")
    return {"values": [{"value": raw, "name": name, "label": text} for raw, (name, text) in sorted(expected.items())]}


def parse_flags(lines, expected, point_id):
    found = {}
    for line in lines:
        match = re.fullmatch(r"\s*Bit (\d+) = (.+?)\s*", line)
        if not match:
            break
        found[int(match.group(1))] = match.group(2)
    require(found == {bit: text for bit, (_, text) in expected.items()}, f"Janitza {point_id}: unexpected bit list")
    return {"flags": [{"bit": bit, "name": name, "label": text} for bit, (name, text) in sorted(expected.items())]}


def extract_pdf_list(data, document, name, evidence):
    count = pdf_page_count(data)
    pages = pdf_pages(data, 1, 12, layout=False)
    front = flat(" ".join(pages))
    for pattern in document["identity"]:
        require(re.search(pattern, flat(pages[0])), f"Janitza {name}: document identity {pattern!r} not found")
    selected = document["rows"]
    check_statements(front, document["slave"], {kind for _, kind, _, _, _ in selected.values()}, name)

    found, rule3, headers = {}, set(), 0
    for number, page in enumerate(pdf_pages(data, 12, count), start=12):
        lines = page.splitlines()
        for index, line in enumerate(lines):
            if re.match(document["header"], line.strip()):
                headers += 1
                continue
            match = document["row"].match(line)
            if not match:
                continue
            address, kind, access, designation, rest = match.groups()
            rest = " ".join(rest.split())
            if (int(address), kind, designation, rest) in (document["rule3"] or []):
                rule3.add(int(address))
            if designation in selected:
                require(designation not in found, f"Janitza {name}: duplicate row {designation}")
                found[designation] = (number, int(address), kind, access, rest, lines[index + 1:index + 9])
    require(headers >= 20, f"Janitza {name}: address list table header not found")
    missing = sorted(set(selected) - found.keys())
    require(not missing, f"Janitza {name}: missing rows {missing}")
    if document["rule3"] is not None:
        require(rule3 == {address for address, _, _, _ in document["rule3"]},
                f"Janitza {name}: rows that settle the address base and the table are missing")

    points = []
    for designation, (point_id, kind, vendor_unit, note, extra) in selected.items():
        number, address, found_kind, access, rest, following = found[designation]
        require(found_kind == kind, f"Janitza {name} {designation}: format {found_kind!r}, expected {kind!r}")
        require(rest == (f"{vendor_unit} {note}" if vendor_unit else note),
                f"Janitza {name} {designation}: unexpected unit or note {rest!r}")
        point = {"id": point_id, "address": address, "type": FORMATS[kind][1]}
        unit_fields(vendor_unit, point, extra)
        if "enum" in extra:
            point["enum"] = parse_enum(note, extra["enum"], point_id)
        if "flags" in extra:
            point["flags"] = parse_flags(following, extra["flags"], point_id)
        point["aliases"] = [designation, note.rstrip(":")]
        point["source"] = {"address": str(address), "page": number, "reference": f"Address list, {designation}"}
        points.append(point)

    manual = manual_text(evidence, document["manual"], name)
    if document["example_row"]:
        address, registers = request_example(manual, name)
        example = found[document["example_row"]]
        require((example[1], example[2]) == (address, "float") and registers == 2,
                f"Janitza {name}: the manual's example does not read the list's L1-N voltage float")
    return sorted(points, key=lambda point: point["address"])


def pdf_rows_96pa(pdf, count):
    """address -> (page, type with its "(x10)" factor line, access) for every row of the PDF list."""
    rows = {}
    for number, page in enumerate(pdf_pages(pdf, 12, count), start=12):
        lines = page.splitlines()
        for index, line in enumerate(lines):
            match = PA_ROW.match(line)
            if not match:
                continue
            address, kind, access = match.groups()
            following = next((text.strip() for text in lines[index + 1:index + 3] if text.strip()), "")
            if re.fullmatch(r"\(x\d+\)", following):
                kind = f"{kind} {following}"
            require(int(address) not in rows, f"Janitza UMG 96-PA: PDF lists address {address} twice")
            rows[int(address)] = (number, kind, access)
    return rows


def extract_96pa(data, evidence):
    name = "UMG 96-PA"
    require(len(zip_names(data)) == 2, f"Janitza {name}: expected two archive members")
    pdf, workbook = zip_member(data, PA_PDF), zip_member(data, PA_XLSX)
    pages = pdf_pages(pdf, 1, 11, layout=False)
    front = flat(" ".join(pages))
    for pattern in PA_IDENTITY:
        require(re.search(pattern, flat(pages[0])), f"Janitza {name}: document identity {pattern!r} not found")
    kinds = {kind.split(" ")[0] for _, kind, _, _ in ROWS_96PA.values()}
    check_statements(front, PA_SLAVE, kinds, name)
    require(SHORT_FACTORS in front, f"Janitza {name}: rule for short (x10), (x100), (x1000) not found")

    require(xlsx_sheets(workbook) == ["Sheet1(DE)", PA_SHEET, "INFO"], f"Janitza {name}: workbook sheets changed")
    info = [row.get("A") for _, row in xlsx_rows(workbook, "INFO")]
    require(info[:6] == PA_INFO, f"Janitza {name}: workbook INFO sheet changed: {info[:6]}")
    rows = list(xlsx_rows(workbook, PA_SHEET))
    require(rows[0] == (1, PA_HEADER), f"Janitza {name}: unexpected workbook header")
    found, addresses = {}, set()
    for number, row in rows[1:]:
        require(re.fullmatch(r"\d{1,5}", row.get("C", "")) and int(row["C"]) not in addresses,
                f"Janitza {name}: {PA_SHEET}!C{number} is not a unique address")
        addresses.add(int(row["C"]))
        key = (row.get("A"), row.get("F"))
        # The list repeats some quantities in several number formats; the selection names the format.
        if key in ROWS_96PA and row.get("D") == ROWS_96PA[key][1]:
            require(key not in found, f"Janitza {name}: duplicate row {key}")
            found[key] = (number, row)
    missing = sorted(set(ROWS_96PA) - found.keys())
    require(not missing, f"Janitza {name}: missing rows, or rows in another number format: {missing}")

    listed = pdf_rows_96pa(pdf, pdf_page_count(pdf))
    points = []
    for key, (point_id, kind, vendor_unit, extra) in ROWS_96PA.items():
        number, row = found[key]
        ref = f"{PA_SHEET}!C{number}"
        address = int(row["C"])
        require(row.get("G") == vendor_unit, f"Janitza {name} {ref}: unexpected unit {row.get('G')!r}")
        require(row.get("E") in ("RD", "RD/WR"), f"Janitza {name} {ref}: not readable")
        require(address in listed and listed[address][1:] == (kind, row["E"]),
                f"Janitza {name} {ref}: the PDF list disagrees on type or access right")
        factor = PA_FACTOR.match(kind)
        point = {"id": point_id, "address": address, "type": FORMATS[kind.split(" ")[0]][1]}
        if factor:
            point["conversion"] = {"exponent10": -len(factor.group(2)) + 1}
        unit_fields(vendor_unit, point, extra)
        if "named_values" in extra:
            label, values = key[1].split(": ", 1)
            pairs = dict(item.rsplit("=", 1) for item in values.split(", "))
            require(set(pairs) == set(extra["named_values"]) and all(value.isdigit() for value in pairs.values()),
                    f"Janitza {name} {ref}: unexpected value list")
            point["enum"] = {"values": [{"value": int(value), "name": extra["named_values"][text], "label": text}
                                        for text, value in pairs.items()]}
            point["aliases"] = [label]
        else:
            point["aliases"] = [key[1]]
        point["source"] = {"address": str(address), "page": listed[address][0], "reference": f"{ref}, {key[0]}"}
        points.append(point)

    address, registers = request_example(manual_text(evidence, PA_MANUAL, name), name)
    example = found[(FREQUENT_96PA, "Voltage L1-N")][1]
    require((int(example["C"]), example["D"]) == (address, "float") and registers == 2,
            f"Janitza {name}: the manual's example does not read the list's L1-N voltage float")
    return sorted(points, key=lambda point: point["address"])


def extract(data, selector, evidence=None):
    if selector == "umg96-pa":
        return extract_96pa(data, evidence)
    require(selector in DOCUMENTS, f"Unknown Janitza selector {selector!r}")
    return extract_pdf_list(data, DOCUMENTS[selector], selector, evidence)
