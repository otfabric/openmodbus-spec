"""Victron GX Modbus-TCP register list (XLSX): VE.Bus inverter/charger rows.

The GX device serves the com.victronenergy.vebus service for a VE.Bus
inverter/charger. The pinned GX Modbus-TCP Manual (wiki source at a fixed
revision, evidence victron-gx-modbus-tcp-manual) supplies the facts the
register list does not state, and the extractor reads them from it:
- section 5, mapping example: the input voltage of a Multi or Quattro is read
  by setting "the data address of the first request register to 3" and dividing
  the reply by 10. The register list row "Input voltage phase 1" has Address 3
  and Scalefactor 10, so the Address column holds request (PDU) addresses and
  the Scalefactor column is a divisor;
- section 3: function codes 3 and 4 are both supported and equivalent, so the
  rows are read as holding registers;
- section 2: the GX device acts as a Modbus-TCP gateway selected by unit ID, and
  com.victronenergy.vebus covers VE.Bus inverters, Multis and Quattros.
"""
import re
from decimal import Decimal

from sourcelib import require, xlsx_rows

SHEET = "Field list"
SERVICE = "com.victronenergy.vebus"
HEADER = {"A": "dbus-service-name", "B": "description", "C": "Address", "D": "Type", "E": "Scalefactor",
          "F": "Range", "G": "dbus-obj-path", "H": "writable", "I": "dbus-unit", "J": "Remarks"}
RAW_RANGES = {"uint16": (0, 65535), "int16": (-32768, 32767)}
TYPES = {"uint16": "u16", "int16": "i16"}
UNITS = {"V AC": "V", "V DC": "V", "A DC": "A", "W": "W", "%": "%", "Hz": "Hz", "Degrees celsius": "Cel"}

# dbus path: (point id, vendor description, vendor type, vendor unit, writable on the GX)
MEASUREMENTS = {
    "/Ac/ActiveIn/L1/P": ("ac_input_power_l1", "Input power 1", "int16", "W", "no"),
    "/Ac/Out/L1/V": ("ac_output_voltage_l1", "Output voltage phase 1", "uint16", "V AC", "no"),
    "/Ac/Out/L1/F": ("ac_output_frequency", "Output frequency", "int16", "Hz", "no"),
    "/Ac/Out/L1/P": ("ac_output_power_l1", "Output power 1", "int16", "W", "no"),
    "/Dc/0/Voltage": ("battery_voltage", "Battery voltage", "uint16", "V DC", "no"),
    "/Dc/0/Current": ("battery_current", "Battery current", "int16", "A DC", "no"),
    "/Soc": ("battery_state_of_charge", "VE.Bus state of charge", "uint16", "%", "yes"),
    "/Dc/0/Temperature": ("battery_temperature", "Battery temperature", "int16", "Degrees celsius", "no"),
}
ENUMS = {
    "/State": ("vebus_state", "VE.Bus state"),
    "/Alarms/HighTemperature": ("temperature_alarm", "Temperature alarm"),
    "/Alarms/LowBattery": ("low_battery_alarm", "Low battery alarm"),
    "/Alarms/Overload": ("overload_alarm", "Overload alarm"),
    "/Bms/AllowToCharge": ("bms_allows_charge", "VE.Bus BMS allows battery to be charged"),
    "/Bms/AllowToDischarge": ("bms_allows_discharge", "VE.Bus BMS allows battery to be discharged"),
    "/VebusChargeState": ("charge_state", "Charge state"),
}
STRINGS = {"/CustomName": ("custom_name", "Custom Name")}

MANUAL = "victron-gx-modbus-tcp-manual"
MANUAL_TITLE = "====== GX Modbus-TCP Manual ======"
MAPPING_EXAMPLE = re.compile(
    r"To request the input voltage of a Multi or Quattro, connected to the VE\.Bus sockets on the GX device, use the "
    r"following settings: Unit-ID (\d+), and set the data address of the first request register to (\d+)\.")
MAPPING_REPLY = re.compile(r"The Modbus-TCP reply will contain (\d+)\. Divide it by (\d+), as specified in cell E\d+, "
                           r"and then you have the voltage: ([\d.]+) Volts AC\.")
EXAMPLE_PATH = "/Ac/ActiveIn/L1/V"
MANUAL_LINES = (
    "* ReadHoldingRegisters = 3",
    "* ReadInputRegisters = 4",
    "Note that there is no difference between function code 3 and 4.",
)
GATEWAY = "The GX Device then acts as a Modbus-TCP gateway."
SCOPE = re.compile(r"^\|\s*com\.victronenergy\.vebus\s*\|\s*Inverters \(VE\.Bus\), Multis, and Quattros\s*\|",
                   re.MULTILINE)


def identifier(label):
    name = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    require(re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name), f"Victron: no identifier for {label!r}")
    return name


def string_registers(rows):
    """The document shows string[n] as n registers: 12 characters in string[6], MSB first."""
    serial = [row for _, row in rows if row.get("A") == "com.victronenergy.system" and row.get("G") == "/Serial"]
    require(len(serial) == 1 and serial[0].get("D") == "string[6]" and serial[0].get("F") == "12 characters",
            "Victron: system serial row no longer shows the string[n] register count")
    pv_serial = [row for _, row in rows if row.get("A") == "com.victronenergy.pvinverter" and row.get("G") == "/Serial"]
    require(len(pv_serial) == 1 and "MSB of first register: first character" in pv_serial[0].get("J", ""),
            "Victron: pvinverter serial row no longer states the string byte order")


