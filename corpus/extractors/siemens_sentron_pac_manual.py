"""Siemens SENTRON PAC power monitoring device manuals (PDF): Modbus measured variables.

The selector is the model: "pac3200", "pac4200", "pac3120" or "pac3220" (the last two share one
manual and one table). The manuals list each variable with its "Offset", number of registers, format
(Float, Unsigned long, Double), unit and access, and state that function codes 0x03 and 0x04 read
them. They state neither what "Offset" is on the wire nor the register order of multi-register
values. Each manual names the "PAC RS485 expansion module" manual as its companion for Modbus RTU,
and that manual (A5E02091800B-01, pinned as the evidence document "siemens-pac-rs485-manual") shows
exchanges captured from a PAC3200 in chapter 12.1. The extractor parses them from its bytes and
requires:

- every frame it uses is a valid RTU frame (CRC);
- the FC 0x04 request explained as "From offset 0001: voltage Va-n" carries start address 00 01, and
  the one explained as "From offset 50001" carries C3 51, so an offset is the PDU address;
- the three Float values of the first response decode to the stated 232.4, 231.4 and 231.6 only with
  the most significant word and byte first;
- the Unsigned long values of the second response fall in the documented ranges of the settings at
  those offsets (secondary voltage 1 ... 690 V, secondary current 1 A or 5 A) only in that same order;
- the device identification response names the PAC3200.

The points use the input-register table of that example; the manuals give FC 0x03 the same values.
No Siemens document shows the register order of a Double, so the energy counters in double format
are not selected; the float copies are, where a manual has them. Status bits are taken from the
"Bit mask" column of the device status table, which must agree with its byte and bit columns
(byte 0 is the most significant byte of the Unsigned long).
"""
import re
import struct

from sourcelib import pdf_page_count, pdf_pages, require

EVIDENCE = "siemens-pac-rs485-manual"
UNITS = {"V": "V", "A": "A", "W": "W", "VA": "V.A", "Hz": "Hz", "%": "%", "s": "s", "Wh": "W.h", "VAh": "V.A.h"}
NOT_UCUM = {"var", "VAR", "varh", "VARh"}
ORDERS = {("big", "big"): (0, 1, 2, 3), ("little", "big"): (2, 3, 0, 1),
          ("big", "little"): (1, 0, 3, 2), ("little", "little"): (3, 2, 1, 0)}
TARIFFS = {"Tariff 1": "tariff_1", "Tariff 2": "tariff_2"}

ROW = re.compile(r"^(\d{1,5}) (\d) (.+?) (Float|Unsigned long|Double|Unix_ts|Time stamp) ?(.*?) ?(RW|R|W)$",
                 re.IGNORECASE)
ENUM_VALUE = re.compile(r"^(\d) ?= ?(\S.*)$")
STATUS_ROW = re.compile(r"(\d) (\d) (\S.*?) ?(?:1\))? ?(?:2\))? (Status|Stored|saving) (0x[0-9A-Fa-f]{8})\b")

