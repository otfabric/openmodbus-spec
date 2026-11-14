"""SmartGen HGM9530N Genset Controller Communication Protocol (PDF): the function code 03H map data field.

Section 5.1 (pages 12-18) lists decimal register addresses from 0000 (0109 is followed by 0110). The worked
function 03H example on page 9 puts the starting address 0026H unchanged into the request ("00 26"), so the
table addresses are zero-based PDU addresses of the holding registers that function 03H reads.

Two-register values are written as an "LSB" row followed by an "MSB" row, so the low-order word is at the lower
address. The "(*10)", "(*100)" and "(*1000)" marks are read as "register = value x N"; the document does not
define them (see the class-09 report). Rows the document does not mark "Signed" are read as unsigned. The
document has no unit column: only units named in the item text are used.
"""
import re

from sourcelib import pdf_pages, require

PAGES = 26
TABLE_PAGES = range(12, 19)
FORM_PAGE = 26
HEADER = "HGM9530N Genset Controller Communication Protocol"
TABLE_HEADER = re.compile(r"^Address\s+Item\s+Description\s+Bytes$")
SIZE = re.compile(r"^(\d+)(Bytes|bit)$")
SCALE = re.compile(r"^(Signed ?)?(LSB |MSB )?(?:\(\*(10|100|1000)\))?$")

# Item text -> (point ID, expected description, registers, UCUM unit from the item text or None, description).
NO_UNIT = "The document states no unit for this register."
VALUES = {
    "Gen UAB": ("generator_voltage_ab", "LSB (*10)", 2, None, NO_UNIT),
    "Gen UA": ("generator_voltage_a", "LSB (*10)", 2, None, NO_UNIT),
    "Gen UB": ("generator_voltage_b", "LSB (*10)", 2, None, NO_UNIT),
    "Gen UC": ("generator_voltage_c", "LSB (*10)", 2, None, NO_UNIT),
    "Gen Frequency": ("generator_frequency", "(*100)", 1, None, NO_UNIT),
    "A-Phase Current": ("generator_current_a", "(*10)", 1, None, NO_UNIT),
    "B-Phase Current": ("generator_current_b", "(*10)", 1, None, NO_UNIT),
    "C-Phase Current": ("generator_current_c", "(*10)", 1, None, NO_UNIT),
    "Total Active Power": ("active_power_total", "Signed LSB (*10)", 2, None, NO_UNIT),
    "Average Power Factor": ("power_factor_average", "Signed (*1000)", 1, None, None),
    "Engine Speed": ("engine_speed", "", 1, None, NO_UNIT),
    "Battery Voltage": ("battery_voltage", "(*10)", 1, None, NO_UNIT),
    "Total Running Time (Hour)": ("running_hours", "", 1, "h",
                                  "The document lists the minutes and seconds of the total running time in the "
                                  "next two registers."),
    "Total Start Times": ("start_count", "", 1, None, None),
}
# Item text -> (point ID, form heading on the form page, expected values).
ENUMS = {
    "Gen Status": ("generator_status", "5.5 GENERATOR STATUS FORM", 16),
    "Gen Breaker Status": ("generator_breaker_status", "5.7 BREAKER STATUS FORM", 8),
}
FLAGS = ("Common Alarm", "common_status")
EXPONENTS = {None: None, "10": -1, "100": -2, "1000": -3}


