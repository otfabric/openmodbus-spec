"""Fanox protection relay Modbus protocol manuals (PDF): 32-bit state words.

The selector is the model, "sil-a", "sia-c" or "sia-b". All three manuals read states with
FC 03 from holding registers. Table addresses are PDU addresses: the worked frame that
writes the access code to address 168 carries 0x00A8. Multi-byte formats are sent most
significant byte first, so a two-register state word has its high word first. The SIL-A
manual also lists every state in one-register form (firmware M05.03.04 onwards); the
extractor checks that bit n < 16 of word A sits in register A + 1 and bit n >= 16 in
register A, which confirms both the word order and the bit numbering (bit 0 = LSB).

The model and version string (format ASCIIxx, xx/2 registers, NUL-terminated) comes from the
general memory map. Measurements are not extracted: the manuals give no unit and their float
format ("FLOAT" versus "FLOAT INVERSE") is not defined consistently.
"""
import re

from sourcelib import CorpusError, pdf_page_count, pdf_pages, require

# word description -> (point id, {status label: flag name}); a flag name of the form
# "mask:<id>" makes a separate single-bit mask point instead of a flag.
MODELS = {
    "sil-a": {
        "title": r"SIL-A\s+Feeder Relay\s+MODBUS PROTOCOL MANUAL",
        "byte_order": r"When the data format takes up more than one BYTE, the most important BYTE is sent "
                      r"through the communications first",
        "width": r"Number of registries: 2\s+Type: Bit string 32 bits, Most significant bit first \(MSB-LSB\)",
        "single": r"1\.5\.2\.\s+States Map for FC03, 1 registry",
        "end": r"1\.5\.3\.\s+States identifiers",
        "event_column": True,
        "words": {
            "Self-diagnosis": ("self_diagnosis", {
                "Model Error": "model_error", "Hardware Error": "hardware_error", "COM Error": "com_error",
                "Test State": "test_state", "Settings Error": "settings_error",
                "Configuration Error": "configuration_error"}),
            "General": ("general", {
                "Trip": "trip", "Ready": "ready", "Phase Trip": "phase_trip", "Trip Block": "trip_block",
                "Pickup": "pickup", "Phase A pickup": "phase_a_pickup", "Phase B Pickup": "phase_b_pickup",
                "Phase C Pickup": "phase_c_pickup", "Neutral Pickup": "neutral_pickup",
                "Phase A Trip": "phase_a_trip", "Phase B Trip": "phase_b_trip", "Phase C Trip": "phase_c_trip",
                "Neutral Trip": "neutral_trip"}),
            "50-1": ("overcurrent_50_1", {
                "Pickup": "pickup", "Phase Trip": "trip"}),
            "50G-1": ("earth_overcurrent_50g_1", {
                "Neutral Pickup": "pickup", "Neutral Trip": "trip"}),
            "49": ("thermal_49", {"Alarm": "alarm", "Trip": "trip"}),
            "52": ("breaker_52", {
                "Error": "mask:cb_error", "Open": "mask:cb_open", "Closed": "mask:cb_closed"}),
        },
    },
    "sia-c": {
        "title": r"SIA C\s+Self Power O/C & E/F Protection Relay\s+MODBUS RTU PROTOCOL MANUAL",
        "byte_order": r"When the data format takes up more than one BYTE, the most important BYTE is sent "
                      r"through the communications first",
        "width": r"BIT32\s+2\s+Gathered bits type, groups of 32",
        "end": r"1\.5\.2\.\s+Measurements Map",
        "event_column": True,
        "starred": (r"\(\*\) Depending on model\.", "depending on model"),
        "words": {
            "General": ("general", {
                "Trip": "trip", "External Trip": "external_trip", "Ready": "ready", "EEPROM Error": "eeprom_error",
                "Pickup": "pickup", "Phase A Pickup": "phase_a_pickup", "Phase B Pickup": "phase_b_pickup",
                "Phase C Pickup": "phase_c_pickup", "Ground Pickup": "ground_pickup",
                "Phase A Trip": "phase_a_trip", "Phase B Trip": "phase_b_trip", "Phase C Trip": "phase_c_trip",
                "Ground Trip": "ground_trip", "Aux. Power": "aux_power", "Self-Power": "self_power"}),
            "50-1": ("overcurrent_50_1", {"50-1 Pickup": "pickup", "50-1 Trip": "trip"}),
            "50/51": ("overcurrent_50_51", {"50/51 Pickup": "pickup", "50/51 Trip": "trip"}),
            "50G-1": ("earth_overcurrent_50g_1", {"50N/G Pickup": "pickup", "50N/G Trip": "trip"}),
            "50/51G": ("earth_overcurrent_50_51g", {"50/51G Pickup": "pickup", "50/51G Trip": "trip"}),
            "Outputs": ("outputs", {"Trip Output": "trip_output"}),
            "49 (*)": ("thermal_49", {"49 Alarm": "alarm", "49 Trip": "trip"}),
            "52 (*)": ("breaker_52", {"52 Error": "mask:cb_error", "52 Open": "mask:cb_open",
                                      "52 Close": "mask:cb_closed"}),
        },
    },
    "sia-b": {
        "title": r"SIA-B Specific CT´s\s+Self & Dual Powered\s+Overcurrent & Earth Fault\s+Protection Relay",
        "byte_order": r"When a data format takes up more than 1 byte, it is always sent, firstly the most "
                      r"significant BYTE",
        "width": r"The number of registries for all states is 2\.",
        "end": r"1\.7\.\s+Measurements Map",
        "event_column": True,
        "starred": (None, "this manual does not say what the mark means"),
        "words": {
            "General": ("general", {
                "Trip": "trip", "External Trip": "external_trip", "Trip Block Enable": "trip_block_enable",
                "Ready": "ready", "EEPROM Error": "eeprom_error", "Pickup (*)": "pickup"}),
            "50": ("overcurrent_50", {
                "50 Phase A Pickup": "phase_a_pickup", "50 Pickup": "pickup", "50 Trip": "trip"}),
            "50/51": ("overcurrent_51", {"51 Pickup": "pickup", "51 Trip": "trip"}),
            "50N": ("earth_overcurrent_50n", {"50N Pickup": "pickup", "50N Trip": "trip"}),
            "50/51N": ("earth_overcurrent_51n", {"51N Pickup": "pickup", "51N Trip": "trip"}),
            "Outputs": ("outputs", {"Trip Output": "trip_output"}),
            "49 (*)": ("thermal_49", {"49 Alarm": "alarm", "49 Trip": "trip"}),
        },
    },
}

