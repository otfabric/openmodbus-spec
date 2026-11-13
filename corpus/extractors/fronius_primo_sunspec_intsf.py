"""Fronius Modbus SunSpec maps ZIP: Int&SF inverter register map (XLSX) and state-code CSVs.

The workbook lists 1-based register numbers. The pinned evidence document, the Fronius
Datamanager Modbus TCP & RTU operating instructions (HTML), states the rest and is checked
here: section "Register addresses" (register 40001 is read at address 40000; a worked read of
Mn shows the string byte and register order), "Unavailable
data records" (the not-supported value per SunSpec type), "Scale Factors" (sunssf is a
signed 16-bit integer), "Changing the Data Type" (F_ModelType values) and the SunSpec and
Fronius operating-code tables (cross-checked against St.csv and StVnd.csv).

Only the Common block and the inverter model (101, 102, 103) are mapped: they are the first
two SunSpec blocks and the Common block has a fixed length, so their position does not
depend on which later models are present. 32-bit values are left out because neither
document states their word order.
"""
from html.parser import HTMLParser
import re

from sourcelib import csv_rows, require, xlsx_rows, xlsx_sheets, zip_member

MANUAL = "fronius-datamanager-modbus-manual"
MANUAL_EDITION = "033-24022026"

FOLDER = "SE_EI_Modbus_Sunspec_Maps_State_Codes_Events/"
WORKBOOK = FOLDER + "Inverter_Register_Map_Int&SF_v1.0_with_SYMOHYBRID_MODEL_124.xlsx"
ARCHIVE_VERSION = "Version 1.1.7-0"
TITLE = "Fronius Datamanager Register Map: Integer Inverter Model (101, 102, 103)"
HEADER = {"A": "Start", "B": "End", "C": "Size", "D": "R/W", "E": "Function codes", "F": "Name",
          "G": "Description", "H": "Type", "I": "Units", "J": "Scale Factor", "K": "Range of values"}
MODEL_HEADER = {**HEADER, "A": "Start Offset", "B": "End Offset", "D": "RW"}
MODEL_SHEETS = {"fronius": "Fronius Register", "common": "C001 Common", "inverter": "I10X Inverter"}

# Fronius name -> (point ID, block, expected vendor type, expected vendor unit).
SELECTED = {
    "F_ModelType": ("sunspec_model_type", "fronius", "uint16", None),
    "Mn": ("manufacturer", "common", "String32", None),
    "Md": ("model_name", "common", "String32", None),
    "Vr": ("inverter_software_version", "common", "String16", None),
    "A": ("ac_current", "inverter", "uint16", "A"),
    "A_SF": ("ac_current_sf", "inverter", "sunssf", None),
    "PhVphA": ("ac_voltage_a_n", "inverter", "uint16", "V"),
    "V_SF": ("ac_voltage_sf", "inverter", "sunssf", None),
    "W": ("ac_power", "inverter", "int16", "W"),
    "W_SF": ("ac_power_sf", "inverter", "sunssf", None),
    "Hz": ("ac_frequency", "inverter", "uint16", "Hz"),
    "Hz_SF": ("ac_frequency_sf", "inverter", "sunssf", None),
    "DCA": ("dc_current", "inverter", "uint16", "A"),
    "DCA_SF": ("dc_current_sf", "inverter", "sunssf", None),
    "DCV": ("dc_voltage", "inverter", "uint16", "V"),
    "DCV_SF": ("dc_voltage_sf", "inverter", "sunssf", None),
    "DCW": ("dc_power", "inverter", "int16", "W"),
    "DCW_SF": ("dc_power_sf", "inverter", "sunssf", None),
    "St": ("operating_state", "inverter", "enum16", "Enumerated"),
    "StVnd": ("vendor_operating_state", "inverter", "enum16", "Enumerated"),
}
TYPES = {"uint16": "u16", "int16": "i16", "sunssf": "i16", "enum16": "u16"}
STRINGS = {"String16": 8, "String32": 16}
UNITS = {"A": "A", "V": "V", "W": "W", "Hz": "Hz"}
STATE_TABLES = {"St": "St.csv", "StVnd": "StVnd.csv"}
# Manual article holding the operating codes that each state table must match.
STATE_ARTICLES = {"St": "SunSpec Operating Codes", "StVnd": "Fronius Operating Codes"}
BREAKS = {"br", "p", "li", "div", "tr", "ul", "ol", "table", "h1", "h2", "h3", "h4", "h5", "h6"}


