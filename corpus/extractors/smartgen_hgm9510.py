"""SmartGen HGM9510 Genset Controller Communication Protocol (PDF): alarm/status bits and the value data field.

Table 2 (bits, pages 6-25) and Table 6 (values, pages 26-42) give a decimal "Modbus Address" next to a "PLC
Address" (0000 = 40001). The worked example on page 42 sends the starting address 0103 as "00 67" (103), so the
Modbus addresses are zero-based PDU addresses of the holding registers that function 03H reads.

NOTE1 (page 42) defines the Ratio column: actual value = received data x ratio. NOTE2 and the example on pages
42-43 (0103 = E240H, 0104 = 0001H, combination 0001E240H = 123456) put the low-order word at the lower address.
Rows with a blank Ratio cell are not mapped: the document gives no scale for them.

The table cells wrap over several lines, so the rows are read from `pdftotext -raw` text, which keeps a wrapped
cell together; sourcelib has no helper for that mode (see the class-09 report).
"""
import re
import subprocess
from decimal import Decimal

from sourcelib import pdf_pages, require

PAGES = 48
HEADER = "HGM9510 Genset Controller Communication Protocol"
BIT_PAGES = (6, 25)
VALUE_PAGES = (26, 42)
EXAMPLE_PAGES = (42, 43)
STATUS_PAGES = (45, 46)

# Table 2 registers mapped as flag points: register -> (point ID, label).
BIT_REGISTERS = {0: ("common_status", "Common alarm and mode bits"), 1: ("shutdown_alarms_1", "Shutdown alarms 1")}
COMMON_ALARM_TEXT = ("0 means no common alarm occurs; 1 means there is common alarm. (000.0 is the boolean value "
                     "of bit 0 of address 000) The following contents in turn.")
# Table 6 name -> (point ID, vendor unit, UCUM unit, description).
VALUES = {
    "Mains Freq": ("mains_frequency", "Hz", "Hz", None),
    "Gen UAB": ("generator_voltage_ab", "V", "V", None),
    "Gen UA": ("generator_voltage_a", "V", "V", None),
    "Gen UB": ("generator_voltage_b", "V", "V", None),
    "Gen UC": ("generator_voltage_c", "V", "V", None),
    "A Phase Current": ("generator_current_a", "A", "A", None),
    "B Phase Current": ("generator_current_b", "A", "A", None),
    "C Phase Current": ("generator_current_c", "A", "A", None),
    "Accum. Running Hours": ("running_hours", "h", "h",
                             "The document gives the range 0~23 for this register; the minutes and seconds of the "
                             "accumulated running time follow in the next two registers."),
    "A Gen Power kWh": ("energy_counter_a", "kWh", "kW.h",
                        "The document lists A and B counter sets (running time, starts, energy) without "
                        "explaining them."),
}
# Table 6 name -> (point ID, status table title).
ENUMS = {
    "Gen Working Status": ("generator_status", "Generator Status Table"),
    "Mains Status": ("mains_status", "Mains Status Table"),
}
TYPES = {"16-bit Signed": ("i16", 1), "16-bit Unsigned": ("u16", 1), "32-bit Signed": ("i32", 2)}
HEADER_WORDS = {"Modbus", "Address", "PLC", "Item", "Description", "Bits", "Name", "Range", "(Decimal)", "Ratio",
                "Unit", "Remark"}
ROW = re.compile(r"^(\d{4}) (4\d{4})(?: (.*))?$")
BIT_ROW = re.compile(r"^(\d{4})\.(\d{1,2}) (4\d{4})\.(\d{1,2})(?: (.*))?$")
CELLS = re.compile(r"(?:(?P<range>-?[\d,.]+ ?~ ?-?[\d,.]+) )?(?:(?P<ratio>\d+(?:\.\d+)?) )?(?:(?P<unit>[^\s\d]\S*) )?"
                   r"(?P<type>(?:16|32)-bit (?:Signed|Unsigned))(?: (?P<remark>NOTE\d))?")


