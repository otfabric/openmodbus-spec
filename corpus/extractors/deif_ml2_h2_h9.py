"""DEIF Multi-line 2 options H2 and H9 Modbus PDF: measurement and alarm/status tables.

Both tables are read with function code 04h. Each table has one column per product; an "X" marks a
standard feature, an empty cell means not available, and a number refers to an option or terminal.
The product columns are rotated header text, so rows and columns are rebuilt from pdftotext word
boxes. The selector is the product column label, e.g. "AGC 111".
"""
import functools
import re
import subprocess
from html import unescape

from sourcelib import pdf_pages, require

MEASUREMENT = ("Measurement table (read only) (function code 04h)", 43, 58)
STATUS = ("Alarm and status table (read only) (function code 04h)", 80, 89)
CONFIGURABLE = ("Configurable area (read only) (function code 04h)", 11)
EXAMPLE_PAGE = 198

# Text columns by word xMin; product columns start 15 pt left of the leftmost product header.
MEASUREMENT_COLUMNS = (("address", 70, 105), ("hilo", 105, 135), ("abbreviation", 135, 188),
                       ("content", 188, None))
STATUS_COLUMNS = (("address", 105, 140), ("bit", 140, 170), ("channel", 170, 200), ("content", 200, None))
KEY_FORMATS = {"address": r"\d{3,4}-?", "hilo": r"\[(?:Hi|Lo)\]|\d{1,2}", "bit": r"\d{1,2}", "channel": r"\d{4}"}
TEXT_HEADERS = {"Address", "Bit", "Channel"}
LINE_TOLERANCE = 3.0
ROW_GAP = 13.0
MARK_TOLERANCE = 12.0

# Measurement rows: content label -> (point ID, type, unit bracket in the label, UCUM unit).
# Rows without a bracket take their unit from the label wording, if any.
MEASUREMENTS = {
    "Generator voltage L1-L2 [V]": ("generator_voltage_l1_l2", "u16", "V", "V"),
    "Generator voltage L2-L3 [V]": ("generator_voltage_l2_l3", "u16", "V", "V"),
    "Generator voltage L3-L1 [V]": ("generator_voltage_l3_l1", "u16", "V", "V"),
    "Generator voltage L1-N [V]": ("generator_voltage_l1_n", "u16", "V", "V"),
    "Generator voltage L2-N [V]": ("generator_voltage_l2_n", "u16", "V", "V"),
    "Generator voltage L3-N [V]": ("generator_voltage_l3_n", "u16", "V", "V"),
    "Generator f L1 [Hz/100]": ("generator_frequency_l1", "u16", "Hz/100", "Hz"),
    "Generator current L1 [A]": ("generator_current_l1", "u16", "A", "A"),
    "Generator current L2 [A]": ("generator_current_l2", "u16", "A", "A"),
    "Generator current L3 [A]": ("generator_current_l3", "u16", "A", "A"),
    "Absolute. run hours": ("run_hours", "u32", None, "h"),
    "No. of alarms": ("alarm_count", "u16", None, None),
    "Start attempts": ("start_attempts", "u16", None, None),
    "DC supply term. 1-2 [V/10]": ("dc_supply_voltage", "u16", "V/10", "V"),
    "Cos-phi Inductive/Capacitive 0=Inductive, 1=Capacitive": ("cos_phi_inductive_capacitive", "enum", None, None),
    "RPM": ("engine_speed", "u16", None, "/min"),
    "Fan A running hours": ("fan_a_running_hours", "u32", None, "h"),
}
BRACKET_UNITS = {"V": "V", "A": "A", "Hz": "Hz"}
LABEL_UNITS = {"run hours": "h", "running hours": "h", "RPM": "/min"}

