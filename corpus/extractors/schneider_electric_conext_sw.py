"""Schneider Electric Conext Modbus maps V4 (ZIP of PDFs): Conext SW device map 503-0244-01-01.

The map's address column is hexadecimal and starts at 0x0000 (Device Name), so
the column holds zero-based PDU addresses. The map names no function code but
lists read-only and read/write rows in one register space; read/write rows can
only be holding registers, so the contract reads every selected row as a
holding register (forced by the map itself; confirmation is a work item).

The transport is stated in the pinned Conext ComBox datasheet
DS20130702_ConextComBox (evidence schneider-electric-conext-combox-datasheet):
the ComBox Ethernet port is a Modbus TCP/IP server, its Xanbus port supports
the Conext SW, and it works with the selected product number. The extractor
reads those statements from the datasheet.

Only single-register rows are selected: the map does not state the register
order of uint32 and sint32 values, nor which character of a str<nn> pair is
sent first.

The selector is the product description in Table 1 (Applicable Products).
"""
import re
from decimal import Decimal

from sourcelib import pdf_page_count, pdf_pages, require, zip_member

MEMBER = "503-0244-01-01_RevA.4_Modbus_Map_Conext_SW_Device.pdf"
PAGES = 15
TABLE_PAGES = range(3, 11)
ROW = re.compile(r"^(0x[0-9A-F]{4})\s+(\S.*?)\s+(uint16|uint32|sint32|str\d+)\s+(rw|r)\b(.*)$")
VALUES = re.compile(r"^(?:(\S+(?: \S)?)\s+)?(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*(.*)$")
UNITS = {"deg C": "Cel", "%": "%", "Hz": "Hz", "A": "A"}

# vendor row name: (point id, access, vendor unit or None)
MEASUREMENTS = {
    "Battery Temperature": ("battery_temperature", "r", "deg C"),
    "Charge DC Power Percentage": ("charge_dc_power_percentage", "r", "%"),
    "AC1 Frequency": ("ac1_frequency", "r", "Hz"),
    "Load AC Frequency": ("load_ac_frequency", "r", "Hz"),
    "Maximum Charge Rate": ("maximum_charge_rate", "rw", "%"),
    "Maximum Discharge Current": ("maximum_discharge_current", "rw", "A"),
}
# vendor row name: (point id, section title holding the values, or None for values in the Notes column)
ENUMS = {
    "Device State": ("device_state", "Conext SW Operating State"),
    "Device Present": ("device_present", None),
    "Active Faults Flag": ("active_faults", None),
    "Active Warnings Flag": ("active_warnings", None),
    "Inverter Status": ("inverter_status", "Conext SW Invert Status"),
    "Charger Status": ("charger_status", "Conext SW Charger Status"),
}
FLAGS = {
    "Fault Bitmap 0": ("fault_bitmap_0", "Fault Bitmap 0"),
    "Fault Bitmap 1": ("fault_bitmap_1", "Fault Bitmap 1"),
    "Fault Bitmap 2": ("fault_bitmap_2", "Fault Bitmap 2"),
    "Warning Bitmap 0": ("warning_bitmap_0", "Warning Bitmap"),
}
NOT_AVAILABLE = "Data Not Available"

DATASHEET = "schneider-electric-conext-combox-datasheet"
DATASHEET_ID = "DS20130702_ConextComBox"
ETHERNET = re.compile(r"^\s*Ethernet\s+Connector: 1 x RJ45[^\n]*\n\s+Server: FTP, Web, Modbus TCP/IP\b", re.MULTILINE)
XANBUS = re.compile(r"^\s*Xanbus\s+Connector: 2 x RJ45[^\n]*\n\s+Products Supported: Conext XW, SW,", re.MULTILINE)
WORKS_WITH = re.compile(r"\bSW (\d{4}) 230 Product no\. (865-\d{4}-61)\b")


def identifier(label):
    name = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    require(re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name), f"Conext SW: no identifier for {label!r}")
    return name


