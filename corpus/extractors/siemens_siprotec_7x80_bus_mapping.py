"""Siemens SIPROTEC 7SJ80/7SK80/7RW80 Modbus bus mapping (PDF), standard mapping 3-1.

The selector is the model, "7sj80", "7sk80" or "7rw80". Section 1.1 states that the objects
are sorted by register numbers starting with 1 (30001 is the first input register), so the
Modicon references resolve with modicon_reference(). The functional-scope tables 1-1 to 1-3
are the per-model applicability columns: an input status point is selected for a model only
if its chapter is referenced in that model's table. Measured values carry their default
scaling ("32767 corresponds to ..."); the mapping does not state the register data type, so
only magnitudes are selected, whose documented range 0...32767 decodes the same signed or
unsigned.
"""
from decimal import Decimal
import re

from sourcelib import modicon_reference, pdf_page_count, pdf_pages, require

MODELS = {"7sj80": "Table 1-1", "7sk80": "Table 1-2", "7rw80": "Table 1-3"}

# designation -> (point id, chapter, models)
STATUS = {
    "79 Lockout": ("ar_lockout", "1.4.2", {"7sj80"}),
    "50(N)/51(N) PU": ("overcurrent_pickup", "1.4.3", {"7sj80", "7sk80"}),
    "50N/51NPickedup": ("earth_overcurrent_pickup", "1.4.3", {"7sj80", "7sk80"}),
    "50(N)/51(N)TRIP": ("overcurrent_trip", "1.4.3", {"7sj80", "7sk80"}),
    "67/67N TRIP": ("directional_overcurrent_trip", "1.4.4", {"7sj80"}),
    "46 TRIP": ("negative_sequence_trip", "1.4.5", {"7sk80"}),
    "81-1 TRIP": ("frequency_stage_1_trip", "1.4.6", {"7rw80"}),
    "27-1 picked up": ("undervoltage_stage_1_pickup", "1.4.7", {"7rw80"}),
    "27-1 TRIP": ("undervoltage_stage_1_trip", "1.4.7", {"7sj80", "7rw80"}),
    "59-1 TRIP": ("overvoltage_stage_1_trip", "1.4.7", {"7rw80"}),
    "66 TRIP": ("motor_start_protection_trip", "1.4.9", {"7sk80"}),
    "START-SUP TRIP": ("startup_supervision_trip", "1.4.10", {"7sk80"}),
    "FAIL: Trip cir.": ("trip_circuit_failure", "1.4.11", {"7sj80", "7sk80", "7rw80"}),
    "Cntrl Auth": ("control_authority_local", "1.4.12", {"7sj80", "7sk80", "7rw80"}),
}
# Chapters that are not protection functions and so do not appear in the scope tables.
GENERAL_CHAPTERS = {"1.4.12"}

# designation -> (point id, expected full-scale unit, models)
MEASURED = {
    "Ia": ("current_a", "A", {"7sj80", "7sk80"}),
    "Ib": ("current_b", "A", {"7sj80", "7sk80"}),
    "Ic": ("current_c", "A", {"7sj80", "7sk80"}),
    "In": ("current_n", "A", {"7sj80", "7sk80"}),
    "Va": ("voltage_a_n", "kV", {"7sj80", "7sk80", "7rw80"}),
    "Vb": ("voltage_b_n", "kV", {"7rw80"}),
    "Vc": ("voltage_c_n", "kV", {"7rw80"}),
    "Va-b": ("voltage_a_b", "kV", {"7sj80", "7sk80", "7rw80"}),
    "Freq": ("frequency", "Hz", {"7sj80", "7sk80", "7rw80"}),
}
UNITS = {"A": ("A", 0), "kV": ("V", 3), "Hz": ("Hz", 0)}

DIAGNOSTIC_FLAGS = {
    0: ("device_ok", "Device OK"),
    1: ("settings_calculation", "Settings Calc."),
    2: ("protection_active", "ProtActive"),
    3: ("error_summary_alarm", "Error Sum Alarm"),
    4: ("alarm_summary_event", "Alarm Sum Event"),
    5: ("relay_pickup", "Relay PICKUP"),
    6: ("relay_trip", "Relay TRIP"),
    8: ("test_mode", "Test mode"),
    15: ("data_invalid", "Data invalid"),
}

CHAPTER = re.compile(r"^(1\.\d(?:\.\d+)?)\s+(\S.*?)\s*$", re.MULTILINE)
RANGE = re.compile(r"^Registers? (\d{5})(?: to (\d{5}))?:")
STATUS_ROW = re.compile(r"^\s*(1\d{4})\s+(\S(?:\S| (?=\S))*)(?:\s{2,}|\s*$)", re.MULTILINE)
MEASURED_ROW = re.compile(
    r"^\s*(3\d{4})\s+(\S+) =\s+(\S(?:\S| (?=\S))*)\s{2,}([\d.]+) (A|kV|Hz)\s+(\d+)\s*$", re.MULTILINE)
DIAGNOSTIC_ROW = re.compile(r"^\s*40129/2(\d{1,2})\s+(\S(?:\S| (?=\S))*)\s{2,}", re.MULTILINE)


def scope(text, table):
    """Chapters referenced by one model's functional-scope table."""
    match = re.search(rf"{table}\s+\S+ Functional scope\n(.*?)(?=Table 1-\d|\n1\.3\s)", text, re.DOTALL)
    require(match, f"Siemens: {table} functional scope missing")
    chapters = set(re.findall(r"\s(1\.[34]\.\d+)\s*$", match.group(1), re.MULTILINE))
    require(chapters, f"Siemens: {table} references no chapters")
    return chapters