# Alarm/status registers: register label -> (point ID, {row label: flag name}).
FLAG_WORDS = {
    "Multi-functional input": ("engine_alarms", {
        "Overspeed 1": "overspeed_1",
        "Overspeed 2": "overspeed_2",
        "Crank failure": "crank_failure",
        "Running feedback failure": "running_feedback_failure",
        "MPU wire failure": "mpu_wire_failure",
        "Hz/V failure": "hz_v_failure",
        "Start failure": "start_failure",
    }),
    "Status": ("status_flags", {
        "Mains failure": "mains_failure",
        "MB pos. ON": "mb_position_on",
        "DG ramp down": "dg_ramp_down",
        "Start regulation": "start_regulation",
        "GB pos. ON": "gb_position_on",
        "GB synchronising": "gb_synchronising",
        "Engine running": "engine_running",
        "Running detect. timer expired": "running_detection_timer_expired",
        "DG Hz/V OK, timer expired": "dg_hz_v_ok_timer_expired",
        "Battery test": "battery_test",
        "Printing log": "printing_log",
        "GB position OFF": "gb_position_off",
        "MB position OFF": "mb_position_off",
        "BB Hz/V OK": "bb_hz_v_ok",
        "MB synchronising": "mb_synchronising",
    }),
    "General/Modes": ("mode_flags", {
        "Block mode": "block_mode",
        "Manual mode": "manual_mode",
        "Semi auto mode": "semi_auto_mode",
        "Auto mode": "auto_mode",
        "Test": "test",
        "Island": "island",
        "AMF": "amf",
        "Peak shaving": "peak_shaving",
        "Fixed power": "fixed_power",
        "Mains power export": "mains_power_export",
        "Load takeover": "load_takeover",
        "Power management": "power_management",
        "AMF active": "amf_active",
    }),
}

# Cross-check: the points each product column must yield. A row the product does not mark is left
# out; this set makes a lost or extra mark fail loudly instead.
_AGC3 = {*(entry[0] for entry in MEASUREMENTS.values()), *(entry[0] for entry in FLAG_WORDS.values())}
EXPECTED = {
    "AGC-3": _AGC3 - {"fan_a_running_hours"},
    "AGC 111": _AGC3,
    "AGC 110": {"alarm_count", "dc_supply_voltage", "engine_speed", "fan_a_running_hours",
                "engine_alarms", "status_flags", "mode_flags"},
}

WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')
PAGE = re.compile(r"<page\b[^>]*>(.*?)</page>", re.DOTALL)


def bbox_pages(data, first, last):
    """Word boxes (x0, y0, x1, y1, text) of PDF pages first..last, keyed by page number."""
    command = ["pdftotext", "-f", str(first), "-l", str(last), "-bbox-layout", "-enc", "UTF-8", "-", "-"]
    result = subprocess.run(command, input=data, capture_output=True, check=True, timeout=120)
    pages = PAGE.findall(result.stdout.decode("utf-8"))
    require(len(pages) == last - first + 1, f"DEIF PDF pages {first}-{last}: got {len(pages)} pages")
    return {first + index: [(float(x0), float(y0), float(x1), float(y1), unescape(text))
                            for x0, y0, x1, y1, text in WORD.findall(page)]
            for index, page in enumerate(pages)}


def page_title(words):
    return " ".join(word[4] for word in sorted(words, key=lambda w: w[0]) if 40 < word[1] < 56)


def header_columns(words, page):
    """Rotated header labels by x centre, and the y where the header ends (bottom of 'Content')."""
    content = [word for word in words if word[4] == "Content" and word[1] < 260]
    require(len(content) == 1, f"DEIF page {page}: table header 'Content' not found once")
    bottom = content[0][3]
    stacks = {}
    for x0, y0, x1, y1, text in words:
        if y1 <= bottom + 2 and y1 - y0 > 1.5 * (x1 - x0) and len(text) > 1:
            stacks.setdefault(round((x0 + x1) / 2), []).append((y0, text))
    labels = {centre: " ".join(text for _, text in sorted(parts)) for centre, parts in stacks.items()}
    products = {centre: label for centre, label in labels.items() if label not in TEXT_HEADERS}
    require(len(products) >= 10, f"DEIF page {page}: product header columns not found")
    names = list(products.values())
    require(len(names) == len(set(names)), f"DEIF page {page}: duplicate product columns {names}")
    return products, bottom