def table_rows(pages):
    """Yield one dict per Table 3 row; `stray` collects wrapped cells outside the name and notes columns."""
    for page_number, text in pages:
        require("Table 3 Configuration and Status Registers" in text, f"Conext SW page {page_number}: no Table 3")
        lines = text.splitlines()
        rows = []
        for index, line in enumerate(lines):
            match = ROW.match(line)
            if match:
                rows.append((index, match))
            else:
                require(not line.startswith("0x"), f"Conext SW page {page_number}: unparsed row {line!r}")
        for position, (index, match) in enumerate(rows):
            end = rows[position + 1][0] if position + 1 < len(rows) else len(lines)
            rest = match.group(5).strip()
            values = VALUES.match(rest)
            require(values or (match.group(3).startswith("str") and not rest),
                    f"Conext SW page {page_number}: unparsed columns in {match.group(0)!r}")
            unit, scale, offset, notes = values.groups() if values else (None, None, None, "")
            name_column = match.start(2)
            notes_column = match.start(5) + match.group(5).index(notes) if notes else None
            name, notes, stray = [match.group(2)], [notes] if notes else [], []
            for line in lines[index + 1:end]:
                if re.match(r"^\s*(Section \d+:|\*)", line):
                    break
                if not line.strip() or "Revision A.4" in line:
                    continue
                for cell in re.finditer(r"\S+(?: \S+)*", line):
                    if abs(cell.start() - name_column) <= 1:
                        name.append(cell.group())
                    elif notes_column is not None and abs(cell.start() - notes_column) <= 1:
                        notes.append(cell.group())
                    else:
                        stray.append(cell.group())
            yield {"page": page_number, "address": match.group(1), "name": " ".join(name),
                   "type": match.group(3), "access": match.group(4), "unit": unit, "scale": scale,
                   "offset": offset, "notes": " ".join(notes), "stray": stray}


