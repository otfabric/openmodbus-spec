"""Eastron SDM120-Modbus protocol PDF: input register map on page 5."""
import re

from sourcelib import pdf_pages, require

SELECTED = {
    "Voltage": ("voltage", "Volts", "V"),
    "Current": ("current", "Amps", "A"),
    "Active power": ("active_power", "Watts", "W"),
    "Frequency": ("frequency", "Hz", "Hz"),
    "Import active energy": ("import_active_energy", "kWh", "kW.h"),
}


def extract(data, selector=None):
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
