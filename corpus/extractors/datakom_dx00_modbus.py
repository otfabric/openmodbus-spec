"""Datakom D-300 / D-500 / D-700 Modbus Application Manual (PDF): register definitions and bit lists.

The register table (pages 11-16) gives decimal addresses that the read and write examples on pages 7
and 8 put unchanged into the request PDU (address 20h = 32 decimal -> "01 03 00 20 ..."). All data is
read with function 03, so every point is a holding register. The COEFF column (x1, x10, x100) is read
as "register = value x COEFF": the document does not define the column (see the class-09 report).

Page 10 contradicts itself on the order of 32-bit values ("the least significant register comes
first" and "the high order 16 bits are in the first register"), so no multi-register value is mapped.
Bit arrays (alarm bits) have an explicit, unambiguous layout on the same page.

The selector is the model ("d-300", "d-500", "d-700"); only the unit-mode enumeration differs.
"""
import re

from sourcelib import pdf_pages, require

PAGES = 18
TITLE = "D-300 / 500 / 700 Modbus Application Manual"
TABLE_PAGES = range(11, 17)
ALARM_PAGE = 17
MODELS = {"d-300": None, "d-500": "D500", "d-700": "D700"}

# Register description -> (point ID, data size, COEFF, UCUM unit or None).
# Units are taken only from the description wording; rows without a unit in the text get none.
VALUES = {
    "Genset frequency": ("generator_frequency", "16bit", "x100", None),
    "Battery voltage": ("battery_voltage", "16bit", "x100", None),
    "Oil pressure in bars (multiply by 14.50 to for psi)": ("oil_pressure", "16bit", "x10", "bar"),
    "Fuel level in %": ("fuel_level", "16bit", "x10", "%"),
    "Magnetic pickup input reading (rpm)": ("magnetic_pickup_speed", "16bit", "x1", "/min"),
    "Engine rpm": ("engine_speed", "16bit", "x1", "/min"),
}
ENUMS = {
    "Unit operation status": "operation_status",
    "Unit mode": "unit_mode",
    "Device identity information. (0xD300, 0xD500, 0xD700....)": "device_identity",
}
# Bit-array registers: description prefix -> point ID prefix. ALARM_WORDS are the first alarm bits of
# the 16-bit words mapped from each array (bit n is bit n % 16 of register start + n // 16).
ALARM_ARRAYS = {
    "Shutdown alarm bits.": "shutdown_alarms",
    "Warning alarm bits.": "warning_alarms",
}
ALARM_WORDS = (48, 96)
EXPONENTS = {"x1": None, "x10": -1, "x100": -2}

ROW = re.compile(r"^\s{0,3}(\d{4,5})(-(?:\d{2})?)?\s+(R|W)\s+(\d+)\s?bit\s+(x\d+|-)?\s+(\S.*?)\s*$")


