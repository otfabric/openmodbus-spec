"""TECSYSTEM temperature monitoring unit manuals (PDF): the MODBUS MAPPING TABLE.

The selector names the manual: "nt935-ad", "nt935-eth" or "t1048". The three
manuals share one register layout: holding registers read with function code 3,
addressed by the "Address LO (10)" column, i.e. the decimal value of the
"Starting address LO" byte of the request (the "Starting address HI" byte is 0).
"""
import re

from sourcelib import pdf_page_count, pdf_pages, require

MODELS = {"nt935-ad": "NT935 AD", "nt935-eth": "NT935 ETH", "t1048": "T1048"}
FOOTERS = {"NT935", "NT935 ETH", "T1048"}
ROW = re.compile(r"^\s*(\d{1,2})\s{2,}(\S.*?)\s*$")
CAPTIONS = ("INFO various causes (READ)", "COMMANDS (WRITE)", "CHn SETTING", "CHn STATUS", "CHn STORY",
            "RELAY STATUS (coil energizing status)", "CPU ERROR", "CPU SETTING", "FAIL SAFE FUNCTION",
            "ETHERNET MODULE PARAMETER PROGRAMMING", "ETHERNET MODULE PROGRAMMING PARAMETER")
STATUS_BITS = {6: "TRIP", 5: "ALARM", 4: "FAN_2", 3: "FAN_1", 2: "FCD", 1: "FOC", 0: "FCC"}
STORY_BITS = {6: "TRIP", 5: "ALARM", 1: "FOC", 0: "FCC"}
CPU_BITS = {3: "PT ERROR", 2: "CAL", 1: "FCD Fault", 0: "ECH"}
RELAY_BITS = {4: "FAULT", 3: "TRIP", 2: "ALARM", 1: "FAN_2", 0: "FAN_1"}


def squash(value):
    return " ".join(value.split())


def cells(line):
    return [(match.start(), match.group()) for match in re.finditer(r"\S+(?: \S+)*", line)]


SPAN = r"(–?\d+° ?(?:C|to)? ?÷ ?\d+°(?:C)?)"


def span(text):
    low, high = re.fullmatch(r"(–?\d+)° ?(?:C|to)? ?÷ ?(\d+)°(?:C)?", text).groups()
    return f"{low.replace('–', '-')} °C to {high} °C"


def header_block(pages, caption):
    """Text between a table caption and its first row."""
    for page in pages:
        lines = page.split("\n")
        for index, line in enumerate(lines):
            if squash(line) == caption:
                block = []
                for following in lines[index + 1:]:
                    if ROW.match(following):
                        return squash(" ".join(block))
                    block.append(following)
    raise_missing(caption)


def raise_missing(caption):
    require(False, f"TECSYSTEM: table {caption!r} missing")


def mapping_pages(data):
    pages = pdf_pages(data, 1, pdf_page_count(data))
    starts = [index for index, page in enumerate(pages)
              if re.search(r"MODBUS MAPPING TABLE\s+HEADER \(information and commands\):", page)]
    require(len(starts) == 1, "TECSYSTEM: MODBUS MAPPING TABLE not found exactly once")
    ends = [index for index, page in enumerate(pages) if index >= starts[0] and "CPU ERROR" in page]
    require(ends and ends[0] - starts[0] <= 5, "TECSYSTEM: register notes not found after the mapping table")
    return pages, starts[0], ends[0]


def table_rows(pages, start, end):
    """Return {address: (page, row text, previous line, next line)}; identical duplicate rows are merged."""
    rows = {}
    for index in range(start, end + 1):
        lines = pages[index].split("\n")
        for position, line in enumerate(lines):
            match = ROW.match(line)
            if not match or squash(match.group(2)) in FOOTERS:
                continue
            address, text = int(match.group(1)), squash(match.group(2))
            before = squash(lines[position - 1]) if position else ""
            after = squash(lines[position + 1]) if position + 1 < len(lines) else ""
            if address in rows:
                require(rows[address][1] == text or text.startswith("00 00"),
                        f"TECSYSTEM: conflicting rows for address {address}")
                continue
            rows[address] = (index + 1, text, before, after)
    return rows


