"""Fronius GEN24 SunSpec register maps (ZIP of XLSX): the int+SF maps of the bundle.

The bundle holds one workbook per series (GEN24 Primo/Symo, Tauro, Tauro ECO, Verto,
Smart Meter), SunSpec model type (float or int+SF) and configuration (storage, MPPT
count). Each workbook lists 1-based SunSpec register numbers ("Start"). The address
base, the values returned for unavailable data and the sunssf data type are stated in
the pinned companion manual "Fronius GEN24 - Modbus TCP and RTU Operating instructions"
(evidence fronius-gen24-modbus-manual), which links this ZIP as its register maps. The
extractor reads those facts from the manual: section "Register addresses" ("To read
register 40001, use address 40000"), section "Unavailable data records" and the scale
factor section. The manual's int+SF start addresses of the SunSpec models are checked
against the workbooks.

Only single-register values and strings are selected: neither the workbooks nor the
manual state the register order of 32-bit and 64-bit values. Every measurement of the
float inverter and meter models is such a value, so the float maps are not used.

Selectors:
- a model name that appears in the example list of the common model register Md
  ("Symo GEN24 6.0"): the battery points of the int+SF map with storage, ROW;
- "<layout>/<series>" ("tauro-intsf/Tauro"): the inverter or meter points of one int+SF
  workbook (LAYOUTS). The series must start an entry of that workbook's Md example list.
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
TYPES = {"uint16": "u16", "int16": "i16", "sunssf": "i16", "enum16": "u16", "bitfield16": "u16", "string": "string"}
SIGNED = {"int16", "sunssf"}
UNITS = {"W": "W", "V": "V", "A": "A", "C": "Cel", "% AhrRtg": "%", "Hz": "Hz", "VA": "V.A"}
# UCUM has no code for var: such a point carries no unit and its description names the vendor unit.
NO_UCUM = {"var"}
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

# "<layout>/<series>" selectors, one int+SF workbook each. `device` is the sheet of the inverter or
# meter model, `modules` the IDStr values of the MPPT model's blocks, `end` the device type whose
# End Block start address the manual states for this configuration, and `manual_storage` says that
# the manual's start address of the storage model is for this configuration.
LAYOUTS = {
    "gen24-intsf": {
        "member": "Gen24_Primo_Symo_Inverter_Register_Map_Int&SF_ROW.xlsx",
        "title": "Fronius Gen24 Primo/Symo Inverter Register Map with Integer+SF Inverter Model for ROW use",
        "device": "inverter (10x)", "modules": ("MPPT 1", "MPPT 2"), "end": "Inverter"},
    "gen24-intsf-storage": {
        "member": MEMBER, "title": TITLE, "device": "inverter (10x)",
        "modules": ("MPPT 1", "MPPT 2", "StCha 3", "StDisCha 4"), "storage": True, "manual_storage": True},
    "tauro-intsf": {
        "member": "Tauro_Inverter_Register_Map_Int&SF_ROW.xlsx",
        "title": "Fronius Tauro Inverter Register Map with Integer+SF Inverter Model for ROW use",
        "device": "inverter (103)", "modules": ("MPPT 1", "MPPT 2", "MPPT 3")},
    "tauro-eco-intsf": {
        "member": "Tauro_ECO_Inverter_Register_Map_Int&SF_ROW.xlsx",
        "title": "Fronius Tauro ECO Inverter Register Map with Integer+SF Inverter Model for ROW use",
        "device": "inverter (103)", "modules": ("MPPT 1",)},
    "verto-3mppt-intsf": {
        "member": "Verto_Inverter_Register_Map_3MPPT_Int&SF_ROW.xlsx",
        "title": "Fronius Verto Inverter Register Map with 3 MPPT and Integer+SF Inverter Model for ROW use",
        "device": "inverter (103)", "modules": ("MPPT 1", "MPPT 2", "MPPT 3")},
    "verto-4mppt-intsf": {
        "member": "Verto_Inverter_Register_Map_4MPPT_Int&SF_ROW.xlsx",
        "title": "Fronius Verto Inverter Register Map with 4 MPPT and Integer+SF Inverter Model for ROW use",
        "device": "inverter (103)", "modules": ("MPPT 1", "MPPT 2", "MPPT 3", "MPPT 4")},
    "verto-3mppt-intsf-storage": {
        "member": "Verto_Inverter_Register_Map_3MPPT_Int&SF_storage_ROW.xlsx",
        "title": ("Fronius Verto Inverter Register Map with 3 MPPT, Integer+SF Inverter Model and storage "
                  "configured for ROW use"),
        "device": "inverter (103)", "modules": ("MPPT 1", "MPPT 2", "MPPT 3", "StCha 4", "StDisCha 5"),
        "storage": True},
    "smart-meter-intsf": {
        "member": "Smart_Meter_Register_Map_Int&SF.xlsx",
        "title": "Smart Meter Register Map with Integer+SF AC-Meter Model",
        "device": "ac_meter (20x)", "end": "Energy meter"},
}
DEVICE = "<device>"
# (model sheet, register name, point id, vendor type, vendor unit); DEVICE is the layout's device sheet.
INVERTER_POINTS = (
    ("common (1)", "Md", "model", "string", None),
    (DEVICE, "A", "ac_current", "uint16", "A"),
    (DEVICE, "PhVphA", "voltage_l1_n", "uint16", "V"),
    (DEVICE, "W", "ac_power", "int16", "W"),
    (DEVICE, "Hz", "frequency", "uint16", "Hz"),
    (DEVICE, "DCW", "dc_power", "int16", "W"),
    (DEVICE, "St", "operating_state", "enum16", None),
    ("status (122)", "PVConn", "pv_connection_status", "bitfield16", None),
    ("mppt (160)", "module/1/DCA", "mppt1_current", "uint16", "A"),
    ("mppt (160)", "module/1/DCV", "mppt1_voltage", "uint16", "V"),
)
STORAGE_POINTS = (
    ("storage (124)", "ChaState", "battery_state_of_charge", "uint16", "% AhrRtg"),
    ("storage (124)", "ChaSt", "battery_charge_status", "enum16", None),
)
METER_POINTS = (
    ("common (1)", "Md", "model", "string", None),
    (DEVICE, "ID", "meter_model", "uint16", None),
    (DEVICE, "A", "current_total", "int16", "A"),
    (DEVICE, "PhVphA", "voltage_l1_n", "int16", "V"),
    (DEVICE, "Hz", "frequency", "int16", "Hz"),
    (DEVICE, "W", "active_power_total", "int16", "W"),
    (DEVICE, "VA", "apparent_power_total", "int16", "VA"),
    (DEVICE, "VAR", "reactive_power_total", "int16", "var"),
)
# Scale-factor registers of these model sheets get a prefixed point ID (the inverter model has its own DCW_SF).
SF_PREFIX = {"mppt (160)": "mppt_"}
ST_NOTE = "see all states in our Modbus TCP & RTU user manual under SunSpec Operating Codes"
METER_MODEL = re.compile(r"(\d+): ([A-Za-z-]+(?: [A-Za-z]+)*) \(([A-Z]+(?: or [A-Z]+)?)\)")

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
MODEL_ARTICLES = {"nameplate (120)": "Nameplate Register", "settings (121)": "Basic Settings Register",
                  "status (122)": "Extended Measurements & Status Register", **START_ARTICLES}
# Statements of the model type per device kind: the float model is the default, int+SF the other setting.
MODEL_TYPES = {
    "inverter": ("Inverter Model Register",
                 r'the default set inverter model with floating point display \(setting "float"; (\d+), (\d+) or '
                 r'(\d+)\) the inverter model with integers and scale factors \(setting "int\+SF"; (\d+), (\d+) or '
                 r"(\d+)\) The register number of the two model types is different!"),
    "meter": ("Meter Model Register",
              r'the meter model with floating point display \(setting "float"; (\d+), (\d+) or (\d+)\) the meter '
              r'model with integers and scale factors \(setting "int\+SF"; (\d+), (\d+) or (\d+)\) The register '
              r"number of the two model types is different! The Modbus device ID of the energy meter is "
              r"configurable \(default = (\d+)\)\."),
}
# Default Modbus device ID of the energy meter; the manifest states it as the unit ID default.
METER_DEVICE_ID = 200
CHAIN_NOTES = ("Register addresses do not remain constant.",
               "The actual register addresses depend on the composition of the dynamic SunSpec register list.")
OPERATING_CODE = re.compile(r"I_STATUS_([A-Z]+(?:_[A-Z]+)*)")
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


def start_address(parsed, title):
    found = [re.fullmatch(r'for "int\+SF" setting: (\d+)', line) for line in article(parsed, title)]
    found = [match for match in found if match]
    require(len(found) == 1, f"Fronius manual: no int+SF start address in {title!r}")
    return int(found[0].group(1))


def end_blocks(parsed):
    """int+SF start address of the End Block per device type that has a float and an int+SF setting."""
    lines = [line for name, lines in parsed.articles if name == "End Block" for line in lines]
    starts = {}
    for index, line in enumerate(lines):
        if not line.endswith(":") or index + 2 >= len(lines):
            continue
        settings = (re.fullmatch(r'- Start address for setting "float": (\d+)', lines[index + 1]),
                    re.fullmatch(r'- Start address for setting "int\+SF": (\d+)', lines[index + 2]))
        if all(settings):
            require(line[:-1] not in starts, f"Fronius manual: End Block of {line[:-1]} stated twice")
            starts[line[:-1]] = int(settings[1].group(1))
    return starts


def model_types(parsed):
    """SunSpec model IDs of the int+SF setting per device kind; the manual names float as the default."""
    models = {}
    for kind, (title, pattern) in MODEL_TYPES.items():
        match = re.search(pattern, " ".join(article(parsed, title)))
        require(match, f"Fronius manual: model type statement changed in {title!r}")
        numbers = [int(value) for value in match.groups()]
        models[kind] = {"float": set(numbers[:3]), "int+SF": set(numbers[3:6]), "rest": numbers[6:]}
    return models


def operating_codes(parsed):
    """Enumeration of the inverter model register St from the manual's table "SunSpec Operating Codes"."""
    lines = article(parsed, "SunSpec Operating Codes")
    heads = [index for index in range(len(lines) - 2) if lines[index:index + 3] == ["Name", "Value", "Description"]]
    require(len(heads) == 1, "Fronius manual: SunSpec Operating Codes table changed")
    values = []
    index = heads[0] + 3
    while index + 2 < len(lines) and OPERATING_CODE.fullmatch(lines[index]):
        require(re.fullmatch(r"\d+", lines[index + 1]), f"Fronius manual: operating code value {lines[index + 1]!r}")
        values.append({"value": int(lines[index + 1]), "name": OPERATING_CODE.fullmatch(lines[index]).group(1).lower(),
                       "label": lines[index], "description": lines[index + 2]})
        index += 3
    require(len(values) >= 2 and [item["value"] for item in values] == list(range(1, len(values) + 1))
            and lines[index:] == ["*", "Inverter model register"], "Fronius manual: unparsed SunSpec Operating Codes")
    return values


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
    require(all(note in addressing for note in CHAIN_NOTES), "Fronius manual: dynamic register list statement changed")

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

    model_starts = {model: start_address(parsed, title) for model, title in MODEL_ARTICLES.items()}
    starts = {model: model_starts[model] for model in START_ARTICLES}
    return {"offset": register - address, "invalid": invalid, "starts": starts, "model_starts": model_starts,
            "end_blocks": end_blocks(parsed), "model_types": model_types(parsed),
            "operating_codes": operating_codes(parsed)}


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
    if vendor_type not in ("enum16", "bitfield16", "string") and re.search(r"[a-z]", remark):
        text = f"{text.rstrip('.')}. {remark}" if text else remark
    return text