# The general memory map lists "Write access code" at 168 and a worked FC 16 frame writes it to
# start address 0x00A8, so table addresses are PDU addresses.
FRAME = r"Write access code\s+168\b.*?0x10\s+0x00\s+0xA8"
FRAME_SPELLED = r"Write access code\s+168\b.*?Function\s+10\s+H start address\s+00\s+L start address\s+A8"
HEADER = re.compile(r"^\s*Address\s+Description\s+Bit\b")
MODEL_ROW = re.compile(r"^\s*03\s+Read of Model and Version\s+(\d+)\s+(\d+)\s+ASCII(\d+)\s*$", re.MULTILINE)
STRING_TYPE = (r"ASCIIxx xx/2",
               r"String: (?:In length|Length) variable character chain\. Final of String marked with ‘\\0’\.")
FOOTER = re.compile(r"^\s*www\.fanox\.com\s+Rev\.")
ADDRESS = re.compile(r"^\s{0,12}(\d{3})(?:\s{2,}(.*))?$")
BIT = re.compile(r"^\s{10,}(\d{2}|-)(?:\s{2,}(.*))?$")
# Where the address sits alone on its line the description is printed on a line of its own or
# in front of a bit row (SIL-A Rev. 05, 724/725 LMS).
DESCRIBED = re.compile(r"^\s{10,}([A-Za-z](?:\S| (?=\S))*)(?:\s{2,}((?:\d{2}|-)(?:\s{2,}.*)?))?\s*$")


def parse_bit(text, event_column):
    """(bit or None, status) from the cells after the address/description columns."""
    match = re.match(r"(\d{2}|-)(?:\s{2,}(.*))?$", text.strip())
    if not match:
        return None
    bit = None if match.group(1) == "-" else int(match.group(1))
    cells = [cell for cell in re.split(r"\s{2,}", match.group(2) or "") if cell and cell != "√"]
    if event_column and cells and re.fullmatch(r"\d+|-", cells[0]):
        cells = cells[1:]
    return bit, (cells[0] if cells else None)


