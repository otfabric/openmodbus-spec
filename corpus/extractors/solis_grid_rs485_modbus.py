"""Solis RS485_MODBUS protocol for grid-connected PV inverters (PDF): input registers (0x04).

The register table lists plain decimal numbers. The worked examples in section 6 send them
unchanged as the PDU start address (e.g. "0B B7 Reg. Start Address (2999)"), so the table
number is the zero-based address. The extractor checks every function-code-04 example.
Section 3.1 states that 32-bit values are sent high word first.
"""
from decimal import Decimal
import re

from sourcelib import pdf_page_count, pdf_pages, require

PAGES = 43
TABLE_PAGES = (6, 12)
EXAMPLE_PAGES = (14, 18)
STATUS_PAGES = (28, 29)
ROW = re.compile(r"^\s*(?P<address>\d{4,5})(?:-(?P<high>\d{2}))?\s+(?P<label>\S.*?)\s+"
                 r"(?P<type>U16|S16|U32|S32)\b(?P<rest>.*)$")
TYPES = {"U16": ("u16", 1), "S16": ("i16", 1), "U32": ("u32", 2), "S32": ("i32", 2)}
UNITS = {"W": "W", "kWh": "kW.h", "V": "V", "A": "A", "℃": "Cel", "Hz": "Hz", "VA": "V.A", "Var": None, "": None}

# Vendor label -> (point ID, vendor type, vendor unit cell).
SELECTED = {
    "Active Power": ("active_power", "S32", "1W"),
    "Total DC output power": ("dc_power_total", "U32", "1W"),
    "Total energy": ("energy_total", "U32", "1kWh"),
    "Energy today": ("energy_today", "U16", "0.1kWh"),
    "DC voltage 1": ("dc_voltage_1", "U16", "0.1V"),
    "DC current1": ("dc_current_1", "U16", "0.1A"),
    "DC voltage 2": ("dc_voltage_2", "U16", "0.1V"),
    "DC current 2": ("dc_current_2", "U16", "0.1A"),
    "AB line voltage / A phase voltage": ("ac_voltage_ab_or_a", "U16", "0.1V"),
    "A phase current": ("ac_current_a", "U16", "0.1A"),
    "Standard working mode": ("working_mode", "U16", None),
    "Inverter temperature": ("inverter_temperature", "S16", "0.1℃"),
    "Grid Frequency": ("grid_frequency", "U16", "0.01Hz"),
    "Working Status": ("working_status", "U16", None),
    "Reactive power value": ("reactive_power", "S32", "1Var"),
    "Apparent power value": ("apparent_power", "S32", "1VA"),
    "Real-time power factor": ("power_factor", "S16", "0.010"),
}
# Single-line remarks copied into the description, checked verbatim.
REMARKS = {"Inverter temperature": "Note：AC NTC (IGBT)"}
# Appendix 3 rows for register 3071 whose label wraps around the BIT cell; left unnamed.
WRAPPED_STATUS_BITS = {9, 11, 12}


def identifier(text):
    name = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    require(re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name), f"Solis: no identifier for {text!r}")
    return name


def words(text):
    return " ".join(text.split())


def check_preamble(text):
    """Scope, word order and read interval statements of sections 1 to 3; return the interval in ms."""
    text = words(text)
    require("This protocol applies to machines manufactured after mid-2023." in text,
            "Solis section 3: manufacturing-date scope statement changed")
    for kind in ("U32", "S32"):
        require(re.search(kind + r" 4-byte \w+ integer, the high byte is in front of the low byte, and the high "
                r"word is in the front and the low word is behind;", text), f"Solis section 3.1: {kind} order changed")
    for kind, sign in (("U16", "unsigned"), ("S16", "signed")):
        require(f"{kind} 2-byte {sign} integer, high first and then low;" in text,
                f"Solis section 3.1: {kind} order changed")
    match = re.search(r"More than (\d+)ms communications frame of acquiring interval is required", text)
    require(match, "Solis section 3.2: read interval requirement missing")
    return int(match.group(1))


