"""AutomationDirect Stride Field I/O user guides (PDF): Modbus register and coil tables.

The selector is the module name, e.g. "SIO-MB12CDR". The guides give holding
registers in 4xxxx notation and coils in 0xxxx notation (decimal, with the same
number in hexadecimal). They do not state the address base in words, but each
register that mirrors a group of coils pins it down: the bit diagrams place coil
reference c in register reference r = 40001 + (c - 1) // 16, at bit
((c - 1) % 16) ^ 8, so the first coil of each register is its bit 8. No
zero-based reading of the references fits the diagrams. The extractor checks
this for every mirrored bit it uses, then resolves the references as 1-based.

Points are taken in groups, in priority order, while the contract stays within
MAX_POINTS points.
"""
import re

from sourcelib import modicon_reference, pdf_pages, require

TABLE_PAGE = 2
MAX_POINTS = 20
REGISTER = re.compile(r"^\s+(4\d{4})\s+(\S.*?)\s{2,}(RO|R/W)(?=\s|$)")
COIL = re.compile(r"(0x[0-9A-F]{4})\s+(\d{5})\s+(\S.*?)\s{2,}(RO|R/W)\s*$")
HEADING = re.compile(r"^(4\d{4})(?:\s*(?:[–-]|/)\s*(4\d{4}))?:\s+(.+?)(?:\s{3,}.*)?$")
BITS = [f"{bit:02d}" for bit in range(15, -1, -1)]
MODELS = {
    "SIO-MB12CDR": ("Discrete Combo Module: 8-point in, 4-point out", ("di", "do", "system_flags", "frequency",
                                                                       "firmware")),
    "SIO-MB16CDD2": ("Discrete Combo Module: 8-point in, 8-point out", ("di", "do", "system_flags", "frequency",
                                                                        "firmware")),
    "SIO-MB08THMS": ("Temperature Input Module: thermocouple, 8-channel in", ("ai", "input_type", "break_status",
                                                                              "system_flags", "firmware")),
}
SYSTEM_FLAGS = {"Watchdog Enable": "watchdog_enable", "Watchdog Event": "watchdog_event",
                "Power Up Event": "power_up_event", "Short Circuit Alarm": "short_circuit_alarm"}
INPUT_TYPES = {"Disabled": "disabled", "250mV": "mv_250", "TC J": "tc_j", "TC K": "tc_k", "TC R": "tc_r",
               "TC S": "tc_s", "TC T": "tc_t", "TC B": "tc_b", "TC E": "tc_e", "TC N": "tc_n"}
FREQUENCY = ("The value is in 16-bit unsigned integer format, with units of hundredths of Hertz "
             "(i.e., Hertz with an implied two decimal places).")
ANALOG = ("These registers return the measurement of each channel, converted to engineering units. The values are "
          "stored in the registers as 16-bit signed integers. Values for thermocouple sensor types are stored with "
          "one implied decimal place. Values are stored with two implied decimal places for mV inputs.")
ANALOG_EXAMPLE = "Input type set as Tc: 246 stored in the register indicates 24.6°C"


def normalized(text):
    return " ".join(text.split())


def tables(page):
    """Register rows {reference: (label, access)} and coil rows {reference: (label, access, hex)}."""
    registers, coils = {}, {}
    for line in page.splitlines():
        register = REGISTER.match(line)
        if register:
            reference, label, access = register.groups()
            require(reference not in registers, f"Stride: duplicate register {reference}")
            registers[reference] = (normalized(label), access)
        coil = COIL.search(line)
        if coil:
            hexadecimal, reference, label, access = coil.groups()
            require(int(hexadecimal, 16) == int(reference), f"Stride: coil {reference} and {hexadecimal} disagree")
            require(reference not in coils, f"Stride: duplicate coil {reference}")
            coils[reference] = (normalized(label), access, hexadecimal)
    require(registers and coils, "Stride: register or coil table missing")
    return registers, coils


def sections(pages, first_page):
    """Register descriptions {reference: {"title", "page", "lines"}}; grouped headings share one body."""
    found, group = {}, []
    for number, page in enumerate(pages, first_page):
        for line in page.splitlines():
            heading = HEADING.match(line)
            if heading:
                if group and any(found[reference]["lines"] for reference in group):
                    group = []
                first, second, title = heading.groups()
                for reference in filter(None, (first, second)):
                    require(reference not in found, f"Stride: duplicate description of {reference}")
                    found[reference] = {"title": title.strip(), "page": number, "lines": []}
                    group.append(reference)
            elif group:
                for reference in group:
                    found[reference]["lines"].append(line)
    return found


def left_column(line, width):
    """Drop a right-hand column: text after a wide gap that starts well beyond the bit diagram's width."""
    for text in re.finditer(r"(?:^|\s{12,})(\S+)", line):
        if text.start(1) > width + 10:
            return line[:text.start(1)].rstrip()
    return line


