"""ABB M4M network analyzers, Modbus map workbook (XLSX, 9AKK107492A7627): selected measurements.

The selector is a product name from the workbook's "Details" sheet, e.g. "M4M 20 Modbus". The
"Mapping Table" lists, per row, the product type IDs that support it in the columns from N (ID 0)
onwards; every selected row must list the selected product's ID.

Cells are read as cached values only. The conventions for this table are stated in ABB's companion
"Modbus manual, M4M network analyzers" (2CSG445050D0201, v1.05), pinned as the evidence document
"abb-m4m-modbus-manual". The extractor parses and requires from its bytes: FC 3 (Read holding
registers) reads the measurement values (section 2); the FC 3 request example "read phase voltage
L1", whose bytes must form a valid RTU frame (CRC), gives the start address on the wire, and the
workbook's row for that quantity must carry the same hex register and register count (section 3);
the readable range; multi-register values carry the most significant byte in the high byte of the
first register and the least significant byte in the low byte of the last; unused quantities read
FFFF in every register (unsigned) or the highest value the register count can express (signed),
with the stated one- and two-register values checked ("Reading and Writing to Registers"); the
hex register column is "expressed exactly as it is sent on the bus" (section 4).
"""
from decimal import Decimal
import re

from sourcelib import column_letter, pdf_page_count, pdf_pages, require, xlsx_rows, xlsx_sheets

SHEETS = ["Mapping Table", "M2M mapping table", "OBIS Code", "Event ID", "Changes", "Details"]
MAP_VERSION = "v1.3O"
HEADER = {"A": "Parameter", "B": "Unit", "C": "Details", "D": "Resolution", "E": "Data Type", "F": "Access",
          "G": "Register (Hex)", "H": "Reg (Dec)", "I": "Nr of quantities", "J": "Size", "K": "Nr of registers",
          "L": "Product Type", "M": "Functionality group"}
FIRST_ID_COLUMN = 13  # column N holds product type ID 0, column N+k holds ID k
MANUAL = "abb-m4m-modbus-manual"
MANUAL_IDENTITY = ["MODBUSMANUALM4MNetworkanalyzers", "2CSG445050D0201[V.1.05]"]
# Statements in the manual's text with whitespace collapsed (line-break hyphens kept as "- ").
MANUAL_STATEMENTS = {
    "supported": r"The following function codes are supported: \S Function code 3 \(Read holding registers\)",
    "read_function": r"Function Code 3 \(Read holding registers\) Function code 3 is used to read measurement values "
                     r"or other information from the electricity meter\.",
    "column": r"Start Reg \(Hex\) Hexadecimal number for the first \(lowest\) Modbus Reg- ister for this quantity\. "
              r"It is expressed exactly as it is sent on the bus\.",
    "byte_order": r"For quantities that are represented as more than 1 register, the most significant byte is found "
                  r"in the high byte of the first \(lowest\) register\. The least significant byte is found in the "
                  r"low byte of the last \(highest\) register\.",
}
READABLE = re.compile(r"The readable range in the Modbus mapping are registers ([0-9A-F]{4})-([0-9A-F]{4}) "
                      r"\(hexadeci- mal\)\.")
UNUSED = re.compile(r"For quantities with data type “unsigned”, the value will be ([0-9A-F]{4}) in all registers\. "
                    r"For quantities with data type “signed”, the value is the highest value possible to express\. "
                    r"That means that a quantity that is represented by only one register will have the value "
                    r"([0-9A-F]+)\. A quantity that is represented by 2 registers will have the value ([0-9A-F]+), "
                    r"and so on\.")
EXAMPLE = re.compile(r"example of a request \(read ([^)]+)\)\. Slave address 0x([0-9A-F]{2}) Function code "
                     r"0x([0-9A-F]{2}) Start address, high byte 0x([0-9A-F]{2}) Start address, low byte "
                     r"0x([0-9A-F]{2}) No\. of registers, high byte 0x([0-9A-F]{2}) No\. of registers, low byte "
                     r"0x([0-9A-F]{2}) Error check \(CRC\), high byte 0x([0-9A-F]{2}) Error check \(CRC\), "
                     r"low byte 0x([0-9A-F]{2})")
UNITS = {"V": "V", "A": "A", "W": "W", "Hz": "Hz", "%": "%", "kWh": "kW.h", "VA": "V.A"}
NOT_UCUM = {"var", "kvarh"}
TYPES = {("Unsigned", 1): "u16", ("Unsigned", 2): "u32", ("Unsigned", 4): "u64",
         ("Signed", 1): "i16", ("Signed", 2): "i32", ("Signed", 4): "i64"}