def table_rows(pages, first_page):
    lines = [(first_page + number, line) for number, page in enumerate(pages) for line in page.splitlines()]
    texts = [line for _, line in lines]
    start = next((index for index, line in enumerate(texts)
                  if "5.1. Inverter Parameter Address Definition for 0x04 (RO)" in line), None)
    end = next((index for index, line in enumerate(texts)
                if "5.2. Inverter Parameter Address Definition for 0x03, 0x06 and 0x10" in line), None)
    require(start is not None and end is not None and start < end, "Solis: input register table not found")
    rows, current = [], None
    for page, line in lines[start:end]:
        match = ROW.match(line)
        if match:
            rest = match.group("rest")
            unit = re.match(r"\s+(\d+(?:\.\d+)?\S*)", rest)
            current = {"match": match, "line": line, "more": [], "page": page,
                       "unit": unit.group(1) if unit else None,
                       "unit_column": match.end("type") + unit.start(1) if unit else None}
            rows.append(current)
        elif current is not None and line.strip():
            current["more"].append(line)
    result = {}
    for row in rows:
        match = row["match"]
        label_start, type_start = match.start("label"), match.start("type")
        label = [match.group("label")]
        unit = row["unit"]
        high = match.group("high")
        for index, line in enumerate(row["more"]):
            if high and index == 0:
                digits = re.match(r"\s*(\d{2})\b", line)
                require(digits, f"Solis {match.group('address')}: address continuation missing")
                high += digits.group(1)
                line = " " * digits.end() + line[digits.end():]
            label.append(line[label_start:type_start])
            if unit and row["unit_column"] < len(line):
                tail = line[row["unit_column"]:row["unit_column"] + len(unit) + 2].strip()
                if tail and not re.match(r"\d", tail):
                    unit += tail.split()[0]
        name = words(" ".join(label))
        first = int(match.group("address"))
        last = int(high) if match.group("high") else first
        result.setdefault(name, []).append({
            "address": first, "last": last, "type": match.group("type"), "unit": unit,
            "more": row["more"], "label_line": row["line"], "page": row["page"],
            "match_end": (row["unit_column"] + len(row["unit"])) if row["unit"] else match.end("type"),
        })
    return result


def check_examples(text):
    sections = re.split(r"(?m)^\s*6\.(\d+)\.\s+", text[text.index("6. Example"):])
    checked = []
    for number, body in zip(sections[1::2], sections[2::2]):
        request = re.search(r"(?m)^\s*((?:[0-9A-F]{2} ){5,}[0-9A-F]{2})\s", body)
        require(request, f"Solis example 6.{number}: request frame missing")
        frame = request.group(1).split()
        if frame[1] != "04":
            continue
        label = re.search(r"([0-9A-F]{2}) ([0-9A-F]{2})\s+Reg\. Start Address\s*[（(](\d+)[）)]", body)
        require(label, f"Solis example 6.{number}: start address row missing")
        address = int(label.group(1) + label.group(2), 16)
        require(address == int(label.group(3)) == int(frame[2] + frame[3], 16),
                f"Solis example 6.{number}: hex start address and register number disagree")
        checked.append(number)
    require(len(checked) >= 4 and "2" in checked, f"Solis: too few function-code-04 examples {checked}")


def scale(cell, point_id):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(\D*)", cell)
    require(match and match.group(2) in UNITS, f"Solis {point_id}: unexpected unit cell {cell!r}")
    factor = Decimal(match.group(1))
    exponent = factor.normalize().as_tuple().exponent
    require(factor == Decimal(1).scaleb(exponent), f"Solis {point_id}: scale {cell} is not a power of ten")
    return exponent, UNITS[match.group(2)], match.group(2)


def working_mode_enum(row):
    values = []
    for line in row["more"]:
        match = re.fullmatch(r"\s*(\d{2})---(\S.*?)\s*", line)
        if match:
            values.append({"value": int(match.group(1)), "name": identifier(match.group(2)),
                           "label": match.group(2)})
    require([value["value"] for value in values] == list(range(len(values))) and len(values) >= 5,
            "Solis working mode: unexpected value list")
    return {"values": values}