def table_rows(data, title, first, last, columns):
    """Rows of one table over a page range, in reading order.

    A row starts at a line with a key-column token (address, [Hi]/[Lo], bit, channel) or at a line
    at least ROW_GAP below the previous line; shorter steps are wrapped text of the same row.
    Product marks belong to the row whose vertical band contains them.
    """
    rows = []
    group = None
    for page, words in bbox_pages(data, first, last).items():
        require(title in page_title(words), f"DEIF page {page}: header {title!r} missing")
        products, bottom = header_columns(words, page)
        lowest = min(products) - 15
        footer = [word[1] for word in words if word[4] == "DEIF" and word[1] > 480 and word[0] < 100]
        require(len(footer) == 1, f"DEIF page {page}: footer not found")
        body = [word for word in words if bottom + 1 < word[1] < footer[0] - 1]
        text = [word for word in body if word[0] < lowest]
        marks = [word for word in body if word[0] >= lowest]

        lines = []
        for word in sorted(text, key=lambda w: (w[1], w[0])):
            if lines and word[1] - lines[-1][0] <= LINE_TOLERANCE:
                lines[-1][1].append(word)
            else:
                lines.append((word[1], [word]))
        page_rows = []
        previous = None
        for y, line in lines:
            cells = {}
            for word in line:
                name = next((name for name, low, high in columns
                             if word[0] >= low and (high is None or word[0] < high)), None)
                require(name is not None, f"DEIF page {page}: text {word[4]!r} left of the table")
                cells.setdefault(name, []).append(word)
            keys = {name: " ".join(word[4] for word in cells[name]) for name in KEY_FORMATS if name in cells}
            for name, value in keys.items():
                require(re.fullmatch(KEY_FORMATS[name], value),
                        f"DEIF page {page}: unexpected {name} cell {value!r} at y={y:.1f}")
            if keys or previous is None or y - previous >= ROW_GAP:
                group = keys.get("address", group)
                page_rows.append({"page": page, "y": y, "group": group, **keys, "lines": [], "marks": {}})
            page_rows[-1]["lines"].append(cells)
            previous = y
        require(page_rows, f"DEIF page {page}: no table rows")

        for x0, y0, x1, _, value in marks:
            centre = min(products, key=lambda c: abs(c - (x0 + x1) / 2))
            require(abs(centre - (x0 + x1) / 2) <= MARK_TOLERANCE,
                    f"DEIF page {page}: mark {value!r} at x={x0:.1f} is not under a product column")
            band = [row for row in page_rows if row["y"] - 2.5 <= y0]
            require(band, f"DEIF page {page}: mark {value!r} above the first row")
            band[-1]["marks"].setdefault(products[centre], []).append(value)
        for row in page_rows:
            for name in ("abbreviation", "content"):
                row[name] = " ".join(word[4] for cells in row["lines"] for word in cells.get(name, []))
            row["marks"] = {label: " ".join(values) for label, values in row["marks"].items()}
        rows.extend(page_rows)
    return rows


