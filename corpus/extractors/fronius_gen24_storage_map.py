"""Fronius GEN24 SunSpec register maps (ZIP of XLSX): int+SF map with storage, ROW.

The workbook lists 1-based SunSpec register numbers ("Start"). The address base,
the values returned for unavailable data and the sunssf data type are stated in
the pinned companion manual "Fronius GEN24 - Modbus TCP and RTU Operating
instructions" (evidence fronius-gen24-modbus-manual), which links this ZIP as
the GEN24 Plus register maps. The extractor reads those facts from the manual:
section "Register addresses" ("To read register 40001, use address 40000"),
section "Unavailable data records" and the scale factor section. The manual's
int+SF start addresses of the MPPT and storage models are checked against the
workbook.

Only single-register values and strings are selected: neither the workbook nor
the manual states the register order of 32-bit and 64-bit values.

The selector is a model name that must appear in the example list of the
common model register Md.
"""
import re
from html.parser import HTMLParser

from sourcelib import require, xlsx_rows, zip_member

MEMBER = "Gen24_Primo_Symo_Inverter_Register_Map_Int&SF_storage_ROW.xlsx"
SHEET = "Complete Map"
TITLE = ("Fronius Gen24 Primo/Symo Inverter Register Map with Integer+SF Inverter Model and storage configured "
         "for ROW use")
HEADER = {"A": "Start", "B": "End", "C": "Size", "D": "R/W", "E": "Function codes", "F": "Name",
          "G": "Description", "H": "Type", "I": "Units", "J": "Scale Factor", "K": "Range of values"}
TYPES = {"uint16": "u16", "int16": "i16", "sunssf": "i16", "enum16": "u16", "string": "string"}
SIGNED = {"int16", "sunssf"}
UNITS = {"W": "W", "V": "V", "A": "A", "C": "Cel", "% AhrRtg": "%"}
# Vendor spelling in the enum list; the manual spells the state DISCHARGING.
ENUM_NAMES = {"DISCHAGING": "discharging"}

# (model sheet, register name): (point id, vendor type, vendor unit)
SELECTED = {
    ("common (1)", "Md"): ("model", "string", None),
    ("inverter (10x)", "W"): ("ac_power", "int16", "W"),
    ("inverter (10x)", "TmpCab"): ("cabinet_temperature", "int16", "C"),
    ("mppt (160)", "module/3/DCA"): ("battery_charge_current", "uint16", "A"),
    ("mppt (160)", "module/3/DCV"): ("battery_voltage", "uint16", "V"),
    ("mppt (160)", "module/3/DCW"): ("battery_charge_power", "uint16", "W"),
    ("mppt (160)", "module/4/DCA"): ("battery_discharge_current", "uint16", "A"),
    ("mppt (160)", "module/4/DCW"): ("battery_discharge_power", "uint16", "W"),
    ("storage (124)", "WChaMax"): ("charge_discharge_power_reference", "uint16", "W"),
    ("storage (124)", "ChaState"): ("battery_state_of_charge", "uint16", "% AhrRtg"),
    ("storage (124)", "ChaSt"): ("battery_charge_status", "enum16", None),
}
# The MPPT modules that carry the battery port, identified by their IDStr value.
STORAGE_MODULES = {("mppt (160)", "module/3/IDStr"): "'StCha 3'", ("mppt (160)", "module/4/IDStr"): "'StDisCha 4'"}
MODEL_ID = re.compile(r"Well-known value\. Uniquely identifies this as a sunspec model (.+)")

MANUAL = "fronius-gen24-modbus-manual"
MANUAL_TITLE = "Fronius GEN24 - Modbus TCP and RTU Operating instructions"
ZIP_NAME = "/gen24-modbus-api-external-docs.zip"
ZIP_LINK = "GEN24 Plus Modbus SunSpec Maps, State Codes and Events"
ADDRESS_RULE = re.compile(r"To read register (\d+), use address (\d+) \(0x([0-9A-F]+)\)\.")
ADDRESS_NOTE = "The register address that is output therefore always has 1 number less than the actual register number."
SUNSSF_NOTE = 'The data type "sunssf" is a signed integer with 16 bits.'
UNIT_ID_NOTES = ("TCP: The unit-id of the inverter is always 0x01.",
                 "RTU: The slave-id must be configured on the web interface of the GEN24.")