def working_status_flags(text):
    require(text.count("Appendix 3 Status Bits Definition") == 1, "Solis appendix 3 heading not found")
    lines = text[text.index("Appendix 3 Status Bits Definition"):].splitlines()
    starts = [index for index, line in enumerate(lines) if re.search(r"\bBIT00\b", line)]
    require(len(starts) >= 2 and "Working" in lines[starts[0]], "Solis appendix 3: 3071 block not found")
    block = lines[starts[0]:starts[1]]
    require(any(line.strip() == "3071" for line in block), "Solis appendix 3: register 3071 not in first block")
    named, wrapped = {}, set()
    for line in block:
        match = re.search(r"\bBIT(\d{2})\b(.*)$", line)
        if not match:
            continue
        bit, rest = int(match.group(1)), match.group(2)
        require(bit not in named and bit not in wrapped, f"Solis appendix 3: duplicate bit {bit}")
        label = re.fullmatch(r"\s+(\S.*?)\s+0—false\s+1—true\s*", rest)
        if label:
            named[bit] = words(label.group(1))
        else:
            require(not rest.strip(), f"Solis appendix 3: unexpected bit {bit} row")
            wrapped.add(bit)
    require(sorted(named.keys() | wrapped) == list(range(16)) and wrapped == WRAPPED_STATUS_BITS,
            f"Solis appendix 3: unexpected 3071 bits {sorted(named)} / {sorted(wrapped)}")
    flags = [{"bit": bit, "name": identifier(label), "label": label}
             for bit, label in sorted(named.items()) if label != "Reserved"]
    return {"flags": flags}


def extract(data, selector=None):
    require(pdf_page_count(data) == PAGES, "Solis PDF: unexpected page count")
    interval = check_preamble("\n".join(pdf_pages(data, 4, 5)))
    check_examples("\n".join(pdf_pages(data, *EXAMPLE_PAGES)))
    rows = table_rows(pdf_pages(data, *TABLE_PAGES), TABLE_PAGES[0])
    status_flags = working_status_flags("\n".join(pdf_pages(data, *STATUS_PAGES)))
    points = []
    for label, (point_id, vendor_type, unit_cell) in SELECTED.items():
        require(len(rows.get(label, [])) == 1, f"Solis: expected one row labelled {label!r}")
        row = rows[label][0]
        require(row["type"] == vendor_type and row["unit"] == unit_cell,
                f"Solis {label}: type {row['type']} unit {row['unit']!r}, expected {vendor_type} {unit_cell!r}")
        kind, width = TYPES[vendor_type]
        require(row["last"] - row["address"] + 1 == width, f"Solis {label}: register span disagrees with type")
        point = {"id": point_id, "aliases": [label], "address": row["address"], "type": kind}
        if unit_cell:
            exponent, unit, vendor_unit = scale(unit_cell, point_id)
            if unit:
                point["unit"] = unit
            elif vendor_unit:
                point["description"] = f"Vendor unit: {vendor_unit}."
            if exponent:
                point["conversion"] = {"exponent10": exponent}
        if label in REMARKS:
            remark = row["label_line"][row["match_end"]:].strip()
            require(remark == REMARKS[label], f"Solis {label}: remark {remark!r}")
            point["description"] = f"Vendor remark: {remark}"
        if point_id == "working_mode":
            point["enum"] = working_mode_enum(row)
        elif point_id == "working_status":
            require(any("See Appendix 3" in line for line in [row["label_line"], *row["more"]]),
                    "Solis working status: appendix reference missing")
            point["flags"] = status_flags
        vendor_address = str(row["address"]) if width == 1 else f"{row['address']}-{row['last']}"
        point["source"] = {"address": vendor_address, "page": row["page"],
                           "reference": "5.1 Inverter Parameter Address Definition for 0x04"}
        if point_id == "working_status":
            point["source"]["reference"] += "; Appendix 3 Status Bits Definition (page 28)"
        points.append(point)
    return {"points": sorted(points, key=lambda point: point["address"]),
            "constraints": {"minRequestIntervalMs": interval}}