def words(text):
    return " ".join(text.split())


class _Manual(HTMLParser):
    """Lines and table cells of each <article class="page" title="..."> in the Fronius HTML manual.

    Each cell keeps its list items and its <br>/<p>-separated lines. Superscripts (footnote marks)
    and scripts are skipped.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.articles, self.article, self.depth = [], None, 0
        self.cells, self.item, self.skip = [], None, 0
        self.edition = None

    def newline(self):
        if self.article is not None:
            self.article["lines"].append("")
        if self.cells:
            self.cells[-1]["lines"].append("")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("sup", "script", "style"):
            self.skip += 1
        elif tag == "span" and attrs.get("id") == "extversion":
            self.edition = []
        elif tag == "article":
            if self.article is None and "page" in (attrs.get("class") or "").split():
                self.article = {"title": attrs.get("title"), "lines": [""], "cells": []}
                self.depth = 0
            self.depth += self.article is not None
        elif self.article is not None:
            if tag in ("td", "th"):
                self.cells.append({"items": [], "lines": [""]})
            elif tag == "li":
                self.item = []
        if tag in BREAKS:
            self.newline()

    def handle_endtag(self, tag):
        if tag in ("sup", "script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag == "span" and isinstance(self.edition, list):
            self.edition = words("".join(self.edition))
        elif tag == "article" and self.article is not None:
            self.depth -= 1
            if not self.depth:
                self.article["lines"] = [words(line) for line in self.article["lines"] if line.strip()]
                self.articles.append(self.article)
                self.article = None
        elif tag in ("td", "th") and self.cells:
            cell = self.cells.pop()
            cell["lines"] = [words(line) for line in cell["lines"] if line.strip()]
            self.article["cells"].append(cell)
        elif tag == "li" and self.item is not None:
            if self.cells:
                self.cells[-1]["items"].append(words("".join(self.item)))
            self.item = None
        if tag in BREAKS:
            self.newline()

    def handle_data(self, data):
        if self.skip:
            return
        if isinstance(self.edition, list):
            self.edition.append(data)
        if self.article is not None:
            self.article["lines"][-1] += data
        if self.cells:
            self.cells[-1]["lines"][-1] += data
        if self.item is not None:
            self.item.append(data)


def articles(manual, title):
    found = [article for article in manual.articles if article["title"] == title]
    require(found, f"Fronius manual: no article {title!r}")
    return found


def statement(manual, title, pattern):
    """Match a regex against the lines of an article; every copy of the article must agree."""
    results = set()
    for article in articles(manual, title):
        matches = [re.fullmatch(pattern, line) for line in article["lines"]]
        matches = [match.groups() for match in matches if match]
        require(len(matches) == 1, f"Fronius manual {title!r}: statement {pattern!r} found {len(matches)} times")
        results.add(matches[0])
    require(len(results) == 1, f"Fronius manual {title!r}: copies disagree")
    return results.pop()


def read_example(manual, title):
    """The first worked RTU read in an article: (register, start address, count, data bytes)."""
    results = set()
    for article in articles(manual, title):
        cells = [" ".join(cell["lines"]) for cell in article["cells"]]
        heading = r"1\. Request for four registers starting from register (\d+) \(Mn, Manufacturer\)"
        starts = [index for index, cell in enumerate(cells) if re.fullmatch(heading, cell)]
        require(starts, f"Fronius manual {title!r}: worked read example missing")
        frames = []
        for label in ("Send (bytes in hexadecimal)", "Receive (bytes in hexadecimal)"):
            index = cells.index(label, frames[-1][1] if frames else starts[0])
            index += 1
            while index < len(cells) and not cells[index]:
                index += 1
            end = index
            while end < len(cells) and re.fullmatch(r"[0-9A-F]{2}", cells[end]):
                end += 1
            frames.append(([int(cell, 16) for cell in cells[index:end]], end))
        (send, _), (receive, _) = frames
        require(len(send) == 8 and send[1] == 0x03 and receive[:2] == send[:2]
                and len(receive) == 3 + receive[2] + 2 == 3 + 2 * (send[4] << 8 | send[5]) + 2,
                f"Fronius manual {title!r}: unexpected worked read frames")
        register = int(re.fullmatch(heading, cells[starts[0]]).group(1))
        results.add((register, send[2] << 8 | send[3], send[4] << 8 | send[5], bytes(receive[3:3 + receive[2]])))
    require(len(results) == 1, f"Fronius manual {title!r}: copies disagree")
    return results.pop()


def manual_facts(html):
    manual = _Manual()
    manual.feed(html.decode("utf-8"))
    manual.close()
    require(manual.edition == MANUAL_EDITION, f"Fronius manual: edition {manual.edition!r}")
    title = "Register addresses"
    statement(manual, title, re.escape("Registers begin at 1 and do not represent a function code."))
    fronius_first, = statement(manual, title, r"Fronius Basic Register: (\d+)")
    sunspec_first, = statement(manual, title, r"SunSpec Basic Register: (\d+)")
    register, address, hex_address = statement(manual, title, r"To read register (\d+), use address (\d+) "
                                                                r"\(0x([0-9A-F]+)\)\.")
    less, = statement(manual, title, r"The register address that is output therefore always has (\d+) number "
                                     r"less than the actual register number\.")
    offset = int(register) - int(address)
    require(int(address) == int(hex_address, 16) and offset == int(less) and register == sunspec_first,
            "Fronius manual: register addresses statements disagree")
    example = read_example(manual, title)
    require(example[0] - offset == example[1], "Fronius manual: worked read example disagrees with the offset")

    statement(manual, "Scale Factors", re.escape('The data type "sunssf" is a signed integer with 16 bits.'))
    float_value, = statement(manual, "Changing the Data Type",
                             r"Float = (\d+) \(standard\): Inverter model 111, 112, or 113; .*")
    int_value, = statement(manual, "Changing the Data Type",
                           r"int\+SF = (\d+): Inverter model 101, 102, or 103; .*")

    tables = []
    for article in articles(manual, "Unavailable data records"):
        cells = article["cells"]
        pairs = [(left["items"], right["lines"]) for left, right in zip(cells, cells[1:])
                 if left["items"] and len(left["items"]) == len(right["lines"])]
        require(len(pairs) == 1, "Fronius manual: unavailable data records table not found")
        tables.append(pairs[0])
    require(all(table == tables[0] for table in tables), "Fronius manual: unavailable data records copies disagree")
    sentinels = {}
    for item, value in zip(*tables[0]):
        kind = re.match(r"\w+", item).group()
        bounds = re.search(r"\((?:[^;()]*; )?(-?\d+) to (-?\d+)\):$", item)
        require(kind not in sentinels, f"Fronius manual: duplicate type {kind}")
        sentinels[kind] = (bounds and (int(bounds.group(1)), int(bounds.group(2))), value)

    states = {}
    for name, title in STATE_ARTICLES.items():
        found = set()
        for article in articles(manual, title):
            texts = [" ".join(cell["lines"]) for cell in article["cells"]]
            require(texts[:3] == ["Name", "Value", "Description"], f"Fronius manual {title!r}: unexpected header")
            codes = {}
            for index in range(3, len(texts) - 2, 3):
                if not texts[index].startswith("I_STATUS_"):
                    break
                codes[int(texts[index + 1])] = texts[index]
            found.add(tuple(sorted(codes.items())))
        require(len(found) == 1, f"Fronius manual {title!r}: copies disagree")
        states[name] = dict(found.pop())
    return {"offset": offset, "fronius_first": int(fronius_first), "sunspec_first": int(sunspec_first),
            "example": example,
            "model_type": {"float": int(float_value), "int_sf": int(int_value)},
            "sentinels": sentinels, "states": states}


def not_supported(facts, kind):
    """Raw not-supported value of a 16-bit SunSpec type, in the point's integer type."""
    require(kind in facts["sentinels"], f"Fronius manual: no unavailable value for {kind}")
    bounds, text = facts["sentinels"][kind]
    require(bounds and re.fullmatch(r"0x[0-9A-F]{4}", text), f"Fronius manual: {kind} entry {text!r}")
    raw = int(text, 16)
    value = raw - 0x10000 if bounds[0] < 0 and raw & 0x8000 else raw
    require(not bounds[0] <= value <= bounds[1], f"Fronius manual: {kind} value {text} lies in the valid range")
    return value


