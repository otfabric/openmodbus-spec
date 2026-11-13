"""Brainboxes ED Modbus product data tables (HTML): per-model I/O rows.

The selector is either the model heading ID on the page, e.g. "ed-516", which
selects the digital input and counter rows, or a mapping
{model: <heading ID>, rows: [<row group>, ...]} with row groups from ROWS.
"""
import re

from sourcelib import html_tables, require

# Row group -> (function, Modbus access type, function codes, table, type).
ROWS = {
    "di": ("Read digital inputs", "Discrete input", "2", "discrete_input", "bool"),
    "counter": ("Read DI counter values", "Input register", "4", "input_register", "u16"),
    "do": ("Set/read digital outputs", "Coil", "1, 5, 15", "coil", "bool"),
    "do_overload": ("Output overload flags", "Discrete input", "2", "discrete_input", "bool"),
}
DEFAULT_ROWS = ("di", "counter")
BASES = {"coil": 1, "discrete_input": 10001, "input_register": 30001}


def span(text, pattern, base):
    """Parse an abbreviated range such as '0x0400 - 3' or '11025 - 8' into (first, last)."""
    match = re.fullmatch(pattern, text, re.IGNORECASE)
    require(match is not None, f"Brainboxes: unrecognized range {text!r}")
    first, suffix = match.groups()
    require(len(suffix) <= len(first), f"Brainboxes: unrecognized range {text!r}")
    last = first[:len(first) - len(suffix)] + suffix
    first, last = int(first, base), int(last, base)
    require(first <= last, f"Brainboxes: empty range {text!r}")
    return first, last


def declared_channels(data, model_id):
    """The page's 'provides N digital inputs and M digital outputs' sentence for one model."""
    text = data.decode("utf-8")
    start = text.find(f'id="{model_id}"')
    require(start >= 0, f"Brainboxes {model_id} heading missing")
    end = text.find("<table", start)
    match = re.search(r"provides (?:(\d+) digital inputs)?(?: and )?(?:(\d+) digital outputs)?\.",
                      text[start:end])
    require(match is not None and any(match.groups()), f"Brainboxes {model_id}: channel counts missing")
    inputs, outputs = (int(value) if value else 0 for value in match.groups())
    return {"di": inputs, "counter": inputs, "do": outputs, "do_overload": outputs}


def extract(data, selector):
    if isinstance(selector, dict):
        require(set(selector) == {"model", "rows"}, f"Unexpected Brainboxes selector {selector!r}")
        model_id, groups = selector["model"], tuple(selector["rows"])
    else:
        model_id, groups = selector, DEFAULT_ROWS
    require(groups and set(groups) <= ROWS.keys() and len(set(groups)) == len(groups),
            f"Unexpected Brainboxes row groups {groups!r}")
    tables = [table for table in html_tables(data) if table["context"].get("h2", {}).get("id") == model_id]
    require(len(tables) == 1, f"Brainboxes {model_id} table missing")
    require(tables[0]["rows"][0] == ["Function", "Modbus Access Type", "Function Codes", "Logical Address",
                                     "984 Style Address", "IEC 61131 Address"],
            f"Brainboxes {model_id}: unexpected table header")
    channels = declared_channels(data, model_id)
    model = model_id.upper()
    wanted = {ROWS[group][:3]: group for group in groups}
    points = {}
    for row in tables[0]["rows"][1:]:
        group = wanted.get(tuple(row[:3]))
        if group is None:
            continue
        table, kind = ROWS[group][3:]
        require(group not in points and len(row) == 6, f"Unexpected Brainboxes {group} row")
        first, last = span(row[3], r"0x([0-9a-f]{4})\s*[-–]\s*([0-9a-f]{1,4})", 16)
        first_ref, last_ref = span(row[4], r"(\d{5})\s*[-–]\s*(\d{1,5})", 10)
        require(first_ref - BASES[table] == first and last_ref - first_ref == last - first,
                f"Brainboxes {group}: logical and 984-style addresses disagree")
        require(last - first + 1 == channels[group],
                f"Brainboxes {model} {group}: {last - first + 1} rows for {channels[group]} channels")
        points[group] = []
        for channel, address in enumerate(range(first, last + 1)):
            point = {"id": f"{group}_{channel}", "table": table, "address": address, "type": kind}
            if "," in row[2]:
                point["description"] = f"Vendor function codes {row[2]}; read-only in this contract."
            point["source"] = {"address": f"0x{address:04X}", "reference": f"{model} product data table"}
            points[group].append(point)
    missing = [group for group in groups if group not in points]
    require(not missing, f"Brainboxes {model} rows missing: {missing}")
    return [point for group in groups for point in points[group]]
