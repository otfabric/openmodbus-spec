"""Eastron SDM230-Modbus and SDM630-Modbus protocol PDFs: input register maps.

The selector is the model: "sdm230" or "sdm630". Every input parameter is a
two-register IEEE 754 float, most significant register first by default.
"""
import re

from sourcelib import modicon_reference, pdf_page_count, pdf_pages, require

TITLES = {
    "sdm230": "Eastron SDM230Modbus Smart Meter Modbus Protocol Implementation V1.4",
    "sdm630": "Eastron SDM630Modbus Smart Meter Modbus Protocol Implementation V1.8",
}
SELECTED = {
    "sdm230": {
        "Line to neutral volts.": ("voltage", "Volts"),
        "Current.": ("current", "Amps"),
        "Active power.": ("active_power", "Watts"),
        "Apparent power": ("apparent_power", "VoltAmps"),
        "Reactive power": ("reactive_power", "VAr"),
        "Power factor": ("power_factor", "None"),
        "Phase angle.": ("phase_angle", "Degree"),
        "Frequency": ("frequency", "Hz"),
        "Import active energy": ("import_active_energy", "kwh"),
        "Export active energy": ("export_active_energy", "kwh"),
        "Total active energy": ("total_active_energy", "kwh"),
    },
    "sdm630": {
        "Phase 1 line to neutral volts.": ("voltage_l1_n", "Volts"),
        "Phase 2 line to neutral volts.": ("voltage_l2_n", "Volts"),
        "Phase 3 line to neutral volts.": ("voltage_l3_n", "Volts"),
        "Phase 1 current.": ("current_l1", "Amps"),
        "Phase 2 current.": ("current_l2", "Amps"),
        "Phase 3 current.": ("current_l3", "Amps"),
        "Phase 1 power.": ("active_power_l1", "Watts"),
        "Total system power.": ("active_power_total", "Watts"),
        "Total system volt amps.": ("apparent_power_total", "VA"),
        "Total system VAr.": ("reactive_power_total", "VAr"),
        "Total system power factor (1).": ("power_factor_total", "None"),
        "Frequency of supply voltages.": ("frequency", "Hz"),
        "Total Import kWh": ("import_active_energy", "kWh"),
        "Total Export kWh.": ("export_active_energy", "kWh"),
        "Line 1 to Line 2 volts.": ("voltage_l1_l2", "Volts"),
        "Neutral current.": ("current_n", "Amps"),
    },
}
UNITS = {"Volts": "V", "Amps": "A", "Watts": "W", "VoltAmps": "V.A", "VA": "V.A", "VAr": None, "None": None,
         "Degree": "deg", "Hz": "Hz", "kwh": "kW.h", "kWh": "kW.h"}
WIRING = ("3P4W", "3P3W", "1P2W")
ROWS = {
    "sdm230": re.compile(r"^[ \t]*(3\d{4})[ \t]+(\S[^\n]*?)[ \t]{2,}(\S+)[ \t]+([0-9A-Fa-f]{2})[ \t]+"
                         r"([0-9A-Fa-f]{2})[ \t]*$", re.MULTILINE),
    "sdm630": re.compile(r"^[ \t]*(3\d{4})[ \t]+\d+[ \t]+(\S[^\n]*?)[ \t]{2,}(\S+)[ \t]+([0-9A-Fa-f]{2})[ \t]+"
                         r"([0-9A-Fa-f]{2})[ \t]+([√X])[ \t]+([√X])[ \t]+([√X])[ \t]*$", re.MULTILINE),
}
HOLDING = re.compile(r"^\s*(4\d{4})\s+\d+\s+(Password\s+)?([0-9A-FO]{2})\s+([0-9A-FO]{2})\s+(r|r/w)\s*$")


def flat(text):
    return " ".join(text.split())


def holding_address(reference, high, low):
    # The SDM630 table prints some hex bytes with a letter O for the digit 0 ("00 OE").
    hexadecimal = (high + low).replace("O", "0")
    address = modicon_reference(reference, "holding_register")
    require(int(hexadecimal, 16) == address, f"Eastron holding {reference}: hex and register number disagree")
    return address