def identifier(text):
    name = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    require(re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name), f"Fronius: no identifier for {text!r}")
    return name


def complete_map(workbook):
    """Split the Complete Map sheet into blocks; return {block: {name: (row_number, row)}}."""
    rows = list(xlsx_rows(workbook, "Complete Map"))
    require(rows and rows[0][1] == {"A": TITLE}, "Fronius Complete Map: unexpected title")
    blocks, current = [], None
    for number, row in rows[1:]:
        if row in (HEADER, MODEL_HEADER):
            current = {}
            blocks.append(current)
            continue
        require(current is not None, f"Fronius Complete Map row {number}: data before a header")
        name = row.get("F")
        require(name and name not in current, f"Fronius Complete Map row {number}: missing or duplicate name")
        current[name] = (number, row)
    named = {}
    for block in blocks:
        if "F_ModelType" in block:
            key = "fronius"
        elif "SID" in block:
            key = "common"
        elif block.get("ID", (0, {}))[1].get("K") == "101, 102, 103":
            key = "inverter"
        else:
            continue
        require(key not in named, f"Fronius Complete Map: two {key} blocks")
        named[key] = block
    require(named.keys() == {"fronius", "common", "inverter"}, "Fronius Complete Map: blocks missing")
    return named


def model_sheet(workbook, sheet):
    rows = list(xlsx_rows(workbook, sheet))
    require(rows and rows[0][1] == MODEL_HEADER, f"Fronius {sheet}: unexpected header")
    result = {}
    for number, row in rows[1:]:
        require(row.get("F") and row["F"] not in result, f"Fronius {sheet} row {number}: bad name")
        result[row["F"]] = row
    return result


