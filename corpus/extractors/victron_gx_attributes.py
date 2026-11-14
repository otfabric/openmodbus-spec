"""Victron GX dbus_modbustcp attributes.csv: system-service battery points."""
from decimal import Decimal

from sourcelib import csv_rows, require

POINT_IDS = {
    "/Dc/Battery/Voltage": "battery_voltage",
    "/Dc/Battery/Current": "battery_current",
    "/Dc/Battery/Power": "battery_power",
    "/Dc/Battery/Soc": "battery_state_of_charge",
}


def extract(data, selector=None):
    points = {}
    for line, row in csv_rows(data):
        service, path, _, raw_unit, address, raw_type, divisor, access = row
        if service != "com.victronenergy.system" or path not in POINT_IDS:
            continue
        require(path not in points, f"Duplicate Victron point {path}")
        require(access == "R", f"Unexpected Victron access for {path}: {access}")
        point = {
            "id": POINT_IDS[path],
            "address": int(address),
            "type": {"uint16": "u16", "int16": "i16"}[raw_type],
            "unit": {"V DC": "V", "A DC": "A", "W": "W", "%": "%"}[raw_unit],
        }
        if Decimal(divisor) != 1:
            multiplier = Decimal(1) / Decimal(divisor)
            encoded = float(multiplier)
            require(Decimal(str(encoded)) * Decimal(divisor) == 1, f"{path}: scale needs review")
            point["conversion"] = {"multiplier": encoded}
        point["source"] = {"address": address, "reference": f"attributes.csv:{line}"}
        points[path] = point
    require(points.keys() == POINT_IDS.keys(), f"Missing Victron rows: {sorted(POINT_IDS.keys() - points.keys())}")
    return sorted(points.values(), key=lambda point: point["address"])