def sections(text):
    """Return {section title: (number, [(raw value, label)])} from the bullet lists after Table 3."""
    found = {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^\s*Section (\d+): (.+?)\s*$", line)
        if header:
            current = header.group(2)
            require(current not in found, f"Conext SW: section {current!r} twice")
            found[current] = (int(header.group(1)), [])
            continue
        bullet = re.match(r"^\s*•\s+(bit\d+|\d+)=(.+?)\s*$", line)
        if bullet:
            require(current is not None, f"Conext SW: bullet outside a section: {line!r}")
            found[current][1].append((bullet.group(1), bullet.group(2)))
    return found


def section_items(name, notes, listed, title):
    require(title in listed and notes == f"See section {listed[title][0]}",
            f"Conext SW {name}: notes {notes!r} do not point to section {title!r}")
    return listed[title][1]


def conversion(name, scale, offset):
    scale, offset = Decimal(scale), Decimal(offset)
    result = {}
    if scale != 1:
        digits = scale.normalize().as_tuple()
        require(digits.digits == (1,), f"Conext SW {name}: scale {scale} is not a power of ten")
        result["exponent10"] = digits.exponent
    if offset != 0:
        require(offset == offset.to_integral_value(), f"Conext SW {name}: offset {offset} needs review")
        result["offset"] = int(offset)
    return result


def enum_values(name, items):
    values = []
    invalid = []
    for raw, label in items:
        require(re.fullmatch(r"\d+", raw), f"Conext SW {name}: enum value {raw!r}")
        if label == NOT_AVAILABLE:
            invalid.append(int(raw))
            continue
        values.append({"value": int(raw), "name": identifier(label), "label": label})
    require(len(values) >= 2 and len({v["value"] for v in values}) == len({v["name"] for v in values}) == len(values),
            f"Conext SW {name}: incomplete or duplicate enumeration")
    return values, invalid


def flag_values(name, items):
    flags = []
    for raw, label in items:
        bit = re.fullmatch(r"bit(\d+)", raw)
        code = re.fullmatch(r"([FW]\d+):(.+)", label)
        require(bit and code and int(bit.group(1)) < 16, f"Conext SW {name}: flag {raw}={label}")
        if code.group(2) == "Reserved":
            continue
        flags.append({"bit": int(bit.group(1)), "name": identifier(label), "label": label})
    require(flags and len({f["bit"] for f in flags}) == len({f["name"] for f in flags}) == len(flags),
            f"Conext SW {name}: incomplete or duplicate flags")
    return flags


def datasheet_check(evidence, selector, product):
    """Require the ComBox datasheet to state its Modbus TCP/IP server and to list the selected product."""
    require(evidence and DATASHEET in evidence, f"Conext SW: evidence {DATASHEET} is required")
    document = evidence[DATASHEET]
    require(pdf_page_count(document) == 2, "ComBox datasheet: page count changed")
    text = "\n".join(pdf_pages(document, 1, 2))
    require(DATASHEET_ID in text and "Conext ComBox communication device" in text, "ComBox datasheet: identity changed")
    require(ETHERNET.search(text), "ComBox datasheet: Ethernet port no longer lists a Modbus TCP/IP server")
    require(XANBUS.search(text), "ComBox datasheet: Xanbus port no longer supports the Conext SW")
    model = re.fullmatch(r"Conext SW (\d{4})-230", selector or "")
    require(model and (model.group(1), product) in set(WORKS_WITH.findall(text)),
            f"ComBox datasheet: {selector} ({product}) is not listed as a compatible product")


def extract(data, selector, evidence=None):
    document = zip_member(data, MEMBER)
    require(pdf_page_count(document) == PAGES, "Conext SW map: page count changed")
    text = pdf_pages(document, 1, PAGES)
    require("503-0244-01-01" in text[0] and "Revision A.4" in text[0], "Conext SW map: document number changed")
    applicable = re.findall(r"^\s*(865-\d{4}(?:-\d+)?)\s{2,}(\S.*?)\s*$", text[1], re.MULTILINE)
    products = [product for product, description in applicable if description == selector]
    require(len(products) == 1, f"Conext SW map: {selector!r} is not an applicable product")
    datasheet_check(evidence, selector, products[0])
    require("Two characters are packed into each" in text[1], "Conext SW map: data type table changed")
    listed = sections("\n".join(text[9:]))

    points = {}
    first = None
    accesses = set()
    for row in table_rows([(number, text[number - 1]) for number in TABLE_PAGES]):
        name = row["name"]
        first = first or (row["address"], name)
        accesses.add(row["access"])
        if name not in MEASUREMENTS and name not in ENUMS and name not in FLAGS:
            continue
        require(name not in points, f"Conext SW: duplicate row {name}")
        require(row["type"] == "uint16" and not row["stray"],
                f"Conext SW {name}: expected one uint16 register, found {row['type']} {row['stray']}")
        point = {"id": None, "address": int(row["address"], 16), "type": "u16"}
        if name in MEASUREMENTS:
            point_id, expected_access, expected_unit = MEASUREMENTS[name]
            require((row["access"], row["unit"]) == (expected_access, expected_unit),
                    f"Conext SW {name}: unexpected access or unit ({row['access']}, {row['unit']})")
            point.update({"id": point_id, "unit": UNITS[row["unit"]]})
            converted = conversion(name, row["scale"], row["offset"])
            if converted:
                point["conversion"] = converted
        else:
            require((row["access"], row["unit"], row["scale"], row["offset"]) == ("r", None, "1.0", "0.0"),
                    f"Conext SW {name}: unexpected row")
            if name in ENUMS:
                point_id, title = ENUMS[name]
                if title:
                    items = section_items(name, row["notes"], listed, title)
                else:
                    items = re.findall(r"(\d+)=(.+?)(?=\s+\d+=|$)", row["notes"])
                values, invalid = enum_values(name, items)
                point.update({"id": point_id, "enum": {"values": values}})
                if invalid:
                    point["invalid"] = invalid
            else:
                point_id, title = FLAGS[name]
                point.update({"id": point_id,
                              "flags": {"flags": flag_values(name, section_items(name, row["notes"], listed, title))}})
        point["aliases"] = [name]
        point["source"] = {"address": row["address"], "page": row["page"],
                           "reference": "Table 3 Configuration and Status Registers"}
        points[name] = point
    require(first == ("0x0000", "Device Name"), "Conext SW map: Table 3 no longer starts at address 0x0000")
    # Read-only and read/write rows in one register list: only the holding-register table allows both.
    require(accesses == {"r", "rw"}, f"Conext SW map: Table 3 access types changed: {sorted(accesses)}")
    missing = sorted((MEASUREMENTS.keys() | ENUMS.keys() | FLAGS.keys()) - points.keys())
    require(not missing, f"Missing Conext SW rows: {missing}")
    return sorted(points.values(), key=lambda point: point["address"])