def block_base(block, sheet, names):
    """Register number of offset 0, checked to agree for every listed name."""
    bases = set()
    for name in names:
        row, model_row = block[name][1], sheet[name]
        for column in "CEFHIJ":
            require(row.get(column) == model_row.get(column), f"Fronius {name}: maps disagree in column {column}")
        start, offset = int(row["A"]), int(model_row["A"])
        require(int(row["B"]) - start == int(model_row["B"]) - offset, f"Fronius {name}: maps disagree on extent")
        bases.add(start - offset)
    require(len(bases) == 1, f"Fronius: inconsistent block base {sorted(bases)}")
    return bases.pop()


def state_enum(archive, member, codes):
    values = []
    for line, row in csv_rows(zip_member(archive, FOLDER + member)):
        require(len(row) == 5 and int(row[0], 16) == int(row[1]), f"Fronius {member}:{line}: unexpected row")
        require(row[2].startswith("I_STATUS_"), f"Fronius {member}:{line}: unexpected state name")
        values.append({"value": int(row[1]), "name": identifier(row[2][len("I_STATUS_"):]), "label": row[3]})
    require(values and [value["value"] for value in values] == list(range(1, len(values) + 1)),
            f"Fronius {member}: states are not numbered 1..n")
    require({value["value"]: "I_STATUS_" + value["name"].upper() for value in values} == codes,
            f"Fronius {member}: disagrees with the operating codes in the manual")
    return {"values": values}


def range_enum(text):
    pairs = re.findall(r"(\d+):\s*(.+?)(?=\s+\d+:|$)", text)
    require(pairs and " ".join(f"{value}: {label}" for value, label in pairs) == text,
            f"Fronius: unexpected enumeration text {text!r}")
    return {"values": [{"value": int(value), "name": identifier(label), "label": label} for value, label in pairs]}