# (Parameter, Details): (point id, data type, registers, workbook unit)
SELECTED = {
    ("Active energy - import", ""): ("active_energy_import", "Unsigned", 4, "kWh"),
    ("Active energy - export", ""): ("active_energy_export", "Unsigned", 4, "kWh"),
    ("Active energy - net", ""): ("active_energy_net", "Signed", 4, "kWh"),
    ("Reactive energy - import", ""): ("reactive_energy_import", "Unsigned", 4, "kvarh"),
    ("Phase voltage L1", "L1"): ("voltage_l1_n", "Unsigned", 2, "V"),
    ("Phase voltage L2", "L2"): ("voltage_l2_n", "Unsigned", 2, "V"),
    ("Phase voltage L3", "L3"): ("voltage_l3_n", "Unsigned", 2, "V"),
    ("Line voltage L1-L2", "L1-L2"): ("voltage_l1_l2", "Unsigned", 2, "V"),
    ("Current", "L1"): ("current_l1", "Unsigned", 2, "A"),
    ("Current", "L2"): ("current_l2", "Unsigned", 2, "A"),
    ("Current", "L3"): ("current_l3", "Unsigned", 2, "A"),
    ("Active power", "Total"): ("active_power_total", "Signed", 2, "W"),
    ("Reactive power", "Total"): ("reactive_power_total", "Signed", 2, "var"),
    ("Apparent power", "Total"): ("apparent_power_total", "Signed", 2, "VA"),
    ("Frequency", ""): ("frequency", "Unsigned", 1, "Hz"),
    ("Power factors", "Total"): ("power_factor_total", "Signed", 1, ""),
    ("Voltage THD harmonics", "L1 (THD)"): ("voltage_thd_l1", "Unsigned", 1, "%"),
    ("Current harmonics", "L1 (THD)"): ("current_thd_l1", "Unsigned", 1, "%"),
    ("Serial number(s)", ""): ("serial_number", "ASCII", 5, ""),
}


def product_types(data):
    rows = dict(xlsx_rows(data, "Details"))
    require(rows[1].get("A") == "Product type number ID", "ABB Details sheet: unexpected header")
    products = {}
    for number, row in sorted(rows.items()):
        if number == 1 or not re.fullmatch(r"\d+", row.get("A", "")):
            continue
        require(row.get("B") and int(row["A"]) not in products.values() and row["B"] not in products,
                f"ABB Details!A{number}: missing or duplicate product type")
        products[row["B"]] = int(row["A"])
    require(list(products.values()) == list(range(len(products))), "ABB product type IDs are not 0..n")
    return products


def crc16(frame):
    """Modbus RTU CRC; the frame carries the low byte first."""
    crc = 0xFFFF
    for byte in frame:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, crc >> 8])


def check_manual(data):
    """Parse the conventions the mapping depends on from the companion Modbus manual."""
    text = "\n".join(pdf_pages(data, 1, pdf_page_count(data)))
    compact = re.sub(r"\s+", "", text)
    for marker in MANUAL_IDENTITY:
        require(marker in compact, f"ABB manual: identity {marker!r} not found")
    flat = " ".join(text.split())
    for key, pattern in MANUAL_STATEMENTS.items():
        require(re.search(pattern, flat), f"ABB manual: statement {key} not found")

    readable = READABLE.findall(flat)
    require(len(readable) == 1, "ABB manual: readable range not found once")
    low, high = (int(value, 16) for value in readable[0])

    unused = UNUSED.findall(flat)
    require(len(unused) == 1, "ABB manual: unused-register rule not found once")
    unsigned, signed_one, signed_two = unused[0]
    require(unsigned == "FFFF", "ABB manual: unsigned invalid value is not FFFF")
    require(int(signed_one, 16) == (1 << 15) - 1 and int(signed_two, 16) == (1 << 31) - 1,
            "ABB manual: signed invalid values are not the highest values of one and two registers")

    examples = EXAMPLE.findall(flat)
    require(len(examples) == 1, "ABB manual: expected one FC 3 read request example")
    quantity, *octets = examples[0]
    frame = bytes(int(octet, 16) for octet in octets)
    require(crc16(frame[:6]) == frame[6:], "ABB manual: the read example is not a valid RTU frame")
    require(frame[1] == 3, "ABB manual: the read example does not use FC 3")
    return {"readable": (low, high), "unsigned_word": int(unsigned, 16), "example": quantity,
            "example_address": frame[2] << 8 | frame[3], "example_registers": frame[4] << 8 | frame[5]}