def diagram(section, row_label):
    """Return {bit: token} from the bit diagram row, and the diagram's description lines."""
    lines = section["lines"]
    starts = [index for index, line in enumerate(lines) if re.match(r"\s+Bit\s", line)]
    require(len(starts) == 1, f"Stride {section['title']}: {len(starts)} bit diagrams")
    header = lines[starts[0]].rstrip()
    tokens = header.split()[1:]
    require(tokens[:16] == BITS, f"Stride {section['title']}: unexpected bit header")
    width = len(header) if len(tokens) == 16 else header.index(" 00 ") + 3
    rest = iter(left_column(line, width) for line in lines[starts[0] + 1:])
    line = next((line for line in rest if line.strip()), "")
    bits = {}
    if row_label:
        row = line.split()
        require(row[:1] == [row_label] and len(row) == 17, f"Stride {section['title']}: no {row_label} row")
        for bit, token in zip(range(15, -1, -1), row[1:]):
            require(re.fullmatch(r"-|\d{3}|#\d", token), f"Stride {section['title']}: bit token {token!r}")
            if token != "-":
                bits[bit] = token
        line = next((line for line in rest if line.strip()), "")
    if line.split()[:1] != ["Description"]:
        return bits, []
    descriptions = [normalized(line.replace("Description", "", 1))]
    for line in rest:
        if not line.strip():
            break
        descriptions.append(normalized(line))
    return bits, descriptions


def mirrored(coil, register, bit, what):
    index = int(coil) - 1
    require(index // 16 == int(register) - 40001 and (index % 16) ^ 8 == bit,
            f"Stride {what}: coil {coil} is not bit {bit} of register {register}")


def find(rows, label, what):
    matches = [reference for reference, (text, *_) in rows.items() if text == label]
    require(len(matches) == 1, f"Stride {what}: {len(matches)} rows labelled {label!r}")
    return matches[0]


def register_point(point_id, reference, registers, **fields):
    label, access = registers[reference]
    point = {"id": point_id, "aliases": [label], "table": "holding_register",
             "address": modicon_reference(reference, "holding_register"), **fields}
    if access != "RO":
        note = f"Vendor access {access}; read-only in this contract."
        point["description"] = f"{point['description']} {note}" if "description" in point else note
    point["source"] = {"address": reference, "page": TABLE_PAGE, "reference": "Register addresses"}
    return point


def coil_points(prefix, label, channels, coils, register, bits, what):
    points = []
    for channel in range(channels):
        reference = find(coils, f"{label} #{channel}", what)
        matches = [bit for bit, token in bits.items() if token == f"#{channel}"]
        require(len(matches) == 1, f"Stride {what}: #{channel} not in the bit diagram of {register}")
        mirrored(reference, register, matches[0], what)
        text, access, hexadecimal = coils[reference]
        point = {"id": f"{prefix}_{channel}", "aliases": [text], "table": "coil",
                 "address": modicon_reference(reference, "coil"), "type": "bool"}
        if access != "RO":
            point["description"] = f"Vendor access {access}; read-only in this contract."
        point["source"] = {"address": f"{reference} ({hexadecimal})", "page": TABLE_PAGE,
                           "reference": "Coil addresses"}
        points.append(point)
    return points


def system_flags(registers, coils, described):
    reference = find(registers, "System Flags", "system flags")
    bits, _ = diagram(described[reference], "Coil")
    flags = []
    for bit, number in sorted(bits.items()):
        matches = [coil for coil in coils if int(coil) == int(number)]
        require(len(matches) == 1, f"Stride system flags: coil {number} not in the coil table")
        mirrored(matches[0], reference, bit, "system flags")
        label = coils[matches[0]][0]
        require(label in SYSTEM_FLAGS, f"Stride system flags: unexpected coil {label!r}")
        flags.append({"bit": bit, "name": SYSTEM_FLAGS[label], "label": label})
    return [register_point("system_flags", reference, registers, type="u16", flags={"flags": flags})]


def digital(group, channels, registers, coils, described):
    if group == "di":
        register = find(registers, "Digital Inputs", "digital inputs")
        bits, _ = diagram(described[register], "Input")
        return coil_points("di", "Input", channels["in"], coils, register, bits, "digital inputs")
    if group == "do":
        register = find(registers, "Digital Outputs", "digital outputs")
        bits, _ = diagram(described[register], "Output")
        return coil_points("do", "Output", channels["out"], coils, register, bits, "digital outputs")
    points = []
    for channel in range(4):
        reference = find(registers, f"Frequency, Digital Input {channel}", "frequency")
        section = described[reference]
        require(section["title"] == f"FREQUENCY DIGITAL INPUT {channel}" and
                FREQUENCY in normalized(" ".join(section["lines"])), f"Stride frequency {channel}: description")
        points.append(register_point(f"di_frequency_{channel}", reference, registers, type="u16",
                                     conversion={"exponent10": -2}, unit="Hz"))
    return points