def scaled(path, row, raw_type):
    divisor = Decimal(row["E"])
    require(divisor > 0, f"Victron {path}: invalid Scalefactor {row['E']!r}")
    if divisor == 1:
        return None
    # A power-of-ten divisor becomes exponent10; anything else needs review.
    digits = divisor.normalize().as_tuple()
    require(digits.digits == (1,), f"Victron {path}: Scalefactor {row['E']} is not a power of ten")
    exponent = -digits.exponent
    low, high = (Decimal(raw) / divisor for raw in RAW_RANGES[raw_type])
    match = re.fullmatch(r"(-?[\d.]+) to (-?[\d.]+)", row.get("F", ""))
    require(match and (Decimal(match.group(1)), Decimal(match.group(2))) == (low, high),
            f"Victron {path}: Range {row.get('F')!r} disagrees with type and Scalefactor")
    return {"exponent10": exponent}


def manual_example(evidence):
    """Return (unit ID, request address, divisor) of the manual's mapping example after checking its statements."""
    require(evidence and MANUAL in evidence, f"Victron: evidence {MANUAL} is required")
    text = evidence[MANUAL].decode("utf-8")
    lines = [line.strip() for line in text.splitlines()]
    require(lines[0] == MANUAL_TITLE, "Victron manual: title changed")
    require(all(line in lines for line in MANUAL_LINES), "Victron manual: function code statement changed")
    require(GATEWAY in text, "Victron manual: no longer describes the GX device as Modbus-TCP gateway")
    require(SCOPE.search(text), "Victron manual: com.victronenergy.vebus no longer covers Multis and Quattros")
    example, reply = MAPPING_EXAMPLE.search(text), MAPPING_REPLY.search(text)
    require(example and reply, "Victron manual: mapping example changed")
    raw, divisor, volts = int(reply.group(1)), int(reply.group(2)), Decimal(reply.group(3))
    require(Decimal(raw) / divisor == volts, "Victron manual: mapping example arithmetic changed")
    return int(example.group(1)), example.group(2), str(divisor)


def extract(data, selector=None, evidence=None):
    unit, example_address, example_divisor = manual_example(evidence)
    rows = list(xlsx_rows(data, SHEET))
    headers = [row for _, row in rows if row.get("A") == "dbus-service-name"]
    require(len(headers) == 1 and headers[0] == HEADER, "Victron: Field list header changed")
    example = [row for _, row in rows if row.get("A") == SERVICE and row.get("G") == EXAMPLE_PATH]
    require(len(example) == 1 and (example[0].get("C"), example[0].get("E")) == (example_address, example_divisor),
            "Victron: register list no longer matches the manual's mapping example (Address, Scalefactor)")
    units = [row for _, row in xlsx_rows(data, "Unit ID mapping") if row.get("A") == str(unit)]
    require(len(units) == 1 and "VE.Bus port" in units[0].get("C", ""),
            f"Victron: unit ID {unit} of the mapping example is not a VE.Bus port in the Unit ID mapping")
    string_registers(rows)
    wanted = {**MEASUREMENTS, **ENUMS, **STRINGS}
    points = {}
    for number, row in rows:
        path = row.get("G")
        if row.get("A") != SERVICE or path not in wanted:
            continue
        require(path not in points, f"Victron: duplicate vebus row {path}")
        require(re.fullmatch(r"\d+", row.get("C", "")), f"Victron {path}: address {row.get('C')!r}")
        address = int(row["C"])
        point_id, description = wanted[path][:2]
        require(row.get("B") == description, f"Victron {path}: description {row.get('B')!r}")
        point = {"id": point_id, "address": address}
        if path in MEASUREMENTS:
            _, _, raw_type, raw_unit, writable = MEASUREMENTS[path]
            require((row.get("D"), row.get("I"), row.get("H")) == (raw_type, raw_unit, writable),
                    f"Victron {path}: unexpected type, unit or access")
            point["type"] = TYPES[raw_type]
            point["unit"] = UNITS[raw_unit]
            conversion = scaled(path, row, raw_type)
            if conversion:
                point["conversion"] = conversion
        elif path in ENUMS:
            require((row.get("D"), row.get("E"), row.get("H")) == ("uint16", "1", "no"),
                    f"Victron {path}: unexpected enum row")
            values = []
            for item in row.get("I", "").split(";"):
                match = re.fullmatch(r"\s*(\d+)=(.+?)\s*", item)
                require(match, f"Victron {path}: unparsed enum item {item!r}")
                values.append({"value": int(match.group(1)), "name": identifier(match.group(2)),
                               "label": match.group(2)})
            require(len(values) >= 2, f"Victron {path}: enum too short")
            require(len({v["value"] for v in values}) == len({v["name"] for v in values}) == len(values),
                    f"Victron {path}: duplicate enum value or name")
            point["type"] = "u16"
            point["enum"] = {"values": values}
        else:
            match = re.fullmatch(r"[Ss]tring\[(\d+)\]", row.get("D", ""))
            require(match and row.get("H") == "yes", f"Victron {path}: unexpected string row")
            point["type"] = "string"
            point["registers"] = int(match.group(1))
        if row.get("J"):
            point["description"] = row["J"]
        point["aliases"] = [row["B"], f"{SERVICE}{path}"]
        point["source"] = {"address": row["C"], "reference": f"{SHEET}!C{number}"}
        points[path] = point
    missing = sorted(wanted.keys() - points.keys())
    require(not missing, f"Missing Victron vebus rows: {missing}")
    return sorted(points.values(), key=lambda point: point["address"])