def invalid_value(manual, kind, registers):
    """Unsigned: the stated word in every register. Signed: the highest value of the register count."""
    if kind == "Unsigned":
        return int(f"{manual['unsigned_word']:04X}" * registers, 16)
    return (1 << (16 * registers - 1)) - 1


def check_workbook(data):
    require(xlsx_sheets(data) == SHEETS, f"ABB workbook sheets changed: {xlsx_sheets(data)}")
    versions = [row["A"] for _, row in xlsx_rows(data, "Changes") if row.get("A", "").startswith("v")]
    require(versions and versions[-1] == MAP_VERSION, f"ABB map version is not {MAP_VERSION}: {versions[-1:]}")


def conversion(resolution, row_ref):
    value = Decimal(resolution).normalize()
    digits = value.as_tuple()
    require(value > 0 and digits.digits == (1,), f"ABB {row_ref}: resolution {resolution!r} is not a power of ten")
    return digits.exponent


def extract(data, selector, evidence=None):
    require(evidence and MANUAL in evidence, f"ABB: evidence document {MANUAL} missing")
    manual = check_manual(evidence[MANUAL])
    check_workbook(data)
    products = product_types(data)
    require(selector in products, f"ABB product {selector!r} not in the Details sheet")
    product_id = products[selector]
    id_column = column_letter(FIRST_ID_COLUMN + product_id)

    rows = list(xlsx_rows(data, "Mapping Table"))
    require(rows[0][0] == 1 and all(rows[0][1].get(col) == text for col, text in HEADER.items()),
            "ABB Mapping Table: unexpected header row")
    require(rows[1][0] == 2 and rows[1][1].get(column_letter(FIRST_ID_COLUMN)) == "Product type ID",
            "ABB Mapping Table: product type ID columns moved")
    found = {}
    for number, row in rows[2:]:
        key = (row.get("A", ""), row.get("C", ""))
        if key in SELECTED:
            require(key not in found, f"ABB Mapping Table: duplicate row for {key}")
            found[key] = (number, row)
    missing = sorted(set(SELECTED) - found.keys())
    require(not missing, f"ABB Mapping Table: missing rows {missing}")
    example = [key for key in found if key[0].lower() == manual["example"].lower()]
    require(len(example) == 1, f"ABB: the manual's example quantity {manual['example']!r} is not one selected row")
    example_row = found[example[0]][1]
    require(example_row.get("G") == f"{manual['example_address']:04X}"
            and example_row.get("K") == str(manual["example_registers"]),
            "ABB Mapping Table disagrees with the manual's FC 3 read example")

    points = []
    for key, (point_id, kind, registers, vendor_unit) in SELECTED.items():
        number, row = found[key]
        ref = f"'Mapping Table'!A{number}"
        require(row.get("F") == "Read", f"ABB {ref}: not read-only")
        require(row.get("I") == "1" and row.get("J") == row.get("K") == str(registers),
                f"ABB {ref}: unexpected quantity count or register size")
        require(row.get("E", "") == kind and row.get("B", "") == vendor_unit,
                f"ABB {ref}: unexpected data type or unit")
        require(re.fullmatch(r"[0-9A-F]{4}", row.get("G", "")) and int(row["G"], 16) == int(row.get("H", "-1")),
                f"ABB {ref}: hex and decimal registers disagree")
        require(product_id in [int(token) for token in row.get(id_column, "").split()],
                f"ABB {ref}: not listed for product type {product_id} ({selector})")
        address = int(row["G"], 16)
        low, high = manual["readable"]
        require(low <= address and address + registers - 1 <= high, f"ABB {ref}: outside the readable range")
        vendor = f"{key[0]} {key[1]}".strip() if key[1] and key[1] not in key[0] else key[0]
        point = {"id": point_id, "address": address}
        if kind == "ASCII":
            point.update(type="string", registers=registers)
        else:
            point["type"] = TYPES[(kind, registers)]
            exponent = conversion(row.get("D", ""), ref)
            if exponent:
                point["conversion"] = {"exponent10": exponent}
            if vendor_unit in UNITS:
                point["unit"] = UNITS[vendor_unit]
            else:
                require(vendor_unit in NOT_UCUM | {""}, f"ABB {ref}: unknown unit {vendor_unit!r}")
                if vendor_unit:
                    point["description"] = f"Vendor unit: {vendor_unit}."
            point["invalid"] = [invalid_value(manual, kind, registers)]
        point["aliases"] = [vendor]
        point["source"] = {"address": f"0x{row['G']}", "reference": f"'Mapping Table'!G{number}"}
        points.append(point)
    return sorted(points, key=lambda point: point["address"])