# Per manual: identity, the sentence that names the companion manual, the sentence that names the
# function codes, and the selected rows. Values: (section, name, format): (point id, unit as printed).
# A unit of None is the table's "-" or an empty cell. Sections are (start caption, end heading).
# "energy_heading" is a statement about the float energy values that must be present; "energy_note"
# is the description their points get.
MANUALS = {
    "pac3200": {
        "identity": ["SENTRON PAC3200", "Manual, 02/2008, A5E01168664B-04"],
        "companion": '"PAC PROFIBUS DP Expansion Module" operating instructions ● "PAC RS485 expansion module" '
                     'manual',
        "companion_heading": "1.6 Further documentation Overview You can find further details in the following "
                             "manuals:",
        "function_codes": "You can use the MODBUS function codes 0x03 and 0x04 on all the measured variables "
                          "listed below.",
        "sections": {"measured": ("Table 3-6 Available measured variables", "3.9.4 Structure")},
        "values": {
            ("measured", "Voltage Va-n", "float"): ("voltage_l1_n", "V"),
            ("measured", "Voltage Vb-n", "float"): ("voltage_l2_n", "V"),
            ("measured", "Voltage Vc-n", "float"): ("voltage_l3_n", "V"),
            ("measured", "Voltage Va-b", "float"): ("voltage_l1_l2", "V"),
            ("measured", "Voltage Vb-c", "float"): ("voltage_l2_l3", "V"),
            ("measured", "Voltage Vc-a", "float"): ("voltage_l3_l1", "V"),
            ("measured", "Current a", "float"): ("current_l1", "A"),
            ("measured", "Current b", "float"): ("current_l2", "A"),
            ("measured", "Current c", "float"): ("current_l3", "A"),
            ("measured", "THD-R Voltage a", "float"): ("voltage_thd_l1", "%"),
            ("measured", "THD-R Current a", "float"): ("current_thd_l1", "%"),
            ("measured", "Frequency", "float"): ("frequency", "Hz"),
            ("measured", "Total Apparent Power", "float"): ("apparent_power_total", "VA"),
            ("measured", "Total Active Power", "float"): ("active_power_total", "W"),
            ("measured", "Total Reactive Power", "float"): ("reactive_power_total", "var"),
            ("measured", "Total Power Factor", "float"): ("power_factor_total", None),
            ("measured", "Working hours counter", "unsigned long"): ("operating_hours_counter", "s"),
        },
        "tariff": ("measured", "Active Tariff"),
        "status": {
            "row": ("measured", "Device Diagnostics and Device Status*"),
            "caption": "Table 3-8 Modbus offset 205, tab 2: Structure device status and device diagnostics",
            "end": "1) Only these device statuses are to be acknowledged.",
            "flags": {
                ("No synchronization pulse", "Status"): "no_synchronization_pulse",
                ("Device Configuration menu is active", "Status"): "configuration_menu_active",
                ("Voltage overload", "Status"): "voltage_overload",
                ("Current overload", "Status"): "current_overload",
                ("Module slot 1", "Status"): "module_slot_1",
                ("Maximum pulse rate exceeded", "Status"): "pulse_rate_exceeded",
                ("Relevant parameter changes", "saving"): "parameters_changed_stored",
                ("Upper or lower limit violation", "saving"): "limit_violation_stored",
                ("Maximum pulse rate exceeded", "saving"): "pulse_rate_exceeded_stored",
                ("Restart of the device", "saving"): "device_restarted_stored",
                ("Resetting of energy counter by user", "saving"): "energy_counters_reset_stored",
            },
        },
    },
    "pac4200": {
        "identity": ["PAC4200", "System Manual, 05/2019, A5E02316180B-05"],
        "companion": 'You can find further details about the PAC RS485 expansion module and Modus RTU in the '
                     '"PAC RS485 Expansion Module" manual.',
        "function_codes": "A.2.1 Measured variables without a time stamp with the function codes 0x03 and 0x04 "
                          "Addressing the measured variables without a time stamp",
        "sections": {"measured": ("Table A- 1 Measured variables available without a time stamp", "A.2.2 Structure"),
                     "energy": ("Table A- 14 Available tariff-specific measured variables", "A.2.8 Maximum values")},
        "energy_heading": "A.2.7 Tariff-specific energy values in float format with the function codes 0x03 and 0x04",
        "energy_note": "Float copy of the energy value in double format (table A-12).",
        "values": {
            ("measured", "Voltage L1-N", "float"): ("voltage_l1_n", "V"),
            ("measured", "Voltage L2-N", "float"): ("voltage_l2_n", "V"),
            ("measured", "Voltage L3-N", "float"): ("voltage_l3_n", "V"),
            ("measured", "Voltage L1-L2", "float"): ("voltage_l1_l2", "V"),
            ("measured", "Current L1", "float"): ("current_l1", "A"),
            ("measured", "Current L2", "float"): ("current_l2", "A"),
            ("measured", "Current L3", "float"): ("current_l3", "A"),
            ("measured", "Neutral Current", "float"): ("current_n", "A"),
            ("measured", "Line Frequency", "float"): ("frequency", "Hz"),
            ("measured", "Total Apparent Power", "float"): ("apparent_power_total", "VA"),
            ("measured", "Total Active Power", "float"): ("active_power_total", "W"),
            ("measured", "Total Reactive Power (Qn)", "float"): ("reactive_power_total", "VAR"),
            ("measured", "Total Power Factor", "float"): ("power_factor_total", None),
            ("energy", "Active Energy Import Tariff 1", "float"): ("active_energy_import_tariff_1", "Wh"),
            ("energy", "Active Energy Export Tariff 1", "float"): ("active_energy_export_tariff_1", "Wh"),
            ("energy", "Reactive Energy Import Tariff 1", "float"): ("reactive_energy_import_tariff_1", "VARh"),
            ("energy", "Apparent Energy Tariff 1", "float"): ("apparent_energy_tariff_1", "VAh"),
        },
        "tariff": ("measured", "Active Tariff"),
        "status": {
            "row": ("measured", "PMD Diagnostics and Status*"),
            "caption": "Table A- 8 Modbus offset 205, tab 2: Structure of PMD diagnostics and status",
            "end": "1) Only these device states are to be acknowledged.",
            "flags": {
                ("No synchronization pulse", "Status"): "no_synchronization_pulse",
                ("Device Configuration menu is active", "Status"): "configuration_menu_active",
                ("Voltage out of range", "Status"): "voltage_out_of_range",
                ("Current out of range", "Status"): "current_out_of_range",
                ("Device time undefined", "Status"): "device_time_undefined",
                ("Hardware write protection is active", "Status"): "hardware_write_protection",
                ("Module slot 1", "Status"): "module_slot_1",
                ("Maximum pulse rate exceeded", "Status"): "pulse_rate_exceeded",
                ("Module slot 2", "Status"): "module_slot_2",
                ("Process counter active", "Status"): "process_counter_active",
                ("Basic configuration changed", "saving"): "configuration_changed_stored",
                ("Upper or lower limit violation", "saving"): "limit_violation_stored",
                ("Maximum pulse rate exceeded", "saving"): "pulse_rate_exceeded_stored",
                ("Device has rebooted", "saving"): "device_restarted_stored",
                ("Energy counters reset", "saving"): "energy_counters_reset_stored",
                ("Power quality", "saving"): "power_quality_stored",
                ("Bit 0 Slot 1 Parameters changed", "saving"): "slot_1_parameters_changed",
                ("Bit 1 Slot 1 IMDATA changed", "saving"): "slot_1_im_data_changed",
                ("Bit 2 Slot 1 Firmware update active", "saving"): "slot_1_firmware_update_active",
                ("Bit 3 Firmware data block available", "saving"): "firmware_data_block_available",
                ("Bit 4 Bootloader update flag", "saving"): "bootloader_update_flag",
                ("Bit 5 Slot 2 Firmware update active", "saving"): "slot_2_firmware_update_active",
                ("Bit 6 Slot 2 Parameters changed", "saving"): "slot_2_parameters_changed",
                ("Bit 7 Slot 2 IMDATA changed", "saving"): "slot_2_im_data_changed",
            },
        },
    },
    "pac3120-pac3220": {
        "identity": ["PAC3120 and PAC3220", "Equipment Manual, 07/2024, L1V30425208F_RS-AA_002"],
        "companion": "PAC3220 with RS485 expansion module You can find information about setting parameters for the "
                     "RS485 interface in the documentation for the SENTRON PAC RS485 expansion module "
                     "(https://support.industry.siemens.com/cs/ww/en/view/28865965)",
        "function_codes": "You can use the Modbus function codes 0x03 and 0x04 on all the measured variables listed "
                          "below.",
        "sections": {"measured": ("Available measured variables", "A.1.4 Structure")},
        "energy_heading": 'The "float" energy values listed in the table below should only be used for display '
                          'purposes. For calculations, it is recommended to use "double" energy values, as these '
                          'offer a higher resolution.',
        "energy_note": "Float copy of the energy counter in double format; the manual recommends the float values "
                       "for display purposes only.",
        "values": {
            ("measured", "Voltage L1-N", "float"): ("voltage_l1_n", "V"),
            ("measured", "Voltage L2-N", "float"): ("voltage_l2_n", "V"),
            ("measured", "Voltage L3-N", "float"): ("voltage_l3_n", "V"),
            ("measured", "Voltage L1-L2", "float"): ("voltage_l1_l2", "V"),
            ("measured", "Current L1", "float"): ("current_l1", "A"),
            ("measured", "Current L2", "float"): ("current_l2", "A"),
            ("measured", "Current L3", "float"): ("current_l3", "A"),
            ("measured", "Current N", "float"): ("current_n", "A"),
            ("measured", "Frequency", "float"): ("frequency", "Hz"),
            ("measured", "Total apparent power", "float"): ("apparent_power_total", "VA"),
            ("measured", "Total active power", "float"): ("active_power_total", "W"),
            ("measured", "Total reactive power", "float"): ("reactive_power_total", "var"),
            ("measured", "Total power factor", "float"): ("power_factor_total", None),
            ("measured", "Operating hours counter", "unsigned long"): ("operating_hours_counter", "s"),
            ("measured", "Total active energy - import tariff 1", "float"): ("active_energy_import_tariff_1", "Wh"),
            ("measured", "Total active energy - export tariff 1", "float"): ("active_energy_export_tariff_1", "Wh"),
            ("measured", "Total apparent energy - tariff 1", "float"): ("apparent_energy_tariff_1", "VAh"),
        },
        "tariff": ("measured", "Active tariff"),
        "status": {
            "row": ("measured", "PMD diagnostics and status"),
            "caption": "Table A-6 Modbus offset 205, register 2: Structure device status and device diagnostics",
            "end": "Only these device states must be acknowledged.",
            "flags": {
                ("No synchronization pulse", "Status"): "no_synchronization_pulse",
                ("Device configuration menu is active", "Status"): "configuration_menu_active",
                ("Voltage overload", "Status"): "voltage_overload",
                ("Current overload", "Status"): "current_overload",
                ("Maximum pulse rate exceeded", "Status"): "pulse_rate_exceeded",
                ("Relevant parameter changes", "Stored"): "parameters_changed_stored",
                ("Maximum pulse rate exceeded", "Stored"): "pulse_rate_exceeded_stored",
                ("Restart of the device", "Stored"): "device_restarted_stored",
                ("Resetting of energy counters by user", "Stored"): "energy_counters_reset_stored",
            },
        },
    },
}
MODELS = {"pac3200": "pac3200", "pac4200": "pac4200", "pac3120": "pac3120-pac3220", "pac3220": "pac3120-pac3220"}