def slug(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    require(words, f"SmartGen HGM9510: cannot name {text!r}")
    return "_".join(words)


def raw_pages(data, first, last):
    """Text of PDF pages first..last in content-stream order (pdftotext -raw), keyed by page number."""
    command = ["pdftotext", "-f", str(first), "-l", str(last), "-raw", "-enc", "UTF-8", "-", "-"]
    result = subprocess.run(command, input=data, capture_output=True, check=True, timeout=60)
    pages = result.stdout.decode("utf-8").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    require(len(pages) == last - first + 1, f"SmartGen HGM9510 PDF pages {first}-{last}: got {len(pages)} pages")
    out = {}
    for number, page in enumerate(pages, first):
        lines = page.split("\n")
        require(lines[0] == f"{HEADER} Page {number} of {PAGES}", f"SmartGen HGM9510 page {number}: footer missing")
        out[number] = [line.strip() for line in lines[1:] if line.strip()]
    return out


def rows(raw, first, last, pattern, start_after=None, stop_at=None):
    """Group raw lines into table rows: a row is its start line plus the lines up to the next start line."""
    found = []
    for number in range(first, last + 1):
        lines = raw[number]
        if number == first and start_after:
            require(start_after in lines, f"SmartGen HGM9510 page {number}: {start_after!r} missing")
            lines = lines[lines.index(start_after) + 1:]
        if number == last and stop_at:
            ends = [index for index, line in enumerate(lines) if line.startswith(stop_at)]
            require(ends, f"SmartGen HGM9510 page {number}: {stop_at!r} missing")
            lines = lines[:ends[0]]
        starts = [index for index, line in enumerate(lines) if pattern.match(line)]
        require(starts, f"SmartGen HGM9510 page {number}: no table rows")
        head = lines[:starts[0]]
        while head and set(head[0].split()) <= HEADER_WORDS:
            head = head[1:]
        if head:
            # The last row of the previous page continues here.
            require(found and found[-1]["page"] == number - 1,
                    f"SmartGen HGM9510 page {number}: unexpected text before the first row: {head!r}")
            found[-1]["more"].extend(head)
        for position, index in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(lines)
            found.append({"page": number, "match": pattern.match(lines[index]), "more": lines[index + 1:end]})
    for row in found:
        row["text"] = " ".join([part for part in [row["match"].groups()[-1], *row["more"]] if part])
    return found



def find(table, label):
    found = [(index, CELLS.fullmatch(row["text"][len(label) + 1:])) for index, row in enumerate(table)
             if row["text"].startswith(f"{label} ") and CELLS.fullmatch(row["text"][len(label) + 1:])]
    require(len(found) == 1, f"SmartGen HGM9510: {len(found)} value rows for {label!r}")
    return found[0]


def conversion(ratio):
    value = Decimal(ratio)
    require(value > 0, f"SmartGen HGM9510: ratio {ratio!r}")
    exponent = value.adjusted()
    if value == Decimal(1).scaleb(exponent):
        return {"exponent10": exponent} if exponent else None
    return {"multiplier": float(value)}


def status_table(pages, title, count):
    """Parse 'N  Content  Description' rows below 'Table NN <title>' (the table may continue on the next page)."""
    lines = "\n".join(pages).split("\n")
    heads = [index for index, line in enumerate(lines) if re.fullmatch(rf"\s*Table \d+ {title}", line)]
    require(len(heads) == 1, f"SmartGen HGM9510: {title!r} not found once")
    entries = {}
    for line in lines[heads[0] + 1:]:
        if not line.strip() or re.fullmatch(r"\s*(?:No\.|Value \(No\.\))\s+(?:Content|Status)\s+Description", line):
            continue
        if line.strip().startswith(f"{HEADER} "):
            continue
        match = re.fullmatch(r"\s*(\d{1,2})\s{2,}(\S+(?: \S+)*)(?:\s{2,}(\S.*?))?\s*", line)
        if not match:
            break
        value = int(match.group(1))
        require(value not in entries, f"SmartGen HGM9510 {title}: value {value} listed twice")
        entries[value] = match.group(2)
    require(sorted(entries) == list(range(count)), f"SmartGen HGM9510 {title}: expected values 0-{count - 1}")
    return entries


def bit_points(raw):
    table = rows(raw, *BIT_PAGES, BIT_ROW, start_after="Table 2 Alarm, Status Coil Data Field",
                 stop_at="Table 3")
    points = []
    for register, (point_id, label) in BIT_REGISTERS.items():
        bits = [row for row in table if int(row["match"].group(1)) == register]
        require([int(row["match"].group(2)) for row in bits] == list(range(16)),
                f"SmartGen HGM9510 register {register:04d}: expected bits 0-15")
        flags = []
        for bit, row in enumerate(bits):
            _, _, plc, plc_bit, _ = row["match"].groups()
            require((int(plc), int(plc_bit)) == (40001 + register, bit),
                    f"SmartGen HGM9510 {register:04d}.{bit}: PLC address disagrees")
            mark = {0: " (LSB 0)", 15: " (MSB 15)"}.get(bit, "")
            text = row["text"]
            if register == 0 and bit == 0:
                require(text == f"Common Alarm {COMMON_ALARM_TEXT} 1bit (LSB 0)",
                        "SmartGen HGM9510 0000.0: description changed")
                text = "Common Alarm 1bit (LSB 0)"
            require(text.endswith(f" 1bit{mark}") or text == f"/ 1bit{mark}",
                    f"SmartGen HGM9510 {register:04d}.{bit}: unexpected row {text!r}")
            name = text[:-len(f" 1bit{mark}")]
            require(len(name) <= 40 and not re.search(r"[;~]|\d+bit", name),
                    f"SmartGen HGM9510 {register:04d}.{bit}: unexpected item {name!r}")
            if name in ("/", "Reserved"):
                continue
            flags.append({"bit": bit, "name": slug(name), "label": name})
        points.append({
            "id": point_id, "label": label, "address": register, "type": "u16", "flags": {"flags": flags},
            "description": "Bit numbers are the document's (bit 0 is marked LSB); reserved bits are left out.",
            "source": {"address": f"{register:04d}.0-{register:04d}.15", "page": bits[0]["page"],
                       "reference": "Table 2 Alarm, Status Coil Data Field"},
        })
    return points


def extract(data, selector):
    require(selector is None, "SmartGen HGM9510 takes no selector")
    pages = pdf_pages(data, 1, PAGES)
    require(all(re.search(rf"{HEADER}\s+Page {number} of {PAGES}\s*$", page)
                for number, page in enumerate(pages[1:], 2)), "SmartGen HGM9510: running footer missing")
    require(re.search(r"2021-10-21\s+1\.1\b", pages[1]), "SmartGen HGM9510: expected version 1.1 (2021-10-21)")
    intro = " ".join(pages[3].split())
    require("adopting Modbus-RTU protocol" in intro and "Supported function code: 03H, 05H, 06H." in intro,
            "SmartGen HGM9510 page 4: protocol statement missing")
    limit = re.search(r"Once maximum (\d+) data of word register can be read\.", intro)
    require(limit, "SmartGen HGM9510 page 4: read limit missing")
    example = " ".join(" ".join(pages[EXAMPLE_PAGES[0] - 1:EXAMPLE_PAGES[1]]).split())
    require("Actual value=received data*ratio." in example
            and "For 4-byte data, the actual value=received data MSB*65536 + received data LSB;" in example,
            "SmartGen HGM9510 page 42: NOTE1/NOTE2 missing")
    require("(0103)" in example and "01 03 00 67 00 02 75 D4" in example,
            "SmartGen HGM9510 page 42: request example with starting address 0103 missing")
    require(re.search(r"0103 E240H 0001E240H 123456 0104 0001H", example),
            "SmartGen HGM9510 page 43: data analysis example missing")

    raw = raw_pages(data, BIT_PAGES[0], VALUE_PAGES[1])
    points = bit_points(raw)

    table = rows(raw, *VALUE_PAGES, ROW, start_after="Table 6 Value Data Field", stop_at="NOTE1:")
    for row in table:
        modbus, plc, _ = row["match"].groups()
        require(int(plc) == int(modbus) + 40001, f"SmartGen HGM9510 {modbus}: PLC address {plc} disagrees")
    addresses = [int(row["match"].group(1)) for row in table]
    require(addresses[0] == 0 and {109, 110} <= set(addresses), "SmartGen HGM9510: value table addresses changed")

    for label, (point_id, vendor_unit, unit, text) in VALUES.items():
        index, cells = find(table, label)
        row = table[index]
        address = row["match"].group(1)
        require(cells["ratio"] is not None and cells["unit"] == vendor_unit and cells["remark"] is None,
                f"SmartGen HGM9510 {label}: unexpected ratio, unit or remark {cells.groupdict()}")
        data_type, registers = TYPES[cells["type"]]
        point = {"id": point_id, "aliases": [label], "address": int(address), "type": data_type}
        source_address = address
        if registers == 2:
            low = table[index + 1]
            require(int(low["match"].group(1)) == int(address) + 1 and not low["text"],
                    f"SmartGen HGM9510 {label}: expected an empty second row")
            point["wordOrder"] = "little"
            source_address = f"{address}-{low['match'].group(1)}"
        scale = conversion(cells["ratio"])
        if scale:
            point["conversion"] = scale
        point["unit"] = unit
        if text:
            point["description"] = text
        point["source"] = {"address": source_address, "page": row["page"],
                           "reference": f"Table 6 Value Data Field, {label}"}
        points.append(point)

    for label, (point_id, title) in ENUMS.items():
        found = [row for row in table if row["text"] == f"{label} No. {title}"]
        require(len(found) == 1, f"SmartGen HGM9510: {len(found)} rows for {label!r}")
        row = found[0]
        entries = status_table(pages[STATUS_PAGES[0] - 1:STATUS_PAGES[1]], title,
                               16 if title.startswith("Generator") else 4)
        points.append({
            "id": point_id, "aliases": [label], "address": int(row["match"].group(1)), "type": "u16",
            "enum": {"values": [{"value": value, "name": slug(name), "label": name}
                                for value, name in sorted(entries.items())]},
            "source": {"address": row["match"].group(1), "page": row["page"],
                       "reference": f"Table 6 Value Data Field, {label}; {title}"},
        })
    points.sort(key=lambda point: point["address"])
    return {"points": points, "constraints": {"maxReadRegisters": int(limit.group(1))}}