def extract(data, selector=None, evidence=None):
    require(evidence and MANUAL in evidence, f"Fronius: evidence document {MANUAL} missing")
    facts = manual_facts(evidence[MANUAL])
    info = zip_member(data, FOLDER + "_INFO.TXT").decode("ascii").strip()
    require(info == ARCHIVE_VERSION, f"Fronius archive version {info!r}")
    workbook = zip_member(data, WORKBOOK)
    require(xlsx_sheets(workbook)[0] == "Complete Map", "Fronius workbook: Complete Map is not the first sheet")
    blocks = complete_map(workbook)
    sheets = {key: model_sheet(workbook, sheet) for key, sheet in MODEL_SHEETS.items()}

    require(block_base(blocks["fronius"], sheets["fronius"], ["F_ModelType"]) == 0,
            "Fronius Register sheet and Complete Map disagree")
    require(min(int(row["A"]) for _, row in blocks["fronius"].values()) == facts["fronius_first"],
            "Fronius: first Fronius register differs from the manual")
    common, inverter = blocks["common"], blocks["inverter"]
    common_base = block_base(common, sheets["common"], ["SID", "ID", "L", "Mn", "Md", "Vr"])
    require("0x53756e53" in common["SID"][1]["K"] and int(common["SID"][1]["A"]) == common_base + 1
            == facts["sunspec_first"], "Fronius: SunSpec marker row differs from the manual")
    # The worked read returns the first registers of Mn: one ASCII character per byte, high byte
    # first, registers in ascending order (the draft's default byte and word order for strings).
    register, _, count, payload = facts["example"]
    require(int(common["Mn"][1]["A"]) == register and payload == common["Mn"][1]["K"].encode("ascii")[:2 * count]
            .ljust(2 * count, b"\0"), "Fronius: worked Mn read disagrees with the workbook")
    inverter_names = [name for name, (_, block, _, _) in SELECTED.items() if block == "inverter"]
    inverter_base = block_base(inverter, sheets["inverter"], ["ID", "L", *inverter_names])
    common_length = int(common["L"][1]["K"])
    require(int(inverter["ID"][1]["A"]) == int(common["L"][1]["A"]) + common_length + 1 == inverter_base + 1,
            "Fronius: inverter model does not directly follow the Common block")

    points = []
    for name, (point_id, block, vendor_type, vendor_unit) in SELECTED.items():
        number, row = blocks[block][name]
        require(row["H"] == vendor_type, f"Fronius {name}: type {row['H']!r}, expected {vendor_type}")
        require(row.get("I") == vendor_unit, f"Fronius {name}: unit {row.get('I')!r}, expected {vendor_unit}")
        require("0x03" in row["E"].split() and row["D"] in ("R", "RW"), f"Fronius {name}: not readable")
        start, end, size = int(row["A"]), int(row["B"]), int(row["C"])
        require(end - start + 1 == size, f"Fronius {name}: size disagrees with start and end")
        point = {"id": point_id, "aliases": [name], "description": row["G"], "address": start - facts["offset"]}
        if vendor_type in STRINGS:
            require(size == STRINGS[vendor_type], f"Fronius {name}: string size {size}")
            point.update(type="string", registers=size)
        else:
            require(size == 1, f"Fronius {name}: expected one register")
            point["type"] = TYPES[vendor_type]
            if vendor_unit in UNITS:
                point["unit"] = UNITS[vendor_unit]
            scale = row.get("J")
            if vendor_type == "sunssf":
                require(scale is None and name.endswith("_SF"), f"Fronius {name}: unexpected scale-factor row")
            elif vendor_type in ("uint16", "int16") and block == "inverter":
                require(scale in SELECTED and SELECTED[scale][2] == "sunssf", f"Fronius {name}: scale {scale!r}")
                point["conversion"] = {"exponent10": {"point": SELECTED[scale][0]}}
            else:
                require(scale in (None, "N/A"), f"Fronius {name}: unexpected scale {scale!r}")
            if name in STATE_TABLES:
                point["enum"] = state_enum(data, STATE_TABLES[name], facts["states"][name])
            elif name == "F_ModelType":
                point["enum"] = range_enum(row["K"])
                values = {value["name"]: value["value"] for value in point["enum"]["values"]}
                require(values == {"floating_point": facts["model_type"]["float"],
                                   "integer_sf": facts["model_type"]["int_sf"]},
                        "Fronius F_ModelType: values disagree with the manual")
            if block != "fronius":
                point["invalid"] = [not_supported(facts, vendor_type)]
        remark = row.get("K")
        if remark and block == "inverter":
            require(not remark.lower().startswith("not supported") or name in ("DCA", "DCV", "DCA_SF", "DCV_SF"),
                    f"Fronius {name}: marked not supported")
            point["description"] = f"{point['description'].rstrip('.')}. Vendor remark: {remark}"
        point["source"] = {"address": row["A"], "reference": f"{WORKBOOK.split('/')[-1]}!Complete Map row {number}"}
        points.append(point)
    return sorted(points, key=lambda point: point["address"])