def slug(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    require(words, f"Datakom: cannot name {text!r}")
    return "_".join(words)


def table_rows(pages):
    """Return the table rows as dicts; lines below a row that start no new row are kept in "more"."""
    rows = []
    for number in TABLE_PAGES:
        page = pages[number - 1]
        require(re.search(r"ADDRESS\s+R/W\s+DATA\s+COEFF\.\s+DESCRIPTION", page),
                f"Datakom page {number}: register table header missing")
        current = None
        for line in page.split("\n"):
            match = ROW.match(line)
            if match:
                start, dash, access, bits, coeff, text = match.groups()
                current = {"page": number, "start": int(start), "range": dash, "access": access,
                           "bits": f"{bits}bit", "coeff": coeff, "text": text, "more": []}
                rows.append(current)
            elif current is not None and line.strip() and not line.lstrip().startswith(("ADDRESS", "(decimal)")):
                current["more"].append(line)
    return rows


def find_row(rows, text, prefix=False):
    found = [row for row in rows if (row["text"].startswith(text) if prefix else row["text"] == text)]
    require(len(found) == 1, f"Datakom: {len(found)} rows for {text!r}")
    return found[0]


def status_entries(page, text):
    """Parse the two-column 'N= label' block under the operation status row."""
    lines = page.split("\n")
    heads = [index for index, line in enumerate(lines) if ROW.match(line) and ROW.match(line).group(6).startswith(text)]
    require(len(heads) == 1, f"Datakom {text}: row not found once")
    head = lines[heads[0]]
    require(head.count("=") == 1, f"Datakom {text}: expected one entry on the row line")
    left, right = head.index(text), head.index(re.search(r"\d+=", head).group())
    block = [head]
    for line in lines[heads[0] + 1:]:
        if ROW.match(line) or not line.strip():
            break
        block.append(line)
    entries = {}
    for side in (slice(left, right), slice(right, None)):
        last = None
        for line in block:
            part = line[side].strip()
            if not part or part == text:
                continue
            match = re.fullmatch(r"(\d+)\s*=\s*(.+?),?", part)
            if match:
                last = int(match.group(1))
                require(last not in entries, f"Datakom {text}: duplicate value {last}")
                entries[last] = match.group(2)
            else:
                require(last is not None and not re.search(r"\d=", part), f"Datakom {text}: stray text {part!r}")
                entries[last] = f"{entries[last]} {part}"
    return entries


def mode_entries(row):
    """Parse the one-column 'N= label' lines under a row; a value may repeat with a model tag."""
    entries = {}
    for line in row["more"]:
        match = re.fullmatch(r"\s*(\d+)\s*=\s*(.+?)\s*", line)
        require(match, f"Datakom {row['text']}: unexpected line {line!r}")
        entries.setdefault(int(match.group(1)), []).append(match.group(2))
    return entries


def alarm_bits(page):
    require(page.lstrip().startswith(TITLE) and "LIST OF ALARM BITS" in page, "Datakom page 17: alarm list missing")
    bits = {}
    for line in page.split("\n"):
        for match in re.finditer(r"(\d{3})(?:\.{3,4}(\d{3}))?:\s*(.+?)(?=\s{3,}\d{3}[.:]|\s*$)", line):
            first, last, label = match.groups()
            if last is not None:
                continue
            require(int(first) not in bits, f"Datakom alarm bit {first} listed twice")
            bits[int(first)] = label.strip()
    return bits


def extract(data, selector):
    require(selector in MODELS, f"Unknown Datakom model selector {selector!r}")
    pages = pdf_pages(data, 1, PAGES)
    require(all(page.lstrip().startswith(TITLE) for page in pages[1:]), "Datakom: running header missing")
    require("V5.6 (25.04.2016)" in pages[0], "Datakom: expected manual revision V5.6")
    # Address notation: decimal addresses go unchanged into the PDU (worked examples).
    require("starting from address 20h (32 decimal):" in pages[6] and "01 03 00 20 00 10 45 CC" in pages[6],
            "Datakom page 7: read example missing")
    require("to the register 40h (64 decimal):" in pages[7] and "01 06 00 40 00 10 89 D2" in pages[7],
            "Datakom page 8: write example missing")
    require("-Function 3 (Read multiple registers)" in pages[2], "Datakom page 3: read function missing")
    limit = re.search(r"The maximum number of registers read in one message is (\d+)\.", pages[6])
    require(limit, "Datakom page 7: read limit missing")
    formats = " ".join(pages[9].split())
    require("Bit arrays: Arrays larger than 16 bits are stored in multiple registers. The LSB of the first "
            "register is bit_0. The MSB of the first register is bit_15. The LSB of the second register is "
            "bit_16." in formats, "Datakom page 10: bit array layout missing")
    # The contradiction that keeps 32-bit values out of the contracts; review if a revision fixes it.
    require("The least significant register comes first." in formats
            and "The high order 16 bits are in the first register" in formats,
            "Datakom page 10: 32-bit word order statements changed, review the mapping")

    rows = table_rows(pages)
    points = []
    for text, (point_id, bits, coeff, unit) in VALUES.items():
        row = find_row(rows, text)
        require((row["access"], row["bits"], row["coeff"], row["range"]) == ("R", bits, coeff, None),
                f"Datakom {text}: unexpected access, size or coefficient")
        point = {"id": point_id, "aliases": [text], "address": row["start"], "type": "u16"}
        if EXPONENTS[coeff] is not None:
            point["conversion"] = {"exponent10": EXPONENTS[coeff]}
        if unit:
            point["unit"] = unit
        else:
            point["description"] = "The document states no unit for this register."
        point["source"] = {"address": str(row["start"]), "page": row["page"], "reference": "Register definitions"}
        points.append(point)

    for text, point_id in ENUMS.items():
        row = find_row(rows, text, prefix=point_id == "operation_status")
        require((row["access"], row["bits"], row["coeff"], row["range"]) == ("R", "16bit", "-", None),
                f"Datakom {text}: unexpected access, size or coefficient")
        point = {"id": point_id, "aliases": [text], "address": row["start"], "type": "u16"}
        if point_id == "operation_status":
            entries = status_entries(pages[row["page"] - 1], text)
            require(sorted(entries) == list(range(26)), "Datakom operation status: expected values 0-25")
            point["enum"] = {"values": [{"value": value, "name": slug(label), "label": label}
                                        for value, label in sorted(entries.items())]}
        elif point_id == "unit_mode":
            entries = mode_entries(row)
            require(sorted(entries) == [1, 2, 4, 8], "Datakom unit mode: expected values 1, 2, 4, 8")
            values = []
            for value, labels in sorted(entries.items()):
                if len(labels) == 1:
                    label = labels[0]
                else:
                    tagged = {re.fullmatch(r"(.+?) \((D\d00)\)", item).group(2):
                              re.fullmatch(r"(.+?) \((D\d00)\)", item).group(1) for item in labels}
                    require(set(tagged) == {"D500", "D700"}, f"Datakom unit mode {value}: unexpected models")
                    if MODELS[selector] is None:
                        continue
                    label = tagged[MODELS[selector]]
                require(label.endswith(" mode"), f"Datakom unit mode {value}: unexpected label {label!r}")
                values.append({"value": value, "name": slug(label[:-len(" mode")]), "label": label})
            point["enum"] = {"values": values}
            if MODELS[selector] is None:
                point["description"] = ("Value 2 is documented only for the D-500 (RUN mode) and the D-700 "
                                        "(MANUAL mode); it is left unnamed for the D-300.")
        else:
            codes = re.findall(r"0x(D\d00)", text)
            require(codes == ["D300", "D500", "D700"], "Datakom device identity: unexpected codes")
            point["enum"] = {"values": [{"value": int(code, 16), "name": f"d_{code[1:]}", "label": f"D-{code[1:]}"}
                                        for code in codes]}
            point["stability"] = "constant"
        point["source"] = {"address": str(row["start"]), "page": row["page"], "reference": "Register definitions"}
        points.append(point)

    bits = alarm_bits(pages[ALARM_PAGE - 1])
    for text, prefix in ALARM_ARRAYS.items():
        row = find_row(rows, text, prefix=True)
        require((row["access"], row["bits"], row["coeff"], row["range"]) == ("R", "256bit", "-", "-"),
                f"Datakom {text}: unexpected access or size")
        end = re.fullmatch(r"\s*(\d{5})\s+document\.", row["more"][0])
        require(end and int(end.group(1)) - row["start"] + 1 == 16, f"Datakom {text}: expected 16 registers")
        for first in ALARM_WORDS:
            register = row["start"] + first // 16
            flags = []
            for bit in range(16):
                require(first + bit in bits, f"Datakom alarm bit {first + bit} missing")
                label = bits[first + bit]
                flags.append({"bit": bit, "name": slug(label), "label": label})
            points.append({
                "id": f"{prefix}_{first}_{first + 15}",
                "label": f"{text[:-1]} {first:03d}-{first + 15:03d}",
                "address": register,
                "type": "u16",
                "flags": {"flags": flags},
                "source": {"address": f"{row['start']}-{end.group(1)} (register {register})", "page": row["page"],
                           "reference": f"Register definitions; list of alarm bits (page {ALARM_PAGE})"},
            })
    points.sort(key=lambda point: point["address"])
    return {"points": points, "constraints": {"maxReadRegisters": int(limit.group(1))}}
