"""ABB B21 and B23/B24 user manuals (PDF): chapter 9.3 Modbus mapping tables.

The selector is the model: "b21", "b23" or "b24". B23 and B24 share one manual.
Addresses come from the "Start Reg (Hex)" column, which the manual states is
sent on the bus as is. Unused quantities read as the documented "invalid" value.
"""
from decimal import Decimal
import re

from sourcelib import pdf_page_count, pdf_pages, require

DOCUMENTS = {
    "b21": ("B21", "2CMC485004M0201"),
    "b23": ("B23/B24", "2CMC485003M0201"),
    "b24": ("B23/B24", "2CMC485003M0201"),
}
SECTIONS = ("Total energy", "Energy accumulators divided into tariffs", "Energy accumulators per phase",
            "Resettable energy accumulators", "Instantaneous values", "Inputs and", "Production data",
            "Miscellaneous", "Settings", "Operations", "DMTME")
# (section, quantity, details) -> (point id, resolution, vendor unit, UCUM unit or None)
MEASUREMENTS = {
    ("Total energy", "Active import", "kWh"): ("active_import_energy", "0.01", "kWh", "kW.h"),
    ("Total energy", "Active export", "kWh"): ("active_export_energy", "0.01", "kWh", "kW.h"),
    ("Total energy", "Active net", "kWh"): ("active_net_energy", "0.01", "kWh", "kW.h"),
    ("Instantaneous values", "Voltage", "L1-N"): ("voltage_l1_n", "0.1", "V", "V"),
    ("Instantaneous values", "Current", "L1"): ("current_l1", "0.01", "A", "A"),
    ("Instantaneous values", "Active power", "Total"): ("active_power_total", "0.01", "W", "W"),
    ("Instantaneous values", "Reactive power", "Total"): ("reactive_power_total", "0.01", "var", None),
    ("Instantaneous values", "Frequency", None): ("frequency", "0.01", "Hz", "Hz"),
    ("Instantaneous values", "Power factor", "Total"): ("power_factor_total", "0.001", "-", None),
    ("Instantaneous values", "Phase angle power", "Total"): ("phase_angle_power_total", "0.1", "°", "deg"),
    ("Production data", "Serial number", None): ("serial_number", None, None, None),
}
THREE_PHASE = {
    ("Instantaneous values", "Voltage", "L2-N"): ("voltage_l2_n", "0.1", "V", "V"),
    ("Instantaneous values", "Voltage", "L3-N"): ("voltage_l3_n", "0.1", "V", "V"),
    ("Instantaneous values", "Current", "L2"): ("current_l2", "0.01", "A", "A"),
    ("Instantaneous values", "Current", "L3"): ("current_l3", "0.01", "A", "A"),
}
STRINGS = {
    ("Production data", "Meter firmware version", None): ("firmware_version", "ASCII string (up to 16"),
    ("Production data", "Type designation", None): ("type_designation", "ASCII string (12 characters,"),
}
TYPES = {("Unsigned", 1): "u16", ("Signed", 1): "i16", ("Unsigned", 2): "u32", ("Signed", 2): "i32",
         ("Unsigned", 4): "u64", ("Signed", 4): "i64"}
HEX_ROW = re.compile(r"[0-9A-F]{4}")


def normalized(text):
    return " ".join(text.replace("“", '"').replace("”", '"').split())


def require_text(text, pattern, message):
    require(re.search(pattern, normalized(text)), message)


def mapping_rows(pages):
    """Yield (section, tokens, next_line, page) for every register row of chapter 9.3."""
    start = [number for number, page in pages if re.search(r"^9\.3 Mapping Tables$", page, re.MULTILINE)]
    end = [number for number, page in pages if re.search(r"^9\.4 ", page, re.MULTILINE)]
    require(len(start) == 1 and len(end) == 1 and start[0] < end[0], "ABB chapter 9.3 boundaries not found")
    section = None
    for number, page in pages:
        if not start[0] <= number <= end[0]:
            continue
        lines = page.splitlines()
        for index, line in enumerate(lines):
            if number == end[0] and re.match(r"9\.4 ", line):
                return
            heading = [name for name in SECTIONS if re.match(re.escape(name) + r"(\s|$)", line)]
            if heading:
                section = heading[0]
                continue
            tokens = re.split(r"\s{2,}", line.strip())
            for position in range(1, len(tokens) - 1):
                if HEX_ROW.fullmatch(tokens[position]) and re.fullmatch(r"\d", tokens[position + 1]):
                    following = lines[index + 1].strip() if index + 1 < len(lines) else ""
                    yield section, tokens[:position], tokens[position:], following, number
                    break


def resolution(words):
    if words and re.fullmatch(r"\d+,\d+", words[0]):
        return Decimal(words[0].replace(",", ".")), words[1:]
    return None, words


def exponent(value):
    sign, digits, power = value.normalize().as_tuple()
    require(sign == 0 and digits == (1,), f"ABB resolution {value} is not a power of ten")
    return power


def invalid_value(kind, width):
    bits = 16 * width
    return (1 << (bits - 1)) - 1 if kind.startswith("i") else (1 << bits) - 1


