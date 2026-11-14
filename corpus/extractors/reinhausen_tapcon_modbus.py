"""Maschinenfabrik Reinhausen TAPCON Modbus supplements (PDF): TAPCON 230 AVT, 250 and 260.

The selector names the supplement: "tapcon-230-avt", "tapcon-250" or "tapcon-260".
Register rows are mapped only when their scaling is the identity (multiplier or
scale 1, offset 0): the supplements do not say whether the "Multiplier"/"Scale"
column multiplies or divides the transmitted value, so scaled rows are left out.
"""
import re

from sourcelib import pdf_pages, require


def squash(value):
    return " ".join(value.split())


def dehyphenate(value):
    return re.sub(r"(\w)- (\w)", r"\1\2", squash(value))


def first_cell(line, column, tolerance=3):
    for match in re.finditer(r"\S+(?: \S+)*", line):
        if abs(match.start() - column) <= tolerance:
            return match.group()
    return None


def subsequence(needle, haystack):
    words = iter(haystack)
    return all(any(word == wanted for word in words) for wanted in needle)


def kind_for(minimum, maximum):
    require(minimum <= maximum, "Reinhausen: range minimum above maximum")
    if minimum < 0:
        require(-32768 <= minimum and maximum <= 32767, "Reinhausen: signed range exceeds 16 bits")
        return "i16"
    require(maximum <= 65535, "Reinhausen: range exceeds 16 bits")
    return "u16"


def bool_point(point_id, table, address, label, states, page, reference, description=None):
    text = description or (f"0 = {states[0]}, 1 = {states[1]}." if states else None)
    result = {"id": point_id, "table": table, "address": address, "type": "bool"}
    if text:
        result["description"] = text
    result["aliases"] = [label]
    result["source"] = {"address": str(address), "page": page, "reference": reference}
    return result


def require_selected(points, selected, model):
    missing = set(selected) - points.keys()
    require(not missing, f"{model}: missing rows {sorted(missing)}")


# --- TAPCON 230 AVT -----------------------------------------------------------------------------

AVT_INPUTS = {
    # phrase on the row line: (point id, (state 0, state 1) or None). State names are checked as
    # word subsequences of the row, because the layout interleaves the table's columns.
    "Raise Output": ("raise_output", ("inactive", "active")),
    "Lower Output": ("lower_output", ("inactive", "active")),
    "Status of Auto/Manual regulation mode": ("auto_mode", ("Manual", "Auto")),
    "Parallel Error status": ("parallel_error", ("No Error", "Error")),
    "Control mode status of AVR": ("remote_mode", ("Local", "Remote")),
    "Overvoltage detection status": ("overvoltage", ("No overvoltage", "Overvoltage")),
    "Undervoltage detection status": ("undervoltage", None),
    "Overcurrent detection status": ("overcurrent", ("No overcurrent", "Overcurrent")),
    "Undercurrent detection status": ("undercurrent", None),
    "Status of the Status Alarm Relay": ("status_alarm_relay", ("No alarm", "Alarm")),
    "Function Monitoring": ("function_monitoring", ("Normal mode", "Signal 15 min out of Bandwith")),
    "Direction of the active power flow": ("negative_power_flow", ("Positive active power flow",
                                                                   "Negative active power flow")),
}
AVT_REGISTERS = {
    # reconstructed name: point id
    "Tap Position": "tap_position",
    "Operation Counter LSW": "operation_counter",
    "Operation Counter MSW": "operation_counter_msw",
}
AVT_INPUT_ROW = re.compile(r"^\s{0,6}(\d{1,2})(?:\s{2,}(.*))?$")
AVT_REGISTER_ROW = re.compile(r"^\s{0,4}(\d{1,2})\s+(?:(\S.*?)\s+)?(-?\d+)\s+(-?\d+)\s+(\d+)\s+(-?\d+)\s+(\S+)\s+(\d+)"
                              r"(?:\s{2,}(.*))?$")