# Data types in the order of the manual's table "Unavailable data records".
SENTINEL_TYPES = ("int16", "uint16", "acc16", "enum16", "bitfield16", "pad", "int32", "uint32", "acc32", "enum32",
                  "bitfield32", "int64", "uint64", "acc64", "stringX", "float32", "sunssf")
# Manual article that states the int+SF start address of a workbook model sheet.
START_ARTICLES = {"mppt (160)": "Multiple MPPT Inverter Extension Register",
                  "storage (124)": "Basic Storage Controls Register"}
BREAKS = {"article", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ol", "p", "table", "td", "th", "title",
          "tr", "ul"}


class _ManualText(HTMLParser):
    """Collect text lines per <article title=...>, the page title and link texts; skip footnote markers."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.articles = []
        self.links = []
        self.title = []
        self.lines = None
        self.parts = []
        self.skip = 0
        self.in_title = False
        self.link = None

    def flush(self):
        text = " ".join("".join(self.parts).split())
        if text and self.lines is not None:
            self.lines.append(text)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "sup"):
            self.skip += 1
            return
        if tag in BREAKS:
            self.flush()
        if tag == "article":
            self.lines = []
            self.articles.append((dict(attrs).get("title"), self.lines))
        elif tag == "title":
            self.in_title = True
        elif tag == "a":
            self.link = (dict(attrs).get("href") or "", [])

    def handle_endtag(self, tag):
        if tag in ("script", "style", "sup"):
            self.skip -= 1
            return
        if tag in BREAKS:
            self.flush()
        if tag == "article":
            self.lines = None
        elif tag == "title":
            self.in_title = False
        elif tag == "a" and self.link:
            self.links.append((self.link[0], " ".join("".join(self.link[1]).split())))
            self.link = None

    def handle_data(self, data):
        if self.skip:
            return
        self.parts.append(data)
        if self.in_title:
            self.title.append(data)
        if self.link:
            self.link[1].append(data)


def article(parsed, title):
    found = [lines for name, lines in parsed.articles if name == title]
    require(len(found) == 1, f"Fronius manual: expected one section {title!r}, found {len(found)}")
    return found[0]


def manual_facts(evidence):
    """Read the address base, unavailable-data values and model start addresses from the pinned manual."""
    require(evidence and MANUAL in evidence, f"Fronius: evidence {MANUAL} is required")
    parsed = _ManualText()
    parsed.feed(evidence[MANUAL].decode("utf-8"))
    parsed.close()
    require("".join(parsed.title).strip() == MANUAL_TITLE, "Fronius manual: title changed")
    require(any(href.endswith(ZIP_NAME) and text == ZIP_LINK for href, text in parsed.links),
            "Fronius manual: no longer links the GEN24 Plus register maps")
    text = "\n".join(line for _, lines in parsed.articles for line in lines)
    require(SUNSSF_NOTE in text, "Fronius manual: sunssf is no longer a signed 16-bit integer")
    require(all(note in text for note in UNIT_ID_NOTES), "Fronius manual: unit ID statement changed")

    addressing = article(parsed, "Register addresses")
    rules = [ADDRESS_RULE.fullmatch(line) for line in addressing]
    rules = [rule for rule in rules if rule]
    require(len(rules) == 1 and ADDRESS_NOTE in addressing, "Fronius manual: register address statement changed")
    register, address, hexadecimal = int(rules[0].group(1)), int(rules[0].group(2)), int(rules[0].group(3), 16)
    require(address == hexadecimal and register - address == 1, "Fronius manual: address is not register - 1")

    records = article(parsed, "Unavailable data records")
    labels = re.findall(r"\b(" + "|".join(SENTINEL_TYPES) + r")(?: \([^)]*\))?:", " ".join(records))
    require(tuple(labels) == SENTINEL_TYPES, f"Fronius manual: unavailable data types changed: {labels}")
    last = [index for index, line in enumerate(records) if line.startswith("sunssf (")]
    require(len(last) == 1, "Fronius manual: unavailable data table changed")
    values = records[last[0] + 1:last[0] + 1 + len(SENTINEL_TYPES)]
    require(records[last[0] + 1 + len(SENTINEL_TYPES)].startswith('The prefix "0x"'),
            "Fronius manual: unavailable data values changed")
    invalid = {}
    for vendor_type, value in zip(SENTINEL_TYPES, values):
        if vendor_type in TYPES:
            require(re.fullmatch(r"0x[0-9A-F]{4}", value), f"Fronius manual: {vendor_type} unavailable value {value!r}")
            raw = int(value, 16)
            invalid[vendor_type] = [raw - 0x10000 if vendor_type in SIGNED and raw >= 0x8000 else raw]

    starts = {}
    for model, title in START_ARTICLES.items():
        found = [re.fullmatch(r'for "int\+SF" setting: (\d+)', line) for line in article(parsed, title)]
        found = [match for match in found if match]
        require(len(found) == 1, f"Fronius manual: no int+SF start address in {title!r}")
        starts[model] = int(found[0].group(1))
    return {"offset": register - address, "invalid": invalid, "starts": starts}


def snake(name):
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name))
    return re.sub(r"_+", "_", words.lower())


def first_sentence(text):
    return re.split(r"(?<=\.)\s", text.strip(), maxsplit=1)[0]


def describe(row, vendor_type):
    text = first_sentence(row.get("G", ""))
    vendor_note = re.search(r"Additional Fronius description: (.+)", row.get("G", ""))
    if vendor_note:
        text = f"{text} {first_sentence(vendor_note.group(1))}"
    remark = row.get("K", "")
    if vendor_type not in ("enum16", "string") and re.search(r"[a-z]", remark):
        text = f"{text.rstrip('.')}. {remark}" if text else remark
    return text


KEY_ORDER = ("id", "address", "type", "registers", "unit", "conversion", "enum", "invalid", "description",
             "aliases", "source")


def ordered(point):
    require(set(point) <= set(KEY_ORDER), f"Fronius: unexpected point keys {sorted(point)}")
    return {key: point[key] for key in KEY_ORDER if key in point}


def complete_map(workbook):
    rows = list(xlsx_rows(workbook, SHEET))
    require(rows and rows[0][1].get("A") == TITLE, "Fronius: Complete Map title changed")
    entries = {}
    model = None
    for number, row in rows[1:]:
        if row.get("A") == "Start":
            require(row == HEADER, f"Fronius: header changed at row {number}")
            continue
        require(re.fullmatch(r"\d{5}", row.get("A", "")) and re.fullmatch(r"\d{5}", row.get("B", "")),
                f"Fronius: unexpected row {number}")
        start, end, size = int(row["A"]), int(row["B"]), int(row["C"])
        require(end - start + 1 == size, f"Fronius: Start/End/Size disagree at row {number}")
        if row.get("F") == "SID":
            require(start == 40001 and row.get("H") == "uint32" and row.get("K") == "0x53756e53 ('SunS')",
                    "Fronius: SunSpec identifier is not at register 40001")
            continue
        if row.get("F") == "ID":
            match = MODEL_ID.fullmatch(row.get("G", ""))
            if match:
                model = match.group(1)
            else:
                require(row.get("G") == "Identifies this as End block", f"Fronius: unknown model at row {number}")
                model = "End Block"
            require(model not in {key[0] for key in entries}, f"Fronius: model {model} listed twice")
        require(model is not None, f"Fronius: register before the first model at row {number}")
        key = (model, row["F"])
        require(key not in entries, f"Fronius: duplicate register {key}")
        entries[key] = (number, row)
    return entries


def model_offsets(workbook, model):
    offsets = {}
    for _, row in xlsx_rows(workbook, model):
        if row.get("A") == "Start":
            require(row == HEADER, f"Fronius: {model} sheet header changed")
            continue
        offsets[row["F"]] = row
    return offsets


def extract(data, selector, evidence=None):
    manual = manual_facts(evidence)
    workbook = zip_member(data, MEMBER)
    entries = complete_map(workbook)
    # The manual's start address of a model is the address of its ID register.
    for model, start in manual["starts"].items():
        require(int(entries[(model, "ID")][1]["A"]) - manual["offset"] == start,
                f"Fronius: manual start address {start} of {model} does not match the workbook")
    _, md = entries[("common (1)", "Md")]
    require(selector and re.search(re.escape(selector) + r"(?![\d.])", md.get("K", "")),
            f"Fronius: model {selector!r} is not named in register Md")
    for key, label in STORAGE_MODULES.items():
        require(key in entries and entries[key][1].get("K") == label, f"Fronius: {key} is not {label}")

    sheets = {}
    points = {}

    def add(model, name, point_id, vendor_type, vendor_unit):
        require((model, name) in entries, f"Fronius: register {model} {name} missing")
        number, row = entries[(model, name)]
        require(row.get("H") == vendor_type and row.get("I") == vendor_unit and row.get("D") == "R"
                and row.get("E") == "0x03", f"Fronius {name}: unexpected type, unit or access")
        require("not supported" not in row.get("K", "").lower(), f"Fronius {name}: marked not supported")
        # The model sheet gives 1-based offsets; the model's ID register is offset 1.
        sheet = sheets.setdefault(model, model_offsets(workbook, model))
        base = int(entries[(model, "ID")][1]["A"])
        require(name in sheet and int(sheet[name]["A"]) == int(row["A"]) - base + 1
                and sheet[name].get("H") == vendor_type,
                f"Fronius {name}: Complete Map and {model} sheet disagree")
        register = int(row["A"])
        point = {"id": point_id, "address": register - manual["offset"], "type": TYPES[vendor_type]}
        if vendor_type == "string":
            point["registers"] = int(row["C"])
        else:
            require(row["C"] == "1", f"Fronius {name}: expected one register")
        if vendor_unit:
            point["unit"] = UNITS[vendor_unit]
        if vendor_type in manual["invalid"]:
            point["invalid"] = list(manual["invalid"][vendor_type])
        description = describe(row, vendor_type)
        if description:
            point["description"] = description
        point["aliases"] = [name]
        point["source"] = {"address": row["A"], "reference": f"{SHEET}!A{number} ({model})"}
        require(point_id not in {p["id"] for p in points.values()}, f"Fronius: duplicate point ID {point_id}")
        points[(model, name)] = point
        return row, point

    for (model, name), (point_id, vendor_type, vendor_unit) in SELECTED.items():
        row, point = add(model, name, point_id, vendor_type, vendor_unit)
        factor = row.get("J")
        if factor:
            require(re.fullmatch(r"\w+_SF", factor), f"Fronius {name}: scale factor {factor!r}")
            if (model, factor) not in points:
                add(model, factor, snake(factor), "sunssf", None)
            point["conversion"] = {"exponent10": {"point": points[(model, factor)]["id"]}}
        if vendor_type == "enum16":
            values = [(int(value), label) for value, label in re.findall(r"(\d+): ([A-Z]+)\b", row.get("K", ""))]
            require([value for value, _ in values] == list(range(1, len(values) + 1)) and len(values) >= 2,
                    f"Fronius {name}: unparsed enumeration")
            point["enum"] = {"values": [{"value": value, "name": ENUM_NAMES.get(label, label.lower())}
                                        for value, label in values]}
    return sorted((ordered(point) for point in points.values()), key=lambda point: point["address"])