def split_address(rest, event_column):
    """(description or None, bit-row text or None) for the cells after an address.

    A bit row starts with the bit and, where the table has one, the event number. A numeric
    description ("46", "52") is told apart by an extra leading number ("52  05  06  Closed")
    or by standing alone ("46").
    """
    cells = [cell for cell in re.split(r"\s{2,}", rest.strip()) if cell and cell != "√"] if rest else []
    if not cells:
        return None, None
    leading = 0
    while leading < len(cells) and re.fullmatch(r"\d{2}|-", cells[leading]):
        leading += 1
    if leading == 0 or leading > (2 if event_column else 1) or len(cells) == 1:
        return cells[0], "  ".join(cells[1:]) or None
    return None, "  ".join(cells)


def state_words(lines, event_column, described_only=True):
    """Map address -> [{description, bits {label: bit}, page}] for one states map.

    A word is a run of rows with rising bit numbers. Its address is the address line that
    carries one of its rows or, failing that, the one free address line printed within the
    run or on the line just before or after it. With described_only False a word may lack a
    description (the SIL-A one-register map prints 724 without one); such a word can only be
    found by its address.
    """
    words = {}
    runs = []  # each run: [(line, bit, label, page)]
    addresses = []  # (line, address, description or None, run of the row on the same line)
    described = []  # (line, description) for addresses printed without one
    run = None
    for index, (page, line) in enumerate(lines):
        if HEADER.match(line):
            run = None
            continue
        address = ADDRESS.match(line)
        loose = None if address else DESCRIBED.match(line)
        row = None
        description = None
        if address:
            description, rest = split_address(address.group(2), event_column)
            if rest:
                row = parse_bit(rest, event_column)
        elif loose:
            described.append((index, loose.group(1)))
            if loose.group(2):
                row = parse_bit(loose.group(2), event_column)
        elif BIT.match(line):
            row = parse_bit(line, event_column)
        if row and row[0] is not None:
            require(row[0] <= 31, f"Fanox: state bit {row[0]} on line {index} is not a 32-bit position")
            if run is None or run[-1][1] >= row[0]:
                run = []
                runs.append(run)
            run.append((index, row[0], row[1], page))
        if address:
            owner = run if row and row[0] is not None else None
            addresses.append((index, int(address.group(1)), description, owner))
    used = set()
    for run in runs:
        first, last = run[0][0], run[-1][0]
        inside = [entry for entry in addresses if entry[3] is run]
        if not inside:
            inside = [entry for entry in addresses if entry[3] is None and first - 1 <= entry[0] <= last + 1]
        require(len(inside) == 1, f"Fanox: state rows {first}-{last} have {len(inside)} addresses")
        require(inside[0][0] not in used, f"Fanox: address line {inside[0][0]} serves two state words")
        used.add(inside[0][0])
        _, address, description, _ = inside[0]
        if description is None:
            texts = [text for line, text in described if first <= line <= last]
            require(len(texts) == 1 or (not texts and not described_only),
                    f"Fanox: address {address} has {len(texts)} descriptions")
            description = texts[0] if texts else None
        bits = {}
        for _, bit, label, page in run:
            if label is not None:
                require(label not in bits, f"Fanox: {address} lists {label!r} twice")
                bits[label] = bit
        # Keep every table: a manual may list one address twice (SIL-A Rev. 05 lists 636 as both
        # SIGNALLING and Control LEDs); a selected word must not share its address.
        words.setdefault(address, []).append({"description": description, "bits": bits, "page": run[0][3]})
    require(len(used) == len(addresses), f"Fanox: {len(addresses) - len(used)} address lines without state rows")
    return words


def section_lines(pages, first, start, stop):
    """(page number, line) from the heading `start` up to the heading `stop`, skipping the contents."""
    lines = []
    active = start is None
    for number, page in enumerate(pages[first - 1:], start=first):
        for line in page.splitlines():
            if "...." in line:
                continue
            if start and re.search(start, line):
                active = True
            if active and re.search(stop, line):
                return lines
            if active and line.strip() and not FOOTER.match(line):
                lines.append((number, line))
    raise CorpusError(f"Fanox: section ending {stop!r} not found")