def avt_input_rows(pages, first_page):
    for page_number, page in enumerate(pages, start=first_page):
        lines = page.split("\n")
        anchors = [index for index, line in enumerate(lines)
                   if AVT_INPUT_ROW.match(line) and "Maschinenfabrik" not in line]
        for position, index in enumerate(anchors):
            start = anchors[position - 1] + 1 if position else 0
            end = anchors[position + 1] if position + 1 < len(anchors) else len(lines)
            window = lines[max(start, index - 3):min(end, index + 4)]
            yield page_number, int(AVT_INPUT_ROW.match(lines[index]).group(1)), lines[index], squash(" ".join(window))


def tapcon_230_avt(data):
    protocol = pdf_pages(data, 11, 12)
    joined = squash(" ".join(protocol))
    require("Addresses in this document refers to the MODBUS PDU addresses." in joined,
            "TAPCON 230 AVT: PDU address statement missing")
    require(re.search(r"02 Read input status 03 Read holding registers 04 Read input registers", joined),
            "TAPCON 230 AVT: function code table missing")
    inputs = pdf_pages(data, 15, 17)
    require(inputs[0].lstrip().startswith("4.2                Input Status") and
            all("Table 6            Device Data Points: Input Status" in page for page in inputs),
            "TAPCON 230 AVT: input status table header missing")
    points = {}
    addresses = []
    for page_number, address, line, window in avt_input_rows(inputs, 15):
        addresses.append(address)
        for phrase, (point_id, states) in AVT_INPUTS.items():
            if phrase not in squash(line):
                continue
            require(point_id not in points, f"TAPCON 230 AVT: duplicate input row {phrase}")
            words = window.split()
            require(all(subsequence(state.split(), words) for state in states or ()),
                    f"TAPCON 230 AVT input {address}: state names not found")
            points[point_id] = bool_point(point_id, "discrete_input", address, phrase, states, page_number,
                                          "Table 6 Device Data Points: Input Status",
                                          description=None if states else f"{phrase}.")
    require(addresses == list(range(51)), "TAPCON 230 AVT: input status rows are not 0..50")
    require_selected(points, {value[0] for value in AVT_INPUTS.values()}, "TAPCON 230 AVT")

    page = pdf_pages(data, 19)[0]
    require(page.startswith("4.4              Input Registers") and
            "Table 8          Device Datat Points: Input Registers" in page,
            "TAPCON 230 AVT: input register table header missing")
    lines = page.split("\n")
    header = next(line for line in lines if re.match(r"^\s+Name\s+Mini-", line))
    name_column = header.index("Name") - 2
    description_column = header.index("Description") - 8  # the column's text is centred under its heading
    anchors = [index for index, line in enumerate(lines) if AVT_REGISTER_ROW.match(line)]
    registers = {}
    for index in anchors:
        match = AVT_REGISTER_ROW.match(lines[index])
        names = []
        if index - 1 not in anchors:
            names.append(first_cell(lines[index - 1], name_column))
        names.append(match.group(2))
        if index + 1 not in anchors:
            names.append(first_cell(lines[index + 1], name_column))
        name = dehyphenate(" ".join(name for name in names if name))
        if name in AVT_REGISTERS:
            require(name not in registers, f"TAPCON 230 AVT: duplicate register row {name}")
            note = (cell.group() for line in lines[index - 1:index + 2]
                    for cell in re.finditer(r"\S+(?: \S+)*", line) if cell.start() >= description_column)
            registers[name] = (match, squash(" ".join(note)))
    require(registers.keys() == AVT_REGISTERS.keys(), f"TAPCON 230 AVT: missing {AVT_REGISTERS.keys() - registers}")
    for name, (match, _) in registers.items():
        multiplier, offset = int(match.group(5)), int(match.group(6))
        require((multiplier, offset, match.group(8)) == (1, 0, "1"), f"TAPCON 230 AVT {name}: scaled row selected")
    tap, low, high = (registers[name][0] for name in AVT_REGISTERS)
    tap_address, tap_min, tap_max = int(tap.group(1)), int(tap.group(3)), int(tap.group(4))
    points["tap_position"] = {
        "id": "tap_position", "table": "input_register", "address": tap_address, "type": kind_for(tap_min, tap_max),
        "description": f"Transmitted range {tap_min} to {tap_max}.",
        "aliases": ["Tap Position"],
        "source": {"address": str(tap_address), "page": 19, "reference": "Table 8 Device Data Points: Input Registers"},
    }
    low_address, high_address = int(low.group(1)), int(high.group(1))
    require(high_address == low_address + 1 and low.group(3, 4) == high.group(3, 4) == ("0", "99999999"),
            "TAPCON 230 AVT: operation counter LSW/MSW rows disagree")
    require(registers["Operation Counter LSW"][1] == registers["Operation Counter MSW"][1] ==
            "The value of Operation Counter consists of LSW and MSW", "TAPCON 230 AVT: operation counter note missing")
    require(int(low.group(4)) <= 0xFFFFFFFF, "TAPCON 230 AVT: operation counter exceeds 32 bits")
    points["operation_counter"] = {
        "id": "operation_counter", "table": "input_register", "address": low_address, "type": "u32",
        "wordOrder": "little",
        "description": "Operation counter: least significant word first, then most significant word. "
                       "Transmitted range 0 to 99999999.",
        "aliases": ["Operation Counter LSW", "Operation Counter MSW"],
        "source": {"address": f"{low_address}-{high_address}", "page": 19,
                   "reference": "Table 8 Device Data Points: Input Registers"},
    }
    return sorted(points.values(), key=lambda item: (item["table"], item["address"]))