def bit_table(page, caption):
    """Return {bit: text} for the bit table under `caption`, assigning each cell to the nearest BIT column."""
    lines = page.split("\n")
    starts = [index for index, line in enumerate(lines) if squash(line) == caption]
    require(len(starts) == 1, f"TECSYSTEM: bit table {caption!r} not found exactly once")
    header_index = next(index for index in range(starts[0] + 1, len(lines)) if "BIT 7" in lines[index])
    columns = [(match.start() + len(match.group()) / 2, int(match.group(1)))
               for match in re.finditer(r"BIT (\d)", lines[header_index])]
    require([bit for _, bit in columns] == list(range(7, -1, -1)), f"TECSYSTEM {caption}: BIT 7..0 header missing")
    bits = {bit: [] for bit in range(8)}
    for line in lines[header_index + 1:]:
        if squash(line) in CAPTIONS or "BIT 7" in line:
            break
        match = ROW.match(line)
        if match and squash(match.group(2)) in FOOTERS:
            break
        for start, cell in cells(line):
            centre = start + len(cell) / 2
            bit = min(columns, key=lambda column: abs(column[0] - centre))[1]
            bits[bit].append(cell)
    return {bit: squash(" ".join(words)) for bit, words in bits.items()}


def require_bits(found, expected, caption):
    for bit in range(8):
        if bit in expected:
            require(found[bit].startswith(expected[bit]), f"TECSYSTEM {caption}: bit {bit} is {found[bit]!r}")
        else:
            require(found[bit] in ("--", "-", "", "0"), f"TECSYSTEM {caption}: unexpected bit {bit} {found[bit]!r}")


def meanings(pages):
    """Sensor fault and CPU error meanings from the diagnostics sections."""
    joined = squash(" ".join(pages))
    sensor = re.search(r"sensor fault \(FCC (short-circuited sensor), FOC (interrupted sensor) or Fcd "
                       r"(quick temperature increase)\)", joined)
    require(sensor, "TECSYSTEM: sensor fault definitions missing")
    cpu = re.search(r"1\) ECH (eeprom fault) erasable message 2\) CAL (measurement circuit fault) erasable message "
                    r".*?4\) ERR PT (FCC or FOC sensor fault) non-resettable", joined)
    require(cpu, "TECSYSTEM: diagnostics list missing")
    fcc, foc, fcd = sensor.groups()
    ech, cal, pt = cpu.groups()
    return {"FCC": fcc, "FOC": foc, "FCD": fcd, "ECH": ech, "CAL": cal, "PT ERROR": pt, "FCD Fault": fcd}


def flag(bit, name, label, meaning=None):
    return {"bit": bit, "name": name, "label": f"{label}: {meaning}" if meaning else label}