def clean(text):
    """One spelling for the hyphens, dashes and ellipses the manuals mix; single spaces."""
    for code in (0x2010, 0x2011, 0x2012, 0x2013):  # hyphen, non-breaking hyphen, figure dash, en dash
        text = text.replace(chr(code), "-")
    return " ".join(text.replace(chr(0x2026), "...").split())


def squeeze(text):
    return re.sub(r"\s+", "", clean(text))


def crc16(frame):
    """Modbus RTU CRC; the frame carries the low byte first."""
    crc = 0xFFFF
    for byte in frame:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, crc >> 8])


def captured(rows, caption):
    """The frame printed under a table caption and the explanation lines below it.

    The first row ends with the CRC; further rows continue the data column. Returns the frame
    without CRC, after checking the CRC. A response prints its byte count in decimal in one table
    (32 for 0x20); the count is taken from the data length, which the CRC confirms.
    """
    starts = [index for index, row in enumerate(rows) if squeeze(row) == squeeze(caption)]
    require(len(starts) == 1, f"PAC RS485 manual: caption {caption!r} found {len(starts)} times")
    index = starts[0] + 1
    while index < min(len(rows), starts[0] + 4) and not re.fullmatch(r"[0-9A-F]{2}( [0-9A-F]{2})*", rows[index]):
        index += 1  # column header
    hex_rows = []
    while index < len(rows) and re.fullmatch(r"[0-9A-F]{2}( [0-9A-F]{2})*", rows[index]):
        hex_rows.append(rows[index].split())
        index += 1
    require(hex_rows and len(hex_rows[0]) >= 5, f"PAC RS485 manual: no frame under {caption!r}")
    explanation = []
    if index < len(rows) and rows[index] == "Explanation:":
        index += 1
        while index < len(rows) and not rows[index].startswith(("Table 12-", "PAC RS485", "Reading a", "Execute")):
            explanation.append(rows[index])
            index += 1
    tokens = hex_rows[0][:-2] + [token for row in hex_rows[1:] for token in row]
    frame = bytes(int(token, 16) for token in tokens)
    crc = bytes(int(token, 16) for token in hex_rows[0][-2:])
    if crc16(frame) != crc and frame[1] in (3, 4) and len(frame) > 3:
        counted = frame[:2] + bytes([len(frame) - 3]) + frame[3:]
        require(tokens[2] == str(len(frame) - 3) and crc16(counted) == crc,
                f"PAC RS485 manual: frame under {caption!r} fails its CRC")
        frame = counted
    require(crc16(frame) == crc, f"PAC RS485 manual: frame under {caption!r} fails its CRC")
    return frame, " ".join(explanation)