KEY_ORDER = ("id", "address", "type", "registers", "unit", "conversion", "enum", "flags", "invalid", "description",
             "aliases", "source")


def ordered(point):
    require(set(point) <= set(KEY_ORDER), f"Fronius: unexpected point keys {sorted(point)}")
    return {key: point[key] for key in KEY_ORDER if key in point}


def complete_map(workbook, title=TITLE):
    rows = list(xlsx_rows(workbook, SHEET))
    require(rows and rows[0][1].get("A") == title, "Fronius: Complete Map title changed")
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


def point_builder(workbook, entries, manual, origin):
    """Return (points, add); add() builds one point from a Complete Map row and checks it against its model sheet."""
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
        if vendor_unit and vendor_unit not in NO_UCUM:
            point["unit"] = UNITS[vendor_unit]
        if vendor_type in manual["invalid"]:
            point["invalid"] = list(manual["invalid"][vendor_type])
        description = describe(row, vendor_type)
        if vendor_unit in NO_UCUM:
            description = (f"{description.rstrip('.')}. " if description else "") + f"Vendor unit: {vendor_unit}."
        if description:
            point["description"] = description
        point["aliases"] = [name]
        point["source"] = {"address": row["A"], "reference": f"{origin}{SHEET}!A{number} ({model})"}
        require(point_id not in {p["id"] for p in points.values()}, f"Fronius: duplicate point ID {point_id}")
        points[(model, name)] = point
        return row, point

    return points, add


