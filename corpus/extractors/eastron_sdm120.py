"""Eastron SDM120-Modbus and SDM120CTM protocol PDFs: input register maps.

Without a selector: the SDM120-Modbus document, input register map on page 5.
Selector "sdm120ctm": the SDM120CTM document, whose map starts on page 5 and
continues on page 6. Every input parameter is a two-register IEEE 754 float.
"""
import re
import struct

from sourcelib import modicon_reference, pdf_page_count, pdf_pages, require

SELECTED = {
    "Voltage": ("voltage", "Volts", "V"),
    "Current": ("current", "Amps", "A"),
    "Active power": ("active_power", "Watts", "W"),
    "Frequency": ("frequency", "Hz", "Hz"),
    "Import active energy": ("import_active_energy", "kWh", "kW.h"),
}
CT_TITLE = "Eastron SDM120CTM Smart Meter Modbus Protocol Implementation V1.3"
# label -> (point id, unit as printed)
CT_SELECTED = {
    "Voltage": ("voltage", "Volts"),
    "Current": ("current", "Amps"),
    "Active power": ("active_power", "Watts"),
    "Apparent power": ("apparent_power", "VA"),
    "Reactive power": ("reactive_power", "VAr"),
    "Power factor": ("power_factor", "None"),
    "Frequency": ("frequency", "Hz"),
    "Import active energy": ("import_active_energy", "kWh"),
    "Export active energy": ("export_active_energy", "kWh"),
    "Import reactive energy": ("import_reactive_energy", "kvarh"),
    "Export reactive energy": ("export_reactive_energy", "kvarh"),
    "current demand.": ("current_demand", "Amps"),
    "Total active energy": ("total_active_energy", "kWh"),
    "Total reactive energy": ("total_reactive_energy", "Kvarh"),
}
CT_UNITS = {"Volts": "V", "Amps": "A", "Watts": "W", "VA": "V.A", "VAr": None, "None": None, "Hz": "Hz",
            "kWh": "kW.h", "kvarh": None, "Kvarh": None}
CT_INPUT = "Function code 04 to read input parameters:"
CT_HOLDING = "Function code 10 to set holding parameter"


def flat(text):
    return " ".join(text.split())


def extract_ct(data):
    """SDM120CTM: rows are split on whitespace; a row whose cells wrap does not have the row shape and is skipped."""
    pages = pdf_pages(data, 1, pdf_page_count(data))
    text = flat(" ".join(pages))
    require(CT_TITLE in flat(pages[0]), "Eastron SDM120CTM protocol title missing")
    for statement in (
        "the data used by the Eastron Digital meter is in 32 bit IEEE 754 floating point format.",
        "MODBUS Protocol code 04 reads the contents of the 3X registers.",
        "As registers are used in pairs and start at zero, then this must be an even number.",
    ):
        require(statement in text, f"Eastron SDM120CTM: statement missing: {statement[:50]}")
    # The worked response is the only place that shows which register of a float comes first.
    example = re.search(r"The following response returns the contents of Volts 1 as (\d+\.\d+)\. .*?"
                        r"Byte Count 04 Data, High Reg, High Byte ([0-9A-F]{2}) Data, High Reg, Low Byte "
                        r"([0-9A-F]{2}) Data, Low Reg, High Byte ([0-9A-F]{2}) Data, Low Reg, Low Byte "
                        r"([0-9A-F]{2}) Error Check Low", text)
    require(example, "Eastron SDM120CTM: worked response for Volts 1 missing")
    decoded = struct.unpack(">f", bytes.fromhex("".join(example.groups()[1:])))[0]
    require(f"{decoded:.1f}" == example.group(1),
            "Eastron SDM120CTM: worked response does not decode with the high register first")
    first = [number for number, page in enumerate(pages, start=1) if CT_INPUT in flat(page)]
    last = [number for number, page in enumerate(pages, start=1) if CT_HOLDING in flat(page)]
    require(len(first) == 1 and len(last) == 1 and first[0] < last[0], "Eastron SDM120CTM: register map headers moved")

    points = {}
    for number in range(first[0], last[0]):
        for line in pages[number - 1].splitlines():
            cells = line.split()
            if len(cells) < 7 or not re.fullmatch(r"3\d{4}", cells[0]):
                continue
            label, (size, kind, raw_unit, high, low) = " ".join(cells[1:-5]), cells[-5:]
            if not (size.isdigit() and re.fullmatch(r"[0-9A-F]{2}", high) and re.fullmatch(r"[0-9A-F]{2}", low)):
                continue
            if label not in CT_SELECTED:
                continue
            point_id, expected_unit = CT_SELECTED[label]
            require(point_id not in points, f"Eastron SDM120CTM: duplicate row {label}")
            require((size, kind, raw_unit) == ("4", "Float", expected_unit),
                    f"Eastron SDM120CTM {label}: unexpected width, encoding or unit")
            address = int(high + low, 16)
            require(modicon_reference(cells[0], "input_register") == address and address % 2 == 0,
                    f"Eastron SDM120CTM {label}: conflicting register addresses")
            point = {"id": point_id, "address": address, "type": "f32"}
            if CT_UNITS[raw_unit]:
                point["unit"] = CT_UNITS[raw_unit]
            elif raw_unit != "None":
                point["description"] = f"Vendor unit: {raw_unit}."
            point["aliases"] = [label]
            point["source"] = {"address": cells[0], "page": number, "reference": "Input register map"}
            points[point_id] = point
    missing = {point_id for point_id, _ in CT_SELECTED.values()} - points.keys()
    require(not missing, f"Eastron SDM120CTM: missing rows {sorted(missing)}")
    return sorted(points.values(), key=lambda point: point["address"])


def extract(data, selector=None):
    if selector == "sdm120ctm":
        return extract_ct(data)
    require(selector is None, f"Unknown Eastron SDM120 selector {selector!r}")
    page = pdf_pages(data, 5)[0]
    require(re.search(r"Function code\s+04\s+to read input parameters", page, re.IGNORECASE),
            "Eastron PDF page 5: input register table header missing")
    rows = re.findall(
        r"^[ \t]*(3\d{4})[ \t]+([^\n]+?)[ \t]+(\d+)[ \t]+(\S+)[ \t]+(\w+)[ \t]+"
        r"([0-9A-F]{2})[ \t]+([0-9A-F]{2})[ \t]*$",
        page, re.MULTILINE,
    )
    points = {}
    for reference, label, size, raw_unit, kind, high, low in rows:
        label = " ".join(label.split())
        if label not in SELECTED:
            continue
        point_id, expected_unit, unit = SELECTED[label]
        require(point_id not in points, f"Duplicate Eastron point {point_id}")
        address = int(high + low, 16)
        require(int(reference) - 30001 == address and address % 2 == 0,
                f"Eastron {label}: conflicting register addresses")
        require((size, raw_unit, kind) == ("4", expected_unit, "Float"),
                f"Eastron {label}: unexpected width, unit or encoding")
        points[point_id] = {
            "id": point_id,
            "address": address,
            "type": "f32",
            "unit": unit,
            "source": {"address": reference, "page": 5, "reference": "Input register map"},
        }
    missing = {point_id for point_id, _, _ in SELECTED.values()} - points.keys()
    require(not missing, f"Missing Eastron rows: {sorted(missing)}")
    return sorted(points.values(), key=lambda point: point["address"])