def ordered(data, order):
    return bytes(data[index] for index in ORDERS[order])


def check_rs485_manual(data):
    """Check the conventions against the worked exchanges in the PAC RS485 expansion module manual.

    Returns the offset of the Float example (the L1-N voltage).
    """
    pages = pdf_pages(data, 1, pdf_page_count(data))
    rows = [clean(line) for page in pages for line in page.splitlines() if line.strip()]
    text = squeeze(" ".join(rows))
    for marker in ("PAC RS485 Manual, 02/2008, A5E02091800B-01", "12.1 Examples of MODBUS communication",
                   "The PAC RS485 expansion module is designed for use with a SENTRON PAC Power Monitoring Device."):
        require(squeeze(marker) in text, f"PAC RS485 manual: {marker!r} not found")
    require(squeeze("application examples from the \"Application Log-File\" of the bus master. The values are "
                    "specified in hexadecimal form.") in text, "PAC RS485 manual: origin of the examples not stated")

    # Float: "From offset 0001: voltage Va-n".
    request, explanation = captured(rows, "Table 12-1 Request of the master")
    match = re.fullmatch(r"From offset (\d+): voltage Va-n", explanation)
    require(match and len(request) == 6 and request[1] == 4, "PAC RS485 manual: table 12-1 is not the FC 04 example")
    offset, registers = int(match.group(1)), request[4] << 8 | request[5]
    require(request[2] << 8 | request[3] == offset, "PAC RS485 manual: table 12-1 start address is not the offset")
    response, explanation = captured(rows, "Table 12-2 Response - confirmation of the slave")
    stated = explanation.split()
    require(response[:2] == request[:2] and response[2] == 2 * registers == len(response) - 3
            and stated[0] == str(response[2]) and len(stated) == 1 + registers // 2,
            "PAC RS485 manual: table 12-2 does not answer table 12-1")
    fits = [order for order in ORDERS
            if [f"{struct.unpack('>f', ordered(response[3 + i:7 + i], order))[0]:.1f}"
                for i in range(0, response[2], 4)] == stated[1:]]
    require(fits == [("big", "big")], f"PAC RS485 manual: Float example fits the orders {fits}")

    # Unsigned long: "From offset 50001", answered with the settings from that offset on.
    request, explanation = captured(rows, "Table 12-3 Requirement")
    match = re.fullmatch(r"From offset (\d+): Read (\d+) registers connection type", explanation)
    require(match and len(request) == 6 and request[1] == 4, "PAC RS485 manual: table 12-3 is not the FC 04 example")
    base, registers = int(match.group(1)), int(match.group(2))
    require(request[2] << 8 | request[3] == base and request[4] << 8 | request[5] == registers,
            "PAC RS485 manual: table 12-3 start address or count is not the stated one")
    response, _ = captured(rows, "Table 12-4 Response - confirmation of the slave")
    require(response[:2] == request[:2] and response[2] == 2 * registers == len(response) - 3,
            "PAC RS485 manual: table 12-4 does not answer table 12-3")
    limits = {}
    for row in rows:
        setting = re.fullmatch(r"(\d{5}) 2 Secondary (voltage|current) - unsigned long (.+) RW", row)
        if setting:
            require(setting.group(2) not in limits, "PAC RS485 manual: secondary setting listed twice")
            limits[setting.group(2)] = (int(setting.group(1)), setting.group(3))
    require(limits.keys() == {"voltage", "current"}, "PAC RS485 manual: secondary voltage/current settings missing")
    span = re.fullmatch(r"(\d+) \.\.\. (\d+) V", limits["voltage"][1])
    require(span and limits["current"][1] == "1 A, 5 A", "PAC RS485 manual: unexpected secondary value ranges")

    def setting_value(name, order):
        position = 3 + 2 * (limits[name][0] - base)
        require(3 <= position <= len(response) - 4, f"PAC RS485 manual: secondary {name} outside the example")
        return int.from_bytes(ordered(response[position:position + 4], order), "big")

    fits = [order for order in ORDERS
            if int(span.group(1)) <= setting_value("voltage", order) <= int(span.group(2))
            and setting_value("current", order) in (1, 5)]
    require(fits == [("big", "big")], f"PAC RS485 manual: Unsigned long example fits the orders {fits}")

    identification, _ = captured(rows, "Table 12-10 Response - confirmation of the slave")
    require(identification[1] == 0x2B and b"SIEMENS AG" in identification and b"PAC3200" in identification,
            "PAC RS485 manual: the examples do not identify a PAC3200")
    # Its own measured-variable table lists the example's quantity at the example's offset.
    require(f"{offset} 2 Voltage Va-n Float V - R" in rows,
            "PAC RS485 manual: the offset of the Float example is not Voltage Va-n in its measured variables")
    return offset