# --- TAPCON 250 ---------------------------------------------------------------------------------

TC250_INPUTS = {
    # designation: (point id, state 0, state 1)
    "status manual/auto": ("auto_mode", "manual", "auto"),
    "operation counter circuit status": ("operation_counter_circuit_closed", "open", "closed"),
    "parallel control": ("parallel_control", "off", "on"),
    "error parallel control": ("parallel_control_error", "no error", "error"),
    "Status remote/local": ("local_mode", "remote", "local"),
    "overvoltage": ("overvoltage", "no overvoltage", "overvoltage"),
    "undervoltage": ("undervoltage", "no undervoltage", "undervoltage"),
    "overcurrent": ("overcurrent", "no overcurrent", "overcurrent"),
    "function monitoring 15 min": ("function_monitoring", "inactive", "active"),
    "auto inhibit": ("auto_inhibit", "inactive", "active"),
    "neutral position indication": ("neutral_position", "inactive", "active"),
    "power flow direction": ("reverse_power_flow", "forward", "reverse"),
    "Hunting alarm": ("hunting_alarm", "inactive", "active"),
}
TC250_ENUMS = {
    "parallel operation method": ("parallel_operation_method", {
        "off": "off", "circulating curr": "circulating_current", "master": "master", "follower": "follower",
        "auto synchron.": "auto_synchronous", "XPA": "xpa"}),
    "paralleling group": ("paralleling_group", {"off": "off", "group1": "group_1", "group2": "group_2"}),
}
TC250_INPUT_ROW = re.compile(r"^\s*(\d+)\s+N/A\s+N/A\s+(\S.*?)\s{2,}0: (\S.*?)\s{2,}02\s*$")
TC250_REGISTER_ROW = re.compile(
    r"^\s*(\d+)\s+(N/A|Volts|%)\s+(N/A|\d+)\s+(\S.*?)\s{2,}(\S.*?)\s{2,}(\d\d(?:, \d\d)?)\s*$")