def extract(data, selector):
    require(selector in MODELS, f"Unknown TECSYSTEM selector {selector!r}")
    model = MODELS[selector]
    pages, start, end = mapping_pages(data)
    joined = squash(" ".join(pages))
    require(f"{model.split()[0]}" in pages[start - 1] + pages[start] + pages[end], f"TECSYSTEM: {model} footer missing")
    require(re.search(r"3\(10\): - holding register reading", joined), "TECSYSTEM: FC 3 statement missing")
    require("Request: Slave address, code 3(10), Starting address HI, Starting address LO, Number of Point HI, "
            "Number of Point LO, Crc LO, Crc HI." in joined, "TECSYSTEM: FC 3 request layout missing")
    for caption in ("HEADER (information and commands):", "TEMPERATURES channels 1÷4:", "CHANNELs 1÷4: Status"):
        header = header_block(pages[start:end + 1], caption).split()
        require(all(word in header for word in ("Address", "LO", "(10)", "HI", "Data")),
                f"TECSYSTEM {caption}: Address LO (10) / Data HI / Data LO header missing")
    disabled = re.search(r"(If the channel 4 is not enabled|In the case in which the channel is not enabled) "
                         r"and ?/ ?or the information is not provided(?: for)?,? (?:the following answers are given|"
                         r"we have the following answers): 1\. (?:Measured temperatures|Temperatures measured) = 0000 "
                         r"\(0 ?° ?C\)", joined)
    require(disabled, "TECSYSTEM: disabled-channel note missing")
    disabled_channels = (4,) if "channel 4" in disabled.group(1) else (1, 2, 3, 4)
    rows = table_rows(pages, start, end)
    words = meanings(pages)
    points = []

    def row(address, pattern, what):
        require(address in rows, f"TECSYSTEM: row {address} ({what}) missing")
        page, text, before, after = rows[address]
        match = re.fullmatch(pattern, text)
        require(match, f"TECSYSTEM row {address}: expected {what}, found {text!r}")
        return page, match, before, after

    def find(pattern, what):
        found = [address for address, (_, text, _, _) in rows.items() if re.fullmatch(pattern, text)]
        require(len(found) == 1, f"TECSYSTEM: {what} row not found exactly once")
        return found[0]

    def add(point_id, address, kind, alias, page, reference, **extra):
        point = {"id": point_id, "address": address, "type": kind}
        point.update(extra)
        point["aliases"] = [alias]
        point["source"] = {"address": str(address), "page": page, "reference": reference}
        points.append(point)

    # Header: model and firmware as ASCII digits, most significant digit in the high byte of the first register.
    for point_id, first_pattern, second_pattern, alias in (
            ("model", r"Modello – MSD \(ASCII\) Modello - 3° Digit \(ASCII\) R",
             r"Modello - 2° Digit \(ASCII\) Modello – LSD \(ASCII\) R", "Modello"),
            ("firmware_version", r"Space \(20H\) Vers\. Fw – MSD\(ASCII\) R",
             r"Vers\. Fw - 2° Digit \(ASCII\) Vers\. Fw – LSD\(ASCII\) R", "Vers. Fw")):
        address = find(first_pattern, point_id)
        page, _, _, _ = row(address, first_pattern, point_id)
        row(address + 1, second_pattern, point_id)
        extra = {"registers": 2}
        if point_id == "firmware_version":
            extra["description"] = "A space (20H) followed by three ASCII characters."
        else:
            extra["description"] = "Four ASCII characters, most significant digit first."
        add(point_id, address, "string", alias, page, "MODBUS MAPPING TABLE, HEADER", stability="constant", **extra)

    def notes(caption):
        """The bit table under `caption` in the notes that follow the mapping table."""
        found = [page for page in pages[start:end + 1]
                 if re.search(rf"^\s*{re.escape(caption)}\s*$", page, re.MULTILINE)]
        require(len(found) == 1, f"TECSYSTEM: notes table {caption!r} not on exactly one page")
        return bit_table(found[0], caption)

    # CPU error and relay status bit fields (high byte 00).
    cpu = notes("CPU ERROR")
    require_bits(cpu, CPU_BITS, "CPU ERROR")
    address = find(r"00 CPU Error See Note R", "CPU Error")
    add("cpu_error", address, "u16", "CPU Error", rows[address][0], "SYSTEM: Setting and Status",
        flags={"flags": [flag(bit, re.sub(r"\W+", "_", text.lower()), text, words[text])
                         for bit, text in sorted(CPU_BITS.items())]},
        description="Bit field in the low byte; the high byte is 00.")
    relays = notes("RELAY STATUS (coil energizing status)")
    require_bits(relays, RELAY_BITS, "RELAY STATUS")
    relay_flags = []
    for bit, name in sorted(RELAY_BITS.items()):
        text = re.fullmatch(rf"{name} [Rr]elay (1=ON|1=No Fault)", relays[bit])
        require(text, f"TECSYSTEM RELAY STATUS: bit {bit} is {relays[bit]!r}")
        relay_flags.append(flag(bit, f"{name.lower()}_relay", f"{name} relay, {text.group(1)}"))
    address = find(r"00 Relays Status See Note R", "Relays Status")
    add("relay_status", address, "u16", "Relays Status", rows[address][0], "SYSTEM: Setting and Status",
        flags={"flags": relay_flags},
        description="Coil energizing state of the relays, subject to the FAIL SAFE settings. "
                    "The high byte is 00.")

    # Temperatures: 16-bit two's complement in degrees Celsius; the table gives no scaling.
    for channel in range(1, 5):
        pattern = rf"2’compl\. sign 2’compl\. Ch{channel} temper\.(?: (–?\d+°(?:C)? ÷ \d+°(?:C)?))? R"
        address = find(pattern, f"Ch{channel} temperature")
        page, match, before, after = row(address, pattern, f"Ch{channel} temperature")
        main = match.group(1) or re.fullmatch(SPAN, before)
        main = main if isinstance(main, str) else main and main.group()
        require(main, f"TECSYSTEM Ch{channel} temperature: range missing")
        text = f"Measured temperature, range {span(main)}"
        alternative = re.fullmatch(SPAN + r" ?\(\*\)", after)
        if alternative:
            require("(*) for version –40°C ÷ +200°C" in pages[page - 1], "TECSYSTEM: range footnote missing")
            text += f" ({span(alternative.group(1))} on the -40 °C to +200 °C version)"
        text += "."
        if channel in disabled_channels:
            text += " Reads 0000 (0 °C) when the channel is not enabled."
        add(f"ch{channel}_temperature", address, "i16", f"Ch{channel} temper.", page,
            "MODBUS MAPPING TABLE, TEMPERATURES channels 1÷4", unit="Cel", description=text)
    pattern = r"2’compl\. sign 2’compl\. Ch1 max temperat\.(?: (\d+° ÷ \d+°))? R"
    address = find(pattern, "Ch1 max temperature")
    add("ch1_max_temperature", address, "i16", "Ch1 max temperat.", rows[address][0],
        "MODBUS MAPPING TABLE, TEMPERATURES channels 1÷4", unit="Cel",
        description="Channel 1 maximum temperature.")
    for kind, setpoint in (("AL", "alarm"), ("TRP", "trip")):
        candidates = [address for address, (_, text, before, after) in rows.items()
                      if re.fullmatch(rf"2’compl\. sign(?: \d+° ÷ \d+°)? \({kind}\) RW", text)
                      and "Ch1 temper." in before and f"{setpoint} set point" in after]
        require(len(candidates) == 1, f"TECSYSTEM: Ch1 {setpoint} set point row not found exactly once")
        address = candidates[0]
        add(f"ch1_{setpoint}_setpoint", address, "i16", f"Ch1 temper. ({kind}) {setpoint} set point",
            rows[address][0], "MODBUS MAPPING TABLE, TEMPERATURES channels 1÷4", unit="Cel",
            description=f"Channel 1 {setpoint} threshold. Read/write in the device; read-only here.")

    # Channel status (low byte) and story (high byte).
    status = notes("CHn STATUS")
    require_bits(status, STATUS_BITS, "CHn STATUS")
    story = notes("CHn STORY")
    require_bits(story, STORY_BITS, "CHn STORY")

    def channel_flags(bits):
        return {"flags": [flag(bit, text.lower(), text, words.get(text)) for bit, text in sorted(bits.items())]}

    components = {"flagSets": {"channel_status": channel_flags(STATUS_BITS),
                               "channel_story": channel_flags(STORY_BITS)}}

    for channel in range(1, 5):
        pattern = rf"Ch{channel} story Ch{channel} status See Note CHx R"
        address = find(pattern, f"Ch{channel} status")
        page = rows[address][0]
        add(f"ch{channel}_status", address, "u16", f"Ch{channel} status", page,
            "MODBUS MAPPING TABLE, CHANNELs 1÷4: Status", mask=0x00FF,
            flags={"$ref": "#/components/flagSets/channel_status"},
            description="Data LO byte of the register.")
        if channel == 1:
            add("ch1_story", address, "u16", "Ch1 story", page, "MODBUS MAPPING TABLE, CHANNELs 1÷4: Status",
                mask=0xFF00, flags={"$ref": "#/components/flagSets/channel_story"},
                description="Data HI byte of the register.")
    return {"components": components,
            "points": sorted(points, key=lambda point: (point["address"], point.get("mask", 0)))}