def unit_of(rest):
    """Unit cell of a row: None for '-' or an empty cell (the value range may follow)."""
    tokens = rest.split()
    return None if not tokens or tokens[0] == "-" else tokens[0].rstrip(",")


def status_flags(section, spec, page):
    """Flags from the device status table; the bit mask must agree with the byte and bit columns."""
    flat = " ".join(section)
    flags, seen = [], set()
    for byte, bit, label, kind, mask in STATUS_ROW.findall(flat):
        position = 8 * (3 - int(byte)) + int(bit)
        require(int(mask, 16) == 1 << position,
                f"SENTRON PAC status {label!r}: mask {mask} is not byte {byte} bit {bit}")
        key = (label, kind)
        require(key in spec["flags"] and key not in seen, f"SENTRON PAC status: unexpected row {key} on page {page}")
        seen.add(key)
        flags.append({"bit": position, "name": spec["flags"][key], "label": label,
                      "description": f"Byte {byte}, bit {bit}, mask {mask}; type {kind}."})
    require(seen == spec["flags"].keys(), f"SENTRON PAC status: rows not found {sorted(spec['flags'].keys() - seen)}")
    return sorted(flags, key=lambda flag: flag["bit"])


def extract(data, selector, evidence=None):
    require(selector in MODELS, f"Unknown SENTRON PAC selector {selector!r}")
    require(evidence and EVIDENCE in evidence, f"SENTRON PAC: evidence document {EVIDENCE} missing")
    example_offset = check_rs485_manual(evidence[EVIDENCE])
    manual = MODELS[selector]
    spec = MANUALS[manual]
    pages = pdf_pages(data, 1, pdf_page_count(data))
    text = squeeze(" ".join(pages))
    for marker in (*spec["identity"], spec["companion"], spec.get("companion_heading", ""), spec["function_codes"],
                   spec.get("energy_heading", "")):
        require(squeeze(marker) in text, f"SENTRON PAC {manual}: {marker!r} not found")

    starts = {squeeze(start): name for name, (start, _) in spec["sections"].items()}
    status = spec["status"]
    points, found, section, opened = [], set(), None, set()
    tariff, tariff_values = None, {}
    status_point, status_section, status_page, in_status = None, [], None, False
    for number, page in enumerate(pages, start=1):
        for line in page.splitlines():
            row = clean(line)
            if not row:
                continue
            if squeeze(row) == squeeze(status["caption"]):
                require(status_page is None, f"SENTRON PAC {manual}: status table caption found twice")
                in_status, status_page = True, number
                continue
            if in_status:
                if squeeze(status["end"]) in squeeze(row):
                    in_status = False
                else:
                    require(number == status_page, f"SENTRON PAC {manual}: status table runs over a page break")
                    status_section.append(row)
                continue
            if squeeze(row) in starts:
                section = starts[squeeze(row)]
                require(section not in opened, f"SENTRON PAC {manual}: section {section} starts twice")
                opened.add(section)
                continue
            if section is None:
                continue
            if row.startswith(spec["sections"][section][1]):
                section = None
                continue
            match = ROW.match(row)
            if not match:
                value = ENUM_VALUE.match(row)
                if tariff is not None and "enum" not in tariff and value:
                    tariff_values[int(value.group(1))] = value.group(2)
                continue
            offset, registers, name, kind, rest, access = match.groups()
            kind = kind.lower()
            if tariff is not None and "enum" not in tariff:
                require(tariff_values.keys() == {0, 1} and set(tariff_values.values()) == TARIFFS.keys(),
                        f"SENTRON PAC {manual}: unexpected tariff values {tariff_values}")
                tariff["enum"] = {"values": [{"value": value, "name": TARIFFS[label], "label": label}
                                             for value, label in sorted(tariff_values.items())]}
                tariff["source"] = tariff.pop("source")
            source = {"address": offset, "page": number,
                      "reference": f"{spec['sections'][section][0]}: {name.rstrip('* ')}"}
            if (section, name) == spec["tariff"]:
                require(tariff is None and (kind, registers, access) == ("unsigned long", "2", "R")
                        and unit_of(rest) is None, f"SENTRON PAC {manual}: unexpected active tariff row {row!r}")
                first = ENUM_VALUE.match(rest[1:].strip())
                require(first, f"SENTRON PAC {manual}: active tariff row has no first value")
                tariff_values[int(first.group(1))] = first.group(2)
                tariff = {"id": "active_tariff", "address": int(offset), "type": "u32", "aliases": [name],
                          "source": source}
                points.append(tariff)
                continue
            if (section, name.rstrip("* ")) == (status["row"][0], status["row"][1].rstrip("* ")):
                require(status_point is None and (kind, registers, access) == ("unsigned long", "2", "R"),
                        f"SENTRON PAC {manual}: unexpected device status row {row!r}")
                status_point = {"id": "device_status", "address": int(offset), "type": "u32",
                                "aliases": [name.rstrip("*")], "source": source}
                points.append(status_point)
                continue
            key = (section, name, kind)
            if key not in spec["values"]:
                continue
            point_id, expected_unit = spec["values"][key]
            require(key not in found, f"SENTRON PAC {manual}: {name} listed twice")
            found.add(key)
            unit = unit_of(rest)
            require(registers == "2" and access in ("R", "RW") and unit == expected_unit,
                    f"SENTRON PAC {manual}: {name}: {registers} registers, unit {unit}, access {access}")
            point = {"id": point_id, "address": int(offset), "type": "f32" if kind == "float" else "u32"}
            if unit in UNITS:
                point["unit"] = UNITS[unit]
            point["aliases"] = [name]
            notes = [spec["energy_note"]] if "_energy_" in point_id else []
            if unit in NOT_UCUM:
                notes.append(f"Vendor unit: {unit}.")
            if notes:
                point["description"] = " ".join(notes)
            point["source"] = source
            points.append(point)

    require(opened == spec["sections"].keys() and section is None and not in_status,
            f"SENTRON PAC {manual}: a table section was not found or not closed")
    require(found == spec["values"].keys(),
            f"SENTRON PAC {manual}: rows not found {sorted(spec['values'].keys() - found)}")
    require(tariff is not None and "enum" in tariff, f"SENTRON PAC {manual}: active tariff row or values missing")
    require(status_point is not None and status_section, f"SENTRON PAC {manual}: device status row or table missing")
    require(f"Modbus offset {status_point['address']}," in status["caption"],
            f"SENTRON PAC {manual}: the device status table is not the one for offset {status_point['address']}")
    status_point["flags"] = {"flags": status_flags(status_section, status, status_page)}
    status_point["description"] = f"Bits as listed in the device status table on page {status_page}."
    status_point["source"] = status_point.pop("source")

    by_id = {point["id"]: point for point in points}
    require(len(by_id) == len(points), f"SENTRON PAC {manual}: duplicate point")
    first = by_id["voltage_l1_n"]
    require(first["address"] == example_offset and first["type"] == "f32",
            f"SENTRON PAC {manual}: the L1-N voltage is not the Float at the offset of the worked example")
    return sorted(points, key=lambda point: point["address"])