def tapcon_250(data):
    coils, inputs, registers, examples = pdf_pages(data, 4, 7)
    # Section 7: the wire bytes of the examples equal the numbers used in the tables.
    coil = re.search(r":01050002FF00F9 \(.*\)\s+--> Force Single Coil request Slave 1 PtAdrs (\d+) On", examples)
    rtu = re.search(r"01 02 ([0-9A-F]{2}) ([0-9A-F]{2}) 00 0A [0-9A-F]{2} [0-9A-F]{2}\s+"
                    r"--> Read Input Status request Slave 1 Start (\d+) Count 10", examples)
    require(coil and int(coil.group(1)) == 0x0002, "TAPCON 250: Force Single Coil example changed")
    require(rtu and int(rtu.group(1) + rtu.group(2), 16) == int(rtu.group(3)) == 0,
            "TAPCON 250: Read Input Status example changed")
    require(re.search(r"^\s+2\s+N/A\s+N/A Lower\s", coils, re.MULTILINE), "TAPCON 250: coil 2 is not Lower")
    require(re.search(r"2\s+Read input status\s+3\s+Read holding registers\s+4\s+Read input registers", coils),
            "TAPCON 250: function code list missing")

    require("6.2        Input Status (1X references)" in inputs, "TAPCON 250: input status table missing")
    lines = inputs.split("\n")
    points = {}
    for index, line in enumerate(lines):
        match = TC250_INPUT_ROW.match(line)
        if not match or match.group(2) not in TC250_INPUTS:
            continue
        address, designation = int(match.group(1)), match.group(2)
        point_id, state0, state1 = TC250_INPUTS[designation]
        following = re.fullmatch(r"\s+1: (\S.*?)\s*", lines[index + 1])
        require((match.group(3), following and following.group(1)) == (state0, state1),
                f"TAPCON 250 input {address}: unexpected states")
        require(point_id not in points, f"TAPCON 250: duplicate input {designation}")
        points[point_id] = bool_point(point_id, "discrete_input", address, designation, (state0, state1), 5,
                                      "6.2 Input Status (1X references)")
    require_selected(points, {value[0] for value in TC250_INPUTS.values()}, "TAPCON 250")

    require("6.3         Input registers (3X references)" in registers and
            "6.4         Holding registers (4X references)" in registers, "TAPCON 250: register tables missing")
    input_part, holding_part = registers.split("6.4         Holding registers (4X references)")
    tap = [match for match in map(TC250_REGISTER_ROW.match, input_part.split("\n"))
           if match and match.group(4) == "tap position"]
    require(len(tap) == 1, "TAPCON 250: tap position row missing")
    address, unit, scale, _, value_range, function = tap[0].groups()
    span = re.fullmatch(r"(-?\d+)\.\.\.(-?\d+)", value_range)
    require((unit, scale, function) == ("N/A", "1", "04") and span, "TAPCON 250: tap position row changed")
    minimum, maximum = int(span.group(1)), int(span.group(2))
    points["tap_position"] = {
        "id": "tap_position", "table": "input_register", "address": int(address), "type": kind_for(minimum, maximum),
        "description": f"Range {minimum} to {maximum} ((50L...140R) in the supplement).",
        "aliases": ["tap position"],
        "source": {"address": address, "page": 6, "reference": "6.3 Input registers (3X references)"},
    }

    lines = holding_part.split("\n")
    for index, line in enumerate(lines):
        match = TC250_REGISTER_ROW.match(line)
        if not match or match.group(4) not in TC250_ENUMS:
            continue
        address, unit, scale, designation, first_value, function = match.groups()
        require((unit, scale, function) == ("N/A", "N/A", "03, 06"), f"TAPCON 250 {designation}: row changed")
        point_id, names = TC250_ENUMS[designation]
        column = line.index(first_value)
        values = [first_value]
        for extra in lines[index + 1:]:
            if TC250_REGISTER_ROW.match(extra):
                break
            fragment = first_cell(extra, column, tolerance=1)
            if not fragment or not re.match(r"\d+: ", fragment):
                break
            values.append(fragment)
        enum = []
        for expected, text in enumerate(values):
            value, name = re.fullmatch(r"(\d+): (.+)", text).groups()
            require(int(value) == expected and name in names, f"TAPCON 250 {designation}: unexpected value {text}")
            enum.append({"value": int(value), "name": names[name], "label": name})
        require(len(enum) == len(names), f"TAPCON 250 {designation}: values missing")
        points[point_id] = {
            "id": point_id, "table": "holding_register", "address": int(address), "type": "u16",
            "enum": {"values": enum},
            "description": "Read with function code 03; the device also accepts writes (06), "
                           "which this read-only contract does not describe.",
            "aliases": [designation],
            "source": {"address": address, "page": 6, "reference": "6.4 Holding registers (4X references)"},
        }
    require_selected(points, {value[0] for value in TC250_ENUMS.values()}, "TAPCON 250")
    return sorted(points.values(), key=lambda item: (item["table"], item["address"]))