def extract(data, selector):
    require(selector in MODELS, f"Unknown SIPROTEC selector {selector!r}")
    pages = pdf_pages(data, 1, pdf_page_count(data))
    flat = re.sub(r"\s+", " ", "\n".join(pages))
    require("Modbus Standard mapping 3-1" in flat and "C53000-L2240-A320-3" in flat,
            "Siemens: standard mapping 3-1 / document number missing")
    require("The SIPROTEC objects transferred are sorted by register numbers (starting with 1)" in flat,
            "Siemens: register numbering statement missing")
    chapters = scope("\n".join(pages), MODELS[selector]) | GENERAL_CHAPTERS

    points = []
    seen = set()
    current = None
    for number, page in enumerate(pages, start=1):
        # Walk each page in order so that a row belongs to the last chapter heading above it.
        marks = sorted([(m.start(), "chapter", m) for m in CHAPTER.finditer(page)] +
                       [(m.start(), "status", m) for m in STATUS_ROW.finditer(page)] +
                       [(m.start(), "measured", m) for m in MEASURED_ROW.finditer(page)] +
                       [(m.start(), "diagnostic", m) for m in DIAGNOSTIC_ROW.finditer(page)],
                       key=lambda item: item[0])
        for _, kind, match in marks:
            if kind == "chapter":
                bounds = RANGE.match(match.group(2))
                first, last = (bounds.group(1), bounds.group(2) or bounds.group(1)) if bounds else (0, 0)
                current = (match.group(1), int(first), int(last))
                continue
            if current and current[0] == "1.1":
                continue  # Section 1.1 shows invented example rows, not the mapping.
            if kind == "status":
                reference, label = match.groups()
                if label not in STATUS or selector not in STATUS[label][2]:
                    continue
                point_id, chapter, _ = STATUS[label]
                require(current and current[0] == chapter and current[1] <= int(reference) <= current[2],
                        f"Siemens {label}: register {reference} outside chapter {chapter}")
                require(chapter in chapters, f"Siemens {selector}: chapter {chapter} not in functional scope")
                points.append({
                    "id": point_id,
                    "table": "discrete_input",
                    "address": modicon_reference(reference, "discrete_input"),
                    "type": "bool",
                    "aliases": [label],
                    "source": {"address": reference, "page": number, "reference": f"Chapter {chapter}"},
                })
            elif kind == "measured":
                reference, label, comment, full_scale, raw_unit, _ = match.groups()
                if label not in MEASURED or selector not in MEASURED[label][2]:
                    continue
                point_id, expected_unit, _ = MEASURED[label]
                require(current and current[0] == "1.5", f"Siemens {label}: not in the input register chapter")
                require(raw_unit == expected_unit, f"Siemens {label}: full-scale unit {raw_unit}")
                unit, shift = UNITS[raw_unit]
                step = Decimal(full_scale) / Decimal(32767) * Decimal(10) ** shift
                exponent = step.log10()
                require(exponent == exponent.to_integral_value(), f"Siemens {label}: scaling {full_scale} not 10^n")
                points.append({
                    "id": point_id,
                    "table": "input_register",
                    "address": modicon_reference(reference, "input_register"),
                    "type": "i16",
                    "conversion": {"exponent10": int(exponent)},
                    "unit": unit,
                    "aliases": [label, comment] if comment != label else [label],
                    "description": f"Default scaling: 32767 corresponds to {full_scale} {raw_unit}.",
                    "source": {"address": reference, "page": number, "reference": "Chapter 1.5 Input Registers"},
                })
            else:
                exponent, label = match.groups()
                exponent = int(exponent)
                require(current and current[0] == "1.6.3" and 0 <= exponent <= 15,
                        f"Siemens diagnostics: unexpected row 40129/2^{exponent}")
                if exponent in DIAGNOSTIC_FLAGS:
                    require(DIAGNOSTIC_FLAGS[exponent][1] == label,
                            f"Siemens diagnostics: bit {exponent} is {label!r}")
                    require(exponent not in seen, f"Siemens diagnostics: duplicate bit {exponent}")
                    seen.add(exponent)
                    diagnostics_page = number

    require(seen == DIAGNOSTIC_FLAGS.keys(), f"Siemens diagnostics: missing bits {DIAGNOSTIC_FLAGS.keys() - seen}")
    points.append({
        "id": "diagnostics",
        "table": "holding_register",
        "address": modicon_reference("40129", "holding_register"),
        "type": "u16",
        "flags": {"flags": [{"bit": bit, "name": name, "label": label}
                            for bit, (name, label) in DIAGNOSTIC_FLAGS.items()]},
        "description": "Diagnostic register; bit n is listed as 40129/2^n. Data invalid (bit 15) is set by the "
                       "Modbus slave when the data in the message are invalid.",
        "source": {"address": "40129", "page": diagnostics_page, "reference": "Chapter 1.6.3 Diagnostics"},
    })

    ids = [point["id"] for point in points]
    require(len(ids) == len(set(ids)), f"Siemens {selector}: duplicate rows")
    expected = {spec[0] for spec in STATUS.values() if selector in spec[2]} | \
        {spec[0] for spec in MEASURED.values() if selector in spec[2]} | {"diagnostics"}
    require(set(ids) == expected, f"Siemens {selector}: missing {sorted(expected - set(ids))}")
    return sorted(points, key=lambda point: (point["table"], point["address"]))