def password_ranges(pages):
    """Holding ranges whose read resets the password timeout (SDM630)."""
    found = {}
    for number, page in pages:
        lines = page.splitlines()
        for index, line in enumerate(lines):
            match = HOLDING.match(line)
            if not match:
                continue
            above = lines[index - 1].split() if index else []
            below = lines[index + 1].split() if index + 1 < len(lines) else []
            if match.group(2):
                name = "Password"
            elif above[:1] == ["Password"] and below[:1] == ["Lock"]:
                name = "Password Lock"
            else:
                continue
            require(name not in found, f"Eastron duplicate {name} row")
            found[name] = (holding_address(match.group(1), match.group(3), match.group(4)), match.group(1))
    require(found.keys() == {"Password", "Password Lock"}, f"Eastron password rows: {sorted(found)}")
    return [{"table": "holding_register", "start": address, "count": 2, "policy": "side_effects",
             "reason": f"{name} ({reference}): reading it resets the password timeout timer."}
            for name, (address, reference) in sorted(found.items(), key=lambda item: item[1][0])]


def extract(data, selector):
    require(selector in TITLES, f"Unknown Eastron selector {selector!r}")
    model = selector.upper()
    pages = list(enumerate(pdf_pages(data, 1, pdf_page_count(data)), start=1))
    text = flat("\n".join(page for _, page in pages))
    require(TITLES[selector] in flat(pages[0][1]), f"Eastron {model} protocol title missing")
    for statement in (
        "Data Format: 4 bytes (2 registers) per parameter. Floating point format ( to IEEE 754) "
        "Most significant register first (Default).",
        f"All data values in the {model}Modbus smart meter are transferred as 32 bit IEEE754",
        f"floating point numbers, (input and output) therefore each {model}Modbus meter value is "
        "transferred using two Modbus Protocol registers.",
        "Modbus Protocol function code 04 is used to access all parameters.",
        "For example, to request: Amps 1 Start address=0006 No. of registers =0002",
    ):
        require(statement in text, f"Eastron {model}: statement missing: {statement[:50]}")
    limit = re.search(r"the maximum number of registers requestable is (\d+)\.", text)
    require(limit, f"Eastron {model}: request limit missing")
    constraints = {"maxReadRegisters": int(limit.group(1))}

    footnote = re.search(r"1\. (The power factor has its sign adjusted to indicate the direction of the current\. "
                         r"Positive refers to forward current, negative refers to reverse current\.)", text)
    if selector == "sdm630":
        require("A (*) in the column indicates that the parameter is valid for the particular wiring system. "
                "Any parameter with a cross(X) will return the value zero." in text,
                "Eastron SDM630 wiring column statement missing")
        require(footnote, "Eastron SDM630 power factor note missing")
        constraints["ranges"] = password_ranges(pages)

    points = {}
    for number, page in pages:
        for row in ROWS[selector].findall(page):
            reference, label, raw_unit, high, low, *wiring = row
            label = " ".join(label.split())
            if label not in SELECTED[selector]:
                continue
            point_id, expected_unit = SELECTED[selector][label]
            require(point_id not in points, f"Eastron {model}: duplicate row {label}")
            require(raw_unit == expected_unit, f"Eastron {model} {label}: unit {raw_unit!r}")
            address = int(high + low, 16)
            require(modicon_reference(reference, "input_register") == address and address % 2 == 0,
                    f"Eastron {model} {label}: conflicting register addresses")
            point = {"id": point_id, "address": address, "type": "f32"}
            if UNITS[raw_unit]:
                point["unit"] = UNITS[raw_unit]
            notes = []
            if not UNITS[raw_unit] and raw_unit != "None":
                notes.append(f"Vendor unit: {raw_unit}.")
            if label.endswith("(1)."):
                notes.append(footnote.group(1))
            if wiring:
                valid = [name for name, mark in zip(WIRING, wiring) if mark == "√"]
                zero = [name for name, mark in zip(WIRING, wiring) if mark == "X"]
                notes.append(f"Valid for {', '.join(valid)}" +
                             (f"; reads zero for {', '.join(zero)}." if zero else "."))
            if notes:
                point["description"] = " ".join(notes)
            point["aliases"] = [label]
            point["source"] = {"address": reference, "page": number, "reference": f"{model}Modbus input register table"}
            points[point_id] = point
    missing = {point_id for point_id, _ in SELECTED[selector].values()} - points.keys()
    require(not missing, f"Eastron {model}: missing rows {sorted(missing)}")
    return {"points": sorted(points.values(), key=lambda point: point["address"]), "constraints": constraints}
