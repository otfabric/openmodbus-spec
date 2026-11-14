"""Brainboxes ED Modbus product data tables (HTML): per-model input and counter rows.

The selector is the model heading ID on the page, e.g. "ed-516".
"""
import re

from sourcelib import html_tables, require

SELECTED = {
    ("Read digital inputs", "Discrete input", "2"): ("di", "discrete_input", "bool"),
    ("Read DI counter values", "Input register", "4"): ("counter", "input_register", "u16"),
}
BASES = {"discrete_input": 10001, "input_register": 30001}


def extract(data, selector):
    tables = [table for table in html_tables(data) if table["context"].get("h2", {}).get("id") == selector]
    require(tables, f"Brainboxes {selector} table missing")
    model = selector.upper()
    points = {}
    for row in tables[0]["rows"]:
        key = tuple(row[:3])
        if key not in SELECTED:
            continue
        prefix, table, kind = SELECTED[key]
        require(prefix not in points and len(row) == 6, f"Unexpected Brainboxes {prefix} row")
        match = re.fullmatch(r"0x([0-9a-f]+)\s*[-–]\s*([0-9a-f]+)", row[3], re.IGNORECASE)
        require(match is not None, f"Brainboxes {prefix}: unrecognized logical range {row[3]!r}")
        first, last = (int(value, 16) for value in match.groups())
        require(last - first + 1 == 16, f"Brainboxes {prefix}: expected 16 channels")
        start_ref = re.match(r"\d{5}", row[4])
        require(start_ref and int(start_ref.group()) - BASES[table] == first,
                f"Brainboxes {prefix}: logical and 984-style addresses disagree")
        points[prefix] = [
            {
                "id": f"{prefix}_{channel}",
                "table": table,
                "address": address,
                "type": kind,
                "source": {"address": f"0x{address:04X}", "reference": f"{model} product data table"},
            }
            for channel, address in enumerate(range(first, last + 1))
        ]
    require(points.keys() == {"di", "counter"}, f"Brainboxes {model} input or counter row missing")
    return points["di"] + points["counter"]