def extract(data, selector):
    require(selector in DOCUMENTS, f"Unknown ABB selector {selector!r}")
    title, document_id = DOCUMENTS[selector]
    count = pdf_page_count(data)
    pages = list(enumerate(pdf_pages(data, 1, count), start=1))
    require_text("\n".join(page for _, page in pages[:3]),
                 re.escape(f"{title} User Manual Document ID: {document_id} Revision: A"),
                 f"ABB {title} manual title page not found")
    chapter = "\n".join(page for _, page in pages)
    require_text(chapter, r"It is expressed exactly as it is sent on the bus\. That is, it should not be "
                          r"subtracted by 40 000 or decremented by 1", "ABB address notation statement missing")
    require_text(chapter, r"the most significant (\w+ )?byte is found in the high byte of the first \(lowest\) "
                          r"register\. The least significant (\w+ )?byte is found in the low byte of the last "
                          r"\(highest\) register", "ABB multi-register order statement missing")
    require_text(chapter, r'data type "unsigned", the value will be FFFF in all registers\. (\w+ )?For quantities '
                          r'with data type "signed", the value is the highest value possible to express',
                 "ABB invalid-value statement missing")
    require_text(chapter, r"In the Modbus mapping version register the high byte corresponds to the Major "
                          r"version \(1.255\), and the low byte corresponds to the Minor version \(0.255\)",
                 "ABB mapping version byte layout missing")

    readable = re.search(r"The readable range in the modbus mapping are registers ([0-9A-F]{4})[-\u2013]([0-9A-F]{4}) "
                         r"(\w+ )?\(hexadecimal\)\. Reading any registers within this range will result in a normal "
                         r"Modbus response\.", normalized(chapter))
    require(readable, "ABB readable range statement missing")
    first, last = (int(value, 16) for value in readable.group(1, 2))
    require(first < last, "ABB readable range is empty")
    constraints = {"ranges": [{
        "table": "holding_register", "start": first, "count": last - first + 1, "policy": "safe_gap",
        "reason": f"Manual 9.2: reading any register in {readable.group(1)}-{readable.group(2)} (hex) returns a "
                  "normal response; quantities the meter lacks read as invalid.",
    }]}

    rows = {}
    for section, head, tail, following, page in mapping_rows(pages):
        quantity = head[0]
        details = head[1] if len(head) > 1 else None
        require(len(head) <= 2, f"ABB row with unexpected columns: {head + tail}")
        rows.setdefault((section, quantity, details), []).append((tail, following, page))

    def row(key):
        found = rows.get(key, [])
        require(len(found) == 1, f"ABB {key}: {len(found)} rows")
        return found[0]

    selected = dict(MEASUREMENTS)
    if selector != "b21":
        selected.update(THREE_PHASE)
    points = []
    for key, (point_id, expected_res, expected_unit, unit) in selected.items():
        tail, _, page = row(key)
        start, size = int(tail[0], 16), int(tail[1])
        res, words = resolution(" ".join(tail[2:]).split())
        kind = TYPES.get((words[-1], size))
        require(kind is not None, f"ABB {point_id}: unexpected data type {words[-1]!r} for size {size}")
        if expected_res is None:
            require(res is None and words == ["Unsigned"], f"ABB {point_id}: unexpected columns {tail}")
        else:
            require(res == Decimal(expected_res) and words[0] == expected_unit,
                    f"ABB {point_id}: unexpected resolution or unit {tail}")
        point = {"id": point_id, "address": start, "type": kind}
        if res is not None:
            point["conversion"] = {"exponent10": exponent(res)}
        if unit:
            point["unit"] = unit
        elif expected_unit not in (None, "-"):
            point["description"] = f"Vendor unit: {expected_unit}"
        point["invalid"] = [invalid_value(kind, size)]
        point["aliases"] = [" ".join(part for part in key[1:] if part)]
        point["source"] = {"address": tail[0], "page": page, "reference": f"{key[0]} table"}
        points.append(point)

    for key, (point_id, data_type) in STRINGS.items():
        tail, _, page = row(key)
        require(" ".join(tail[2:]) == data_type, f"ABB {point_id}: unexpected data type {tail}")
        points.append({
            "id": point_id, "address": int(tail[0], 16), "type": "string", "registers": int(tail[1]),
            "stability": "constant", "aliases": [key[1]],
            "source": {"address": tail[0], "page": page, "reference": f"{key[0]} table"},
        })

    tail, _, page = row(("Production data", "Modbus mapping version", None))
    require(tail[1:] == ["1", "2 bytes"], f"ABB mapping version: unexpected columns {tail}")
    for point_id, mask in (("mapping_version_major", 0xFF00), ("mapping_version_minor", 0x00FF)):
        points.append({
            "id": point_id, "address": int(tail[0], 16), "type": "u16", "mask": mask, "stability": "constant",
            "aliases": ["Modbus mapping version"],
            "source": {"address": tail[0], "page": page, "reference": "Production data table"},
        })

    led = [key for key in rows if key[0] == "Settings" and key[1].startswith("LED source")]
    require(len(led) == 1, "ABB LED source row missing")
    tail, following, page = row(led[0])
    continuation = re.split(r"\s{2,}", following)[0]
    label = f"{led[0][1]} {continuation}"
    match = re.fullmatch(r"LED source \((\d) = ([a-z ]+), (\d) = ([a-z ]+)\)", label)
    require(match and tail[1:] == ["1", "-", "Unsigned"], f"ABB LED source: unexpected row {label!r} {tail}")
    values = [{"value": int(match.group(i)), "name": match.group(i + 1).replace(" ", "_"),
               "label": match.group(i + 1)} for i in (1, 3)]
    points.append({
        "id": "led_source", "address": int(tail[0], 16), "type": "u16", "enum": {"values": values},
        "aliases": ["LED source"],
        "description": "Setting; the manual lists it as read and write. Exposed here read-only.",
        "source": {"address": tail[0], "page": page, "reference": "Settings table"},
    })
    points.sort(key=lambda point: (point["address"], -point.get("mask", 0)))
    return {"points": points, "constraints": constraints}