def check_document(data):
    """Document identity, product scope, and the evidence that table addresses are PDU addresses."""
    cover, scope = pdf_pages(data, 1, 2)
    require("Document no.: 4189340442Z" in cover, "DEIF: document number 4189340442Z missing")
    require(re.search(r"^AGC-3\s+SW version 3\.6x\.x or later\s*$", scope, re.MULTILINE)
            and re.search(r"^AGC 100\s+SW version 4\.0x\.x or later\s*$", scope, re.MULTILINE),
            "DEIF: AGC-3 / AGC 100 software scope missing on page 2")

    title, page = CONFIGURABLE
    words = bbox_pages(data, page, page)[page]
    require(title in page_title(words), f"DEIF page {page}: header {title!r} missing")
    addresses = sorted((word for word in words if word[0] < 110 and word[1] > 300 and word[4].isdigit()),
                       key=lambda word: word[1])
    require([word[4] for word in addresses[:2]] == ["0", "1"],
            f"DEIF page {page}: configurable area does not start at address 0")

    example = pdf_pages(data, EXAMPLE_PAGE)[0]
    stated = re.search(r"Address 4000 \+ 413 = (\d+)d = ([0-9A-F]+)h", example)
    request = re.search(r"Tx:\s+01h 03h ([0-9A-F]{2})h ([0-9A-F]{2})h 00h 01h", example)
    require(stated and request, f"DEIF page {EXAMPLE_PAGE}: worked address example missing")
    require(int(stated.group(1)) == int(stated.group(2), 16) == int("".join(request.groups()), 16) == 4413,
            f"DEIF page {EXAMPLE_PAGE}: table address and request PDU address disagree")


@functools.lru_cache(maxsize=1)
def document_rows(data):
    check_document(data)
    return (table_rows(data, *MEASUREMENT, MEASUREMENT_COLUMNS),
            table_rows(data, *STATUS, STATUS_COLUMNS))


def mark(row, product):
    value = row["marks"].get(product, "")
    require(value in ("", "X"), f"DEIF {row.get('address')} {row['content']!r}: {product} cell {value!r}")
    return value == "X"


def measurement_points(rows, product):
    points = []
    for label, (point_id, kind, bracket, unit) in MEASUREMENTS.items():
        found = [index for index, row in enumerate(rows) if row["content"] == label and row.get("hilo") != "[Lo]"]
        require(len(found) == 1, f"DEIF measurement table: {label!r} found {len(found)} times")
        row = rows[found[0]]
        require("address" in row, f"DEIF {label!r}: row has no address")
        address = int(row["address"])
        if kind == "u32":
            low = rows[found[0] + 1]
            require(row.get("hilo") == "[Hi]" and low.get("hilo") == "[Lo]"
                    and low.get("address") == str(address + 1),
                    f"DEIF {label!r}: expected a [Hi]/[Lo] register pair at {address}")
            require(low["content"] in ("", label) and low["marks"].get(product, "") in ("", row["marks"].get(product)),
                    f"DEIF {label!r}: [Lo] row disagrees with the [Hi] row")
        else:
            require("hilo" not in row, f"DEIF {label!r}: unexpected {row.get('hilo')} at {address}")
        same = [other for other in rows if other["group"] == row["address"] and other["content"]]
        marked = [other for other in same if mark(other, product)]
        if not mark(row, product):
            require(not marked, f"DEIF {address}: {product} marks another row than {label!r}")
            continue
        require(marked == [row], f"DEIF {address}: {product} marks more than one row")

        point = {"id": point_id, "address": address, "type": "u16" if kind == "enum" else kind}
        if kind == "u32":
            point["wordOrder"] = "big"  # [Hi] at the lower address, [Lo] at the next
        brackets = re.findall(r"\[([^\]]*)\]", label)
        if bracket is None:
            require(not brackets, f"DEIF {label!r}: unexpected unit bracket")
            if unit is not None:
                require(any(word in label and value == unit for word, value in LABEL_UNITS.items()),
                        f"DEIF {label!r}: label does not state unit {unit}")
        else:
            require(brackets == [bracket], f"DEIF {label!r}: expected [{bracket}]")
            scale = re.fullmatch(r"(\w+)(?:/(10+))?", bracket)
            require(scale and BRACKET_UNITS.get(scale.group(1)) == unit, f"DEIF {label!r}: unexpected unit")
            if scale.group(2):
                point["conversion"] = {"exponent10": -(len(scale.group(2)) - 1)}
        if unit is not None:
            point["unit"] = unit
        if kind == "enum":
            values = re.findall(r"\b(\d+)=([A-Z][a-z]+)\b", label)
            require(len(values) >= 2 and len({value for value, _ in values}) == len(values),
                    f"DEIF {label!r}: enumeration values not found")
            point["enum"] = {"values": [{"value": int(value), "name": name.lower(), "label": name}
                                        for value, name in values]}
        point["aliases"] = [label]
        if bracket is None and unit is not None:
            point["description"] = "Unit taken from the row label; the document gives no unit bracket or scale."
        notation = f"{address} [Hi], {address + 1} [Lo]" if kind == "u32" else str(address)
        point["source"] = {"address": notation, "page": row["page"], "reference": MEASUREMENT[0]}
        points.append(point)
    return points