def scale_factor(points, add, model, name, row, point, prefix=""):
    factor = row.get("J")
    if factor:
        require(re.fullmatch(r"\w+_SF", factor), f"Fronius {name}: scale factor {factor!r}")
        if (model, factor) not in points:
            add(model, factor, prefix + snake(factor), "sunssf", None)
        point["conversion"] = {"exponent10": {"point": points[(model, factor)]["id"]}}


def enumeration(name, row):
    values = [(int(value), label) for value, label in re.findall(r"(\d+): ([A-Z]+)\b", row.get("K", ""))]
    require([value for value, _ in values] == list(range(1, len(values) + 1)) and len(values) >= 2,
            f"Fronius {name}: unparsed enumeration")
    return {"values": [{"value": value, "name": ENUM_NAMES.get(label, label.lower())} for value, label in values]}


def storage_points(data, selector, manual):
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

    points, add = point_builder(workbook, entries, manual, "")
    for (model, name), (point_id, vendor_type, vendor_unit) in SELECTED.items():
        row, point = add(model, name, point_id, vendor_type, vendor_unit)
        scale_factor(points, add, model, name, row, point)
        if vendor_type == "enum16":
            point["enum"] = enumeration(name, row)
    return points


def layout_points(data, selector, manual):
    key, _, series = selector.partition("/")
    require(key in LAYOUTS and series, f"Fronius: unknown layout selector {selector!r}")
    layout = LAYOUTS[key]
    device = layout["device"]
    meter = device.startswith("ac_meter")
    workbook = zip_member(data, layout["member"])
    entries = complete_map(workbook, layout["title"])

    def address(model):
        require((model, "ID") in entries, f"Fronius: model {model} missing in {layout['member']}")
        return int(entries[(model, "ID")][1]["A"]) - manual["offset"]

    # The series starts an entry of the Md example list ("Tauro" does not match "Tauro ECO 50-3-P").
    _, md = entries[("common (1)", "Md")]
    require(re.search(r"(?<![\w.])" + re.escape(series) + r" \d", md.get("K", "")),
            f"Fronius: series {series!r} is not named in register Md of {layout['member']}")
    # The device model of this workbook is one of the manual's int+SF models; float is the manual's default.
    kind = manual["model_types"]["meter" if meter else "inverter"]
    stated = kind["int+SF"]
    require(not meter or kind["rest"] == [METER_DEVICE_ID], "Fronius manual: default device ID of the meter changed")
    listed = {int(value) for value in re.findall(r"(?<!\d)(\d{3})(?!\d)", entries[(device, "ID")][1].get("K", ""))}
    require(listed and (stated <= listed if meter else listed <= stated),
            f"Fronius: {device} IDs {sorted(listed)} are not the manual's int+SF models {sorted(stated)}")
    # The manual's int+SF start address of a model is the address of its ID register.
    checked = [] if meter else ["nameplate (120)", "settings (121)", "status (122)", "mppt (160)"]
    if layout.get("manual_storage"):
        checked.append("storage (124)")
    for model in checked:
        require(address(model) == manual["model_starts"][model],
                f"Fronius: manual start address of {model} does not match {layout['member']}")
    if "end" in layout:
        require(address("End Block") == manual["end_blocks"].get(layout["end"]),
                f"Fronius: manual End Block address of {layout['end']} does not match {layout['member']}")
    if not meter:
        modules = []
        while ("mppt (160)", f"module/{len(modules) + 1}/IDStr") in entries:
            modules.append(entries[("mppt (160)", f"module/{len(modules) + 1}/IDStr")][1].get("K"))
        require(tuple(modules) == tuple(f"'{label}'" for label in layout["modules"])
                and entries[("mppt (160)", "L")][1].get("K") == str(8 + 20 * len(modules)),
                f"Fronius: MPPT model blocks of {layout['member']} changed: {modules}")

    selection = METER_POINTS if meter else INVERTER_POINTS + (STORAGE_POINTS if layout.get("storage") else ())
    points, add = point_builder(workbook, entries, manual, layout["member"] + " ")
    for sheet, name, point_id, vendor_type, vendor_unit in selection:
        model = device if sheet == DEVICE else sheet
        row, point = add(model, name, point_id, vendor_type, vendor_unit)
        scale_factor(points, add, model, name, row, point, SF_PREFIX.get(model, ""))
        if name == "St":
            require(row.get("K") == ST_NOTE, "Fronius St: no longer refers to the manual's SunSpec Operating Codes")
            point["enum"] = {"values": [dict(item) for item in manual["operating_codes"]]}
            point["description"] = row["G"]
        elif vendor_type == "enum16":
            point["enum"] = enumeration(name, row)
        elif vendor_type == "bitfield16":
            bits = re.findall(r"Bit (\d+): ([A-Za-z]+)", row.get("K", ""))
            require(bits and " ".join(f"Bit {bit}: {label}" for bit, label in bits) == row.get("K"),
                    f"Fronius {name}: unparsed bit list")
            point["flags"] = {"flags": [{"bit": int(bit), "name": label.lower()} for bit, label in bits]}
        elif name == "ID":
            # The meter model ID tells the connection type; an End Block here (0xFFFF) reads as not available.
            models = METER_MODEL.findall(row.get("K", ""))
            require(models and ", ".join(f"{value}: {label} ({phases})" for value, label, phases in models)
                    == row.get("K"), f"Fronius {name}: unparsed model list")
            point["enum"] = {"values": [{"value": int(value), "name": snake(label.replace("-", " ").replace(" ", "_")),
                                         "label": f"{label} ({phases})"} for value, label, phases in models]}
            point["description"] = row["G"]
    return points


def extract(data, selector, evidence=None):
    manual = manual_facts(evidence)
    require(isinstance(selector, str) and selector, "Fronius: a selector is required")
    points = layout_points(data, selector, manual) if "/" in selector else storage_points(data, selector, manual)
    return sorted((ordered(point) for point in points.values()), key=lambda point: point["address"])