def thermocouple(group, channels, registers, described, pages):
    if group == "ai":
        points = []
        for channel in range(channels["in"]):
            reference = find(registers, f"Analog Input ({channel}) - Ch{channel}", "analog input")
            section = described[reference]
            body = normalized(" ".join(section["lines"]))
            require(section["title"] == f"ANALOG INPUT #{channel} VALUE" and body.startswith(ANALOG) and
                    ANALOG_EXAMPLE in body, f"Stride analog input {channel}: description")
            points.append(register_point(f"ai_{channel}", reference, registers, type="i16",
                                         conversion={"exponent10": -1}, unit="Cel"))
        return points
    if group == "input_type":
        values = {}
        for page in pages:
            for label, hexadecimal, decimal in re.findall(r"(Disabled|250mV|TC [A-Z])\s+([0-9A-F]{2})h\s+(\d+)\b",
                                                          page):
                require(int(hexadecimal, 16) == int(decimal) and values.get(label, int(decimal)) == int(decimal),
                        f"Stride input type {label}: inconsistent values")
                values[label] = int(decimal)
        require(values.keys() == INPUT_TYPES.keys(), f"Stride input type table: {sorted(values)}")
        members = sorted(values.items(), key=lambda item: item[1])
        points = []
        for pair in range(channels["in"] // 2):
            high, low = 2 * pair + 1, 2 * pair
            reference = find(registers, f"Input Type, Channels {high}–{low}", "input type")
            section = described[reference]
            require(section["title"] == f"INPUT TYPE CHANNELS {high}–{low}", f"Stride input type {low}: title")
            _, descriptions = diagram(section, None)
            order = re.findall(r"Input Type #(\d)", descriptions[0] if descriptions else "")
            require(order == [str(high), str(low)], f"Stride input type {low}: unexpected byte layout {order}")
            for channel, mask in ((low, 0x00FF), (high, 0xFF00)):
                enum = {"values": [{"value": value, "name": INPUT_TYPES[label], "label": label}
                                   for label, value in members]}
                points.append(register_point(f"input_type_{channel}", reference, registers, type="u16",
                                             mask=mask, enum=enum))
        return sorted(points, key=lambda point: int(point["id"].rsplit("_", 1)[1]))
    reference = find(registers, "Break Status", "break status")
    bits, descriptions = diagram(described[reference], "Input")
    labels = {f"#{channel}": f"Break input #{channel}" for channel in range(channels["in"])}
    require(set(bits.values()) == labels.keys() and sorted(descriptions) == sorted(labels.values()),
            "Stride break status: unexpected bit diagram")
    flags = [{"bit": bit, "name": f"break_input_{token[1:]}", "label": labels[token]}
             for bit, token in sorted(bits.items())]
    require(all(flag["bit"] == int(flag["name"].rsplit("_", 1)[1]) for flag in flags),
            "Stride break status: channel and bit disagree")
    return [register_point("break_status", reference, registers, type="u16", flags={"flags": flags})]


def firmware(registers, described):
    points = []
    for index in range(2):
        reference = find(registers, f"Firmware [{index}]", "firmware")
        section = described[reference]
        require(section["title"] == "FIRMWARE" and normalized(" ".join(section["lines"])).startswith(
            "Two read-only registers, containing the firmware version."), "Stride firmware: description")
        points.append(register_point(f"firmware_{index}", reference, registers, type="u16", stability="constant"))
    return points


def extract(data, selector):
    require(selector in MODELS, f"Unknown Stride module {selector!r}")
    subtitle, groups = MODELS[selector]
    cover, table_page, *description_pages = pdf_pages(data, 1, 6)
    require(normalized(cover).startswith(f"® Field I/O {selector} USER GUIDE {subtitle}"),
            f"Stride {selector}: cover does not name the module")
    counts = re.search(r"(\d+)-(?:point|channel) in(?:, (\d+)-point out)?$", subtitle)
    channels = {"in": int(counts.group(1)), "out": int(counts.group(2) or 0)}
    general = normalized(table_page)
    for statement in ("0xxxx and 1xxxx = Coils (bit)", "3xxxx and 4xxxx = Registers (word)",
                      "03 Read Holding Registers (4xxxx)", "01 Read Coil Status (0xxxx)"):
        require(statement in general, f"Stride {selector}: statement missing: {statement!r}")
    registers, coils = tables(table_page)
    described = sections(description_pages, 3)
    points = []
    for group in groups:
        if group == "system_flags":
            batch = system_flags(registers, coils, described)
        elif group == "firmware":
            batch = firmware(registers, described)
        elif group in ("di", "do", "frequency"):
            batch = digital(group, channels, registers, coils, described)
        else:
            batch = thermocouple(group, channels, registers, described, description_pages)
        if len(points) + len(batch) <= MAX_POINTS:
            points.extend(batch)
    return points