def extract(data, selector):
    require(selector in MODELS, f"Unknown Fanox selector {selector!r}")
    model = MODELS[selector]
    pages = pdf_pages(data, 1, pdf_page_count(data))
    flat = re.sub(r"\s+", " ", " ".join(pages))
    for key in ("title", "byte_order", "width"):
        require(re.search(model[key].replace(r"\s+", " "), flat), f"Fanox {selector}: {key} statement missing")
    require(re.search(FRAME, flat) or re.search(FRAME_SPELLED, flat),
            f"Fanox {selector}: access-code frame example (168 = 0x00A8) missing")

    first = [number for number, page in enumerate(pages, start=1)
             if re.search(r"States Map.*\n\s*The function code implemented to State reading", page)]
    require(len(first) == 1, f"Fanox {selector}: states map heading found {len(first)} times")
    lines = section_lines(pages, first[0], None, model.get("single") or model["end"])
    words = state_words(lines, model["event_column"])
    for address in words:
        require(address % 2 == 0, f"Fanox {selector}: state word {address} is not on an even address")
    require(max(max(word["bits"].values(), default=0) for entries in words.values() for word in entries) > 15,
            f"Fanox {selector}: no state bit above 15, the words would not be 32-bit")

    single = None
    if "single" in model:
        single_lines = section_lines(pages, first[0], model["single"], model["end"])
        single = state_words(single_lines, False, described_only=False)

    by_description = {}
    for address, entries in words.items():
        for word in entries:
            by_description.setdefault(word["description"], []).append(address)

    require(all(re.search(part, flat) for part in STRING_TYPE), f"Fanox {selector}: ASCIIxx type definition missing")
    rows = [(number, match) for number, page in enumerate(pages, start=1) for match in MODEL_ROW.finditer(page)]
    require(len(rows) == 1, f"Fanox {selector}: model and version row found {len(rows)} times")
    model_page, row = rows[0]
    start, registers, characters = (int(value) for value in row.groups())
    require(characters == 2 * registers, f"Fanox {selector}: ASCII{characters} in {registers} registers")

    pattern, starred = model.get("starred", (None, None))
    require(pattern is None or re.search(pattern.replace(r"\s+", " "), flat), f"Fanox {selector}: (*) note missing")

    points = []
    for description, (point_id, labels) in model["words"].items():
        addresses = by_description.get(description, [])
        require(len(addresses) == 1, f"Fanox {selector}: state word {description!r} found {len(addresses)} times")
        address = addresses[0]
        require(len(words[address]) == 1, f"Fanox {selector}: address {address} is listed for several state words")
        word = words[address][0]
        flags = []
        base = description.replace(" (*)", "")
        for label, name in labels.items():
            require(label in word["bits"], f"Fanox {selector}: {description} has no state {label!r}")
            bit = word["bits"][label]
            if single is not None:
                register, position = (address + 1, bit) if bit < 16 else (address, bit - 16)
                entries = single.get(register, [])
                require(len(entries) == 1 and entries[0]["bits"].get(label) == position,
                        f"Fanox {selector}: {label!r} bit {bit} of {address} is not bit {position} of {register}")
            source = {"address": f"{address}" if not name.startswith("mask:") else f"{address} bit {bit:02d}",
                      "page": word["page"], "reference": f"States Map, {description}"}
            note = f"Marked (*) in the states map: {starred}." if "(*)" in f"{description} {label}" else None
            require(note or "(*)" not in f"{description} {label}", f"Fanox {selector}: unexplained (*) on {label!r}")
            if name.startswith("mask:"):
                point = {"id": name[5:], "address": address, "type": "u32", "mask": 1 << bit,
                         "aliases": [label if label.startswith(base) else f"{base} {label}"]}
                if note:
                    point["description"] = note
                point["source"] = source
                points.append(point)
            else:
                flags.append({"bit": bit, "name": name, "label": label})
        if flags:
            point = {"id": point_id, "address": address, "type": "u32",
                     "flags": {"flags": sorted(flags, key=lambda flag: flag["bit"])},
                     "aliases": [description]}
            marked = [flag["label"] for flag in flags if "(*)" in flag["label"]]
            if "(*)" in description:
                point["description"] = f"Marked (*) in the states map: {starred}."
            elif marked:
                point["description"] = f"{', '.join(marked)} marked in the states map: {starred}."
            point["source"] = {"address": str(address), "page": word["page"],
                               "reference": f"States Map, {description}"}
            points.append(point)
    points.append({
        "id": "model_and_version", "address": start, "type": "string", "registers": registers,
        "aliases": ["Read of Model and Version"],
        "description": f"ASCII{characters}: character string ended by a NUL character.",
        "source": {"address": str(start), "page": model_page, "reference": "General Memory Map"},
    })
    return sorted(points, key=lambda point: (point["address"], point.get("mask", 0)))