def flag_points(rows, product):
    """Bit rows per register. A register row either heads its bits or is bit 0 itself; an address
    range such as '1020-' / '1024' points to another manual and is skipped."""
    registers = []
    register = last = None
    in_range = False
    for row in rows:
        if "address" in row:
            number = int(row["address"].rstrip("-"))
            require(last is None or number == last + 1 or in_range,
                    f"DEIF alarm table: register {number} does not follow {last}")
            last, register = number, None
            if row["address"].endswith("-") or in_range:
                in_range = row["address"].endswith("-")
                continue
            register = {"address": number, "label": None, "page": row["page"], "rows": []}
            registers.append(register)
            if "bit" not in row:
                require(not row["marks"], f"DEIF register {number}: marks on the heading row")
                register["label"] = row["content"]
                continue
        if register is None:
            continue
        if "bit" in row:
            register["bit"] = int(row["bit"])
            require(0 <= register["bit"] <= 15, f"DEIF register {register['address']}: bit {row['bit']}")
        require("bit" in register, f"DEIF register {register['address']}: row before bit 0")
        register["rows"].append((register["bit"], row))

    points = []
    for name, (point_id, selected) in FLAG_WORDS.items():
        found = [register for register in registers if register["label"] == name]
        require(len(found) == 1, f"DEIF alarm table: register {name!r} found {len(found)} times")
        register = found[0]
        labels = {row["content"] for _, row in register["rows"]}
        require(set(selected) <= labels, f"DEIF {name}: rows missing: {sorted(set(selected) - labels)}")
        flags = {}
        pages = set()
        for bit, row in register["rows"]:
            value = row["marks"].get(product, "")
            if value == "X":
                require(row["content"] in selected,
                        f"DEIF {name} bit {bit}: {product} marks unselected row {row['content']!r}")
                require(bit not in flags, f"DEIF {name} bit {bit}: {product} marks two rows")
                flags[bit] = {"bit": bit, "name": selected[row["content"]], "label": row["content"]}
                pages.add(row["page"])
            else:
                # Empty: not available. A number refers to an option or input, so the bit is not standard.
                require(value == "" or re.fullmatch(r"\d+(?:\.\d+)?", value),
                        f"DEIF {name} bit {bit}: {product} cell {value!r}")
        if not flags:
            continue
        where = f"pages {min(pages)}-{max(pages)}" if len(pages) > 1 else f"page {min(pages)}"
        points.append({
            "id": point_id,
            "address": register["address"],
            "type": "u16",
            "flags": {"flags": [flags[bit] for bit in sorted(flags)]},
            "aliases": [name],
            "description": f"Bits the document marks as standard (X) for {product} ({where}); "
                           f"bits that are empty or refer to an option or input are not named.",
            "source": {"address": str(register["address"]), "page": register["page"], "reference": STATUS[0]},
        })
    return points


def extract(data, selector=None):
    require(selector in EXPECTED, f"DEIF: unknown product column {selector!r}")
    measurement, status = document_rows(data)
    points = measurement_points(measurement, selector) + flag_points(status, selector)
    ids = {point["id"] for point in points}
    require(ids == EXPECTED[selector],
            f"DEIF {selector}: missing {sorted(EXPECTED[selector] - ids)}, extra {sorted(ids - EXPECTED[selector])}")
    return sorted(points, key=lambda point: point["address"])