# --- TAPCON 260 ---------------------------------------------------------------------------------

TC260_INPUTS = {
    "Function monitoring": "function_monitoring",
    "Undervoltage": "undervoltage",
    "Overvoltage": "overvoltage",
    "Overcurrent": "overcurrent",
    "Parallel operation error": "parallel_operation_error",
    "Auto/Manual (1 = Auto, 0 = Manual)": "auto_mode",
    "Tap-change in progress": "tap_change_in_progress",
    "Parallel operation On": "parallel_operation_on",
    "Local/remote": "local_remote",
    "Motor protective switch": "motor_protective_switch",
}
TC260_REGISTER_ROW = re.compile(r"^(\d+)\s+(\S.*?)?\s{2,}(-?[\d,]+)\s+(-?[\d,]+)\s+(\d+)\s+(-?\d+)\s+(\S+)\s+(\S+)\s*$")


def tapcon_260(data):
    protocol = squash(pdf_pages(data, 13)[0])
    require("Addresses in this document relate to the Modbus PDU addresses." in protocol,
            "TAPCON 260: PDU address statement missing")
    require(re.search(r"02 Read input status 03 Read holding registers 04 Read input registers", protocol),
            "TAPCON 260: function code table missing")
    inputs, registers = pdf_pages(data, 16, 17)
    require("5.2       Inputs (1X reference points)" in inputs
            and "Table 10       Device data points: Inputs" in inputs, "TAPCON 260: input table missing")
    table = inputs.split("Address               Description", 1)[1].split("Table 10", 1)[0]
    rows = [(int(match.group(1)), match.group(2)) for match in
            re.finditer(r"^\s+(\d+)\s{2,}(\S.*?)\s*$", table, re.MULTILINE)]
    require(rows[0] == (0, "Function monitoring"), "TAPCON 260: input table does not start at address 0")
    points = {}
    for address, description in rows:
        if description not in TC260_INPUTS:
            continue
        point_id = TC260_INPUTS[description]
        require(point_id not in points, f"TAPCON 260: duplicate input {description}")
        text = None
        if point_id == "auto_mode":
            text = "0 = Manual, 1 = Auto."
        elif point_id == "local_remote":
            text = "The supplement does not state which value means local."
        points[point_id] = bool_point(point_id, "discrete_input", address, description, None, 16,
                                      "Table 10 Device data points: Inputs", description=text)
    require_selected(points, set(TC260_INPUTS.values()), "TAPCON 260")

    require("5.4             Input register (3X reference points)" in registers
            and "Table 12        Device data points: Input register" in registers,
            "TAPCON 260: input register table missing")
    part = registers.split("5.4             Input register (3X reference points)", 1)[1]
    tap = [match for match in map(TC260_REGISTER_ROW.match, part.split("\n"))
           if match and match.group(2) == "Tap position"]
    require(len(tap) == 1, "TAPCON 260: tap position row missing")
    address, _, minimum, maximum, multiplier, offset, unit, resolution = tap[0].groups()
    require((multiplier, offset, unit, resolution) == ("1", "0", "-", "1"), "TAPCON 260: tap position row changed")
    minimum, maximum = int(minimum.replace(",", "")), int(maximum.replace(",", ""))
    points["tap_position"] = {
        "id": "tap_position", "table": "input_register", "address": int(address), "type": kind_for(minimum, maximum),
        "description": f"Transmitted range {minimum} to {maximum}.",
        "aliases": ["Tap position"],
        "source": {"address": address, "page": 17, "reference": "Table 12 Device data points: Input register"},
    }
    return sorted(points.values(), key=lambda item: (item["table"], item["address"]))


EXTRACTORS = {"tapcon-230-avt": tapcon_230_avt, "tapcon-250": tapcon_250, "tapcon-260": tapcon_260}


def extract(data, selector):
    require(selector in EXTRACTORS, f"Unknown TAPCON selector {selector!r}")
    return EXTRACTORS[selector](data)