def slug(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    require(words, f"SmartGen HGM9530N: cannot name {text!r}")
    return "_".join(words)


def table_lines(pages):
    """Return the table lines as dicts with page, address, item, description and size."""
    lines = []
    for number in TABLE_PAGES:
        page = pages[number - 1].split("\n")
        heads = [index for index, line in enumerate(page) if TABLE_HEADER.match(line.strip())]
        require(len(heads) == 1, f"SmartGen HGM9530N page {number}: table header not found once")
        footer = [index for index, line in enumerate(page)
                  if re.fullmatch(rf"HGM9530N Genset Controller\s+2018-12-21\s+Version 1\.0\s+Page {number} of 26",
                                  line.strip())]
        require(len(footer) == 1, f"SmartGen HGM9530N page {number}: footer not found once")
        item_column = None
        for line in page[heads[0] + 1:footer[0]]:
            if not line.strip():
                continue
            match = re.match(r"^(\d{4})(-?)", line)
            address = match.group(1) if match else None
            rest = line[match.end():] if match else line
            offset = match.end() if match else 0
            parts = [(offset + part.start(), part.group()) for part in re.finditer(r"\S+(?: \S+)*", rest)]
            entry = {"page": number, "address": address, "range": bool(match and match.group(2)),
                     "item": "", "description": [], "size": None}
            for column, text in parts:
                if SIZE.match(text):
                    require(entry["size"] is None, f"SmartGen HGM9530N page {number}: two sizes in {line!r}")
                    entry["size"] = text
                elif column < 20:
                    # Item text is left-aligned right after the address column, at one column per page.
                    item_column = column if item_column is None else item_column
                    require(column == item_column and not entry["item"] and not entry["description"],
                            f"SmartGen HGM9530N page {number}: item text out of place: {line!r}")
                    entry["item"] = text
                else:
                    require(column > 30, f"SmartGen HGM9530N page {number}: unexpected text at column {column}: {line!r}")
                    entry["description"].append(text)
            entry["description"] = " ".join(entry["description"])
            lines.append(entry)
    return lines


def find_item(lines, item):
    found = [index for index, line in enumerate(lines) if line["item"] == item and line["address"] is not None]
    require(len(found) == 1, f"SmartGen HGM9530N: {len(found)} rows for {item!r}")
    return found[0]


def form_entries(page, heading, count):
    lines = page.split("\n")
    starts = [index for index, line in enumerate(lines) if line.strip() == heading]
    require(len(starts) == 1, f"SmartGen HGM9530N: {heading!r} not found once")
    require(re.fullmatch(r"No\.\s+Content\s+Description", lines[starts[0] + 1].strip()),
            f"SmartGen HGM9530N {heading}: form header missing")
    entries = {}
    for line in lines[starts[0] + 2:]:
        if not line.strip():
            continue
        match = re.fullmatch(r"\s+(\d{1,2})\s{2,}(\S+(?: \S+)*)(?:\s{2,}(\S.*?))?\s*", line)
        if not match:
            break
        value = int(match.group(1))
        require(value not in entries, f"SmartGen HGM9530N {heading}: value {value} listed twice")
        entries[value] = match.group(2)
    require(sorted(entries) == list(range(count)), f"SmartGen HGM9530N {heading}: expected values 0-{count - 1}")
    return entries


def extract(data, selector):
    require(selector is None, "SmartGen HGM9530N takes no selector")
    pages = pdf_pages(data, 1, PAGES)
    require(all(page.lstrip().startswith(HEADER) for page in pages[3:]), "SmartGen HGM9530N: running header missing")
    require(re.search(r"2018-12-21\s+1\.0\s+Original release\.", pages[1]), "SmartGen HGM9530N: expected version 1.0")
    require(pages[2].lstrip().startswith("This protocol is only suit for HGM9530N genset controller."),
            "SmartGen HGM9530N: model scope statement missing")
    flat = " ".join(" ".join(pages[5:7]).split())
    require("03H Read Holding Registers" in flat, "SmartGen HGM9530N page 6: function 03H missing")
    require("high byte is in advance" in flat, "SmartGen HGM9530N page 6: byte order statement missing")
    limit = re.search(r"Maximum number of readable registers is (\d+) each time\.", flat)
    require(limit, "SmartGen HGM9530N page 6: read limit missing")
    example = " ".join(pages[8].split())
    require("starting address is 3 data of 0026H" in example and "00 Starting address is 0026 26" in example
            and "The content of address 0026H" in example, "SmartGen HGM9530N page 9: function 03H example missing")
    require("5.1 FUNCTION CODE 03H, 06H MAP DATA FIELD" in pages[11], "SmartGen HGM9530N page 12: section 5.1 missing")

    lines = table_lines(pages)
    numbered = [int(line["address"]) for line in lines if line["address"] is not None]
    require(numbered[0] == 0 and numbered == sorted(numbered), "SmartGen HGM9530N: addresses do not ascend from 0000")
    require({109, 110} <= set(numbered), "SmartGen HGM9530N: decimal address sequence 0109, 0110 missing")

    points = []
    for item, (point_id, description, registers, unit, text) in VALUES.items():
        index = find_item(lines, item)
        row = lines[index]
        address = int(row["address"])
        require((row["description"], row["size"], row["range"]) == (description, "2Bytes", False),
                f"SmartGen HGM9530N {item}: unexpected description or size {row}")
        signed, half, scale = SCALE.match(description).groups()
        if registers == 2:
            high = lines[index + 1]
            require(half == "LSB " and high["address"] is not None and int(high["address"]) == address + 1
                    and (high["item"], high["size"]) == ("", "2Bytes")
                    and high["description"] == description.replace("LSB", "MSB"),
                    f"SmartGen HGM9530N {item}: expected an MSB row at {address + 1}")
            point = {"id": point_id, "aliases": [item], "address": address,
                     "type": "i32" if signed else "u32", "wordOrder": "little"}
            source_address = f"{row['address']}-{high['address']}"
        else:
            require(half is None, f"SmartGen HGM9530N {item}: unexpected LSB/MSB mark")
            point = {"id": point_id, "aliases": [item], "address": address, "type": "i16" if signed else "u16"}
            source_address = row["address"]
        if EXPONENTS[scale] is not None:
            point["conversion"] = {"exponent10": EXPONENTS[scale]}
        if unit:
            point["unit"] = unit
        if text:
            point["description"] = text
        point["source"] = {"address": source_address, "page": row["page"], "reference": f"5.1 map data field, {item}"}
        points.append(point)

    for item, (point_id, heading, count) in ENUMS.items():
        index = find_item(lines, item)
        row, form = lines[index], lines[index + 1]
        require((row["size"], f"{row['description']} {form['description']}") == ("2Bytes", heading.split(" ", 1)[1])
                and form["address"] is None and not form["item"], f"SmartGen HGM9530N {item}: form reference missing")
        entries = form_entries(pages[FORM_PAGE - 1], heading, count)
        points.append({
            "id": point_id, "aliases": [item], "address": int(row["address"]), "type": "u16",
            "enum": {"values": [{"value": value, "name": slug(label), "label": label}
                                for value, label in sorted(entries.items())]},
            "source": {"address": row["address"], "page": row["page"],
                       "reference": f"5.1 map data field, {item}; {heading[4:].title()} (page {FORM_PAGE})"},
        })

    item, point_id = FLAGS
    index = find_item(lines, item)
    group = lines[index:index + 16]
    require(group[0]["address"] == "0000" and all(line["address"] is None for line in group[1:]),
            "SmartGen HGM9530N: common alarm register is not 16 bit rows at 0000")
    require(all(line["size"] == "1bit" for line in group) and lines[index + 16]["size"] != "1bit",
            "SmartGen HGM9530N: common alarm register is not 16 bits")
    marks = [line["description"] for line in group]
    require(marks[0] == "1 for active(LSB)" and marks[-1] == "1 for active(MSB)"
            and set(marks[1:-1]) == {"1 for active"}, "SmartGen HGM9530N: LSB/MSB marks of register 0000 changed")
    flags = [{"bit": bit, "name": slug(line["item"]), "label": line["item"]}
             for bit, line in enumerate(group) if line["item"] != "Reserved"]
    points.append({
        "id": point_id, "label": "Common alarm and mode bits", "aliases": [item], "address": 0, "type": "u16",
        "flags": {"flags": flags},
        "description": "Bit 0 is the row the document marks LSB; reserved bits are left out.",
        "source": {"address": group[0]["address"], "page": group[0]["page"], "reference": "5.1 map data field, 0000"},
    })
    points.sort(key=lambda point: point["address"])
    return {"points": points, "constraints": {"maxReadRegisters": int(limit.group(1))}}
