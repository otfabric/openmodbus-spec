"""Janitza UMG 96RM family Modbus address lists (PDF): selected measurements.

Selectors: "umg96rm" and "umg96rm-pn" read the German address list for the UMG 96RM base device
with its PN, P and CBM extensions (Dok. Nr. 1.040.033.u, from firmware 1.14); "umg96rm-e" reads
the English UMG 96RM-E list (Dok. Nr. 1.040.085.8.o, from firmware 3.01 / hardware 104). The German
list marks the short-format tables as not readable through the PROFINET module of the UMG 96RM-PN
and readable over RS-485, so the RS-485 selection is the same for both German selectors.

Rows are selected by section and by the vendor label and index columns. Section headings are the
entries of the document's table of contents; for the German list only the base-device part, before
the first "Erweiterung" chapter, is read. The documents state that the listed addresses return
big-endian data (section "Byte sequence"), that "short" is a signed 16-bit and "float" an IEEE 754
32-bit number (section "Number formats"), that 16-bit "short" values do not include the transformer
ratios, and that the device answers, as a slave, FC 03 Read Holding Registers, FC 04 Read Input
Registers and the holding-register writes FC 06 and FC 16 (section "Modbus functions (slave)"); all
of these are required. The documents state neither the address base nor which register table the
list addresses. Both are inferred: the parameter table starts at address 0 (device address), so the
addresses are zero-based, and writable (FC 06/16) and read-only rows share the one list, so it is
the holding-register table.
"""
import re

from sourcelib import pdf_page_count, pdf_pages, require

DOCUMENTS = {
    "de": {
        "identity": [r"Dok\. Nr\. 1\.040\.033\.u", r"\(ab Firmware Rel\. 1\.14\)"],
        "big_endian": r"Die in dieser Adressenliste beschrieben Adressen liefern die Daten im Format\s+"
                      r"„Big-Endian“ zurück\.",
        "address_zero": r"^\s*0\s+SHORT\s+RD/WR\s+-\s+Geräteadresse\s",
        "short_unscaled": r"Die Messwerte im Short-Format enthalten keine Strom- und Spannungswandlerverhältnisse\.",
        "tariff_zero": r"Tarif 0 ist immer aktiv",
        "pn_rs485": r"Diese Messwerte \(Adressbereich (\d+)-(\d+) und \d+-\d+\) können nicht über das Profinet-Modul "
                    r"des\s+UMG 96RM-PN ausgelesen werden\. Das Auslesen dieser Messwerte über die Schnittstelle "
                    r"RS485 wird unterstützt\.",
        "sections": {"Häufig benötigte Messwerte": "frequent", "Messwerte, Typ Float": "float",
                     "Messwerte, Typ Short": "short", "Energie, Typ Float": "energy"},
        "header": r"^Adresse\s+Format\s+RD/WR\s+Einheit\s+Bemerkung\s+Index",
        "end": "Erweiterung",
        "slave": r"Modbus-Funktionen \(Slave\)\s+Das UMG 96RM unterstützt als Slave folgende Modbus-Funktionen:",
    },
    "en": {
        "identity": [r"Dok\. Nr\. 1\.040\.085\.8\.o", r"from firmware version 3\.01/ hardware release 104"],
        "big_endian": r"The addresses described in this address list supply the data in the „Big-Endian“ format\.",
        "address_zero": r"^\s*0\s+SHORT\s+RD/WR\s+-\s+Device adress\s",
        "short_unscaled": r"Measured values in the short format do not take into account the set transformer ratio",
        "tariff_zero": r"Tariff 0 is always active",
        "pn_rs485": None,
        "sections": {"Frequently required readings": "frequent", "Measured values, type float": "float",
                     "Measured values, type short": "short", "Energy, type float": "energy"},
        "header": r"^Address\s+Format\s+RD/WR\s+Unit\s+Note\s+Index",
        "end": None,
        "slave": r"Modbus functions \(slave\)\s+As a slave, the UMG 96RM-E supports the following modbus functions:",
    },
}
SELECTORS = {"umg96rm": "de", "umg96rm-pn": "de", "umg96rm-e": "en"}
# The slave function list, in document order, up to the next section.
FUNCTIONS = [r"03 Read Holding Registers\s+Reads the binary contents of holding registers \(4X references\) "
             r"in the slave\.",
             r"04 Read Input Registers\s+Reads the binary contents of input registers \(3X references\) "
             r"in the slave\.",
             r"06 Preset Single Register\s+Presets a value into a single holding register \(4X reference\)\.",
             r"16 \(10Hex\) Preset Multiple Registers\s+Presets values into a sequence of holding registers "
             r"\(4X references\)\."]
NUMBER_FORMATS = [r"^short\s+16 bit\s+-215\s+215 -1$", r"^float\s+32 bit\s+IEEE 754\s+IEEE 754$"]
TOC_LINE = re.compile(r"^\s{0,6}(\S.*?\S)\s{2,}\d{1,3}$")
ROW = re.compile(r"^\s*(\d{1,5})\s+([A-Z][A-Z0-9_]*)\s+(RD|RD/WR)\s+(\S+)\s+(.*?)"
                 r"(?:\s+\[(\d)\])?(?:\s+(\d+(?:,\d+)?))?\s*$")
TYPES = {"FLOAT": "f32", "SHORT": "i16"}
UNITS = {"V": "V", "A": "A", "W": "W", "Hz": "Hz", "%": "%", "Wh": "W.h", "VA": "V.A"}
NOT_UCUM = {"var": "Vendor unit: var.", "-": None}
EXPONENTS = {"1": 0, "0,1": -1, "0,01": -2}

# (section, label, index): (point id, format, unit, description)
SELECTED = {
    ("short", "Voltage U1 L1-N", "0"): ("voltage_l1_n_secondary", "SHORT", "V",
                                        "16-bit value without the voltage transformer ratio."),
    ("frequent", "Voltage L1-N", "0"): ("voltage_l1_n", "FLOAT", "V", None),
    ("frequent", "Voltage L2-N", "1"): ("voltage_l2_n", "FLOAT", "V", None),
    ("frequent", "Voltage L3-N", "2"): ("voltage_l3_n", "FLOAT", "V", None),
    ("frequent", "Voltage L1-L2", "0"): ("voltage_l1_l2", "FLOAT", "V", None),
    ("frequent", "Current I L1", "0"): ("current_l1", "FLOAT", "A", None),
    ("frequent", "Current I L2", "1"): ("current_l2", "FLOAT", "A", None),
    ("frequent", "Current I L3", "2"): ("current_l3", "FLOAT", "A", None),
    ("frequent", "Sum; Psum3=P1+P2+P3", "3"): ("active_power_total", "FLOAT", "W", None),
    ("frequent", "Sum; Qsum3=Q1+Q2+Q3", "3"): ("reactive_power_total", "FLOAT", "var",
                                               "Sum of the fundamental reactive power of L1 to L3."),
    ("frequent", "Sum; Ssum3=S1+S2+S3", "3"): ("apparent_power_total", "FLOAT", "VA", None),
    ("frequent", "Measured frequency", None): ("frequency", "FLOAT", "Hz", None),
    ("frequent", "Harmonic, THD U L1-N", "0"): ("voltage_thd_l1_n", "FLOAT", "%", None),
    ("frequent", "Harmonic, THD I L1", "0"): ("current_thd_l1", "FLOAT", "%", None),
    ("float", "Sum; Power factor sum3=Psum3/Ssum3", "3"): ("power_factor_total", "FLOAT", "-", None),
    ("energy", "Real energy, sum. L1..L3, obtained, rate", "0"): (
        "active_energy_import", "FLOAT", "Wh", "Rate index 0; the document states tariff 0 is always active."),
    ("energy", "Real energy, sum. L1..L3, supplied, rate", "0"): (
        "active_energy_export", "FLOAT", "Wh", "Rate index 0; the document states tariff 0 is always active."),
}
def headings(pages):
    """Section headings from the table of contents on the first three pages."""
    found = set()
    for page in pages[:3]:
        for line in page.splitlines():
            match = TOC_LINE.match(line)
            if match:
                found.add(match.group(1))
    return found


def heading_of(line, known):
    text = line.strip()
    matches = [name for name in known if text == name or text.startswith(name + " (")]
    return max(matches, key=len) if matches else None


def check_document(text, document):
    """Check the statements the selection relies on; return the ranges the UMG 96RM-PN note covers."""
    for pattern in document["identity"]:
        require(re.search(pattern, text), f"Janitza: document identity {pattern!r} not found")
    for key in ("big_endian", "short_unscaled", "tariff_zero"):
        require(re.search(document[key], text), f"Janitza: statement {key} not found")
    require(re.search(document["address_zero"], text, re.MULTILINE),
            "Janitza: parameter table does not start at address 0")
    for pattern in NUMBER_FORMATS:
        require(re.search(pattern, text, re.MULTILINE), f"Janitza: number format {pattern!r} not found")
    slave = re.search(document["slave"], text)
    require(slave, "Janitza: slave Modbus function list not found")
    position = slave.end()
    for pattern in FUNCTIONS:
        match = re.compile(pattern).search(text, position)
        require(match and match.start() - position < 200, f"Janitza: slave function {pattern[:24]!r} not listed")
        position = match.end()
    if document["pn_rs485"] is None:
        return None
    ranges = [(int(match.group(1)), int(match.group(2))) for match in re.finditer(document["pn_rs485"], text)]
    require(ranges, "Janitza: UMG 96RM-PN RS-485 note not found")
    return ranges


def extract(data, selector):
    require(selector in SELECTORS, f"Unknown Janitza selector {selector!r}")
    document = DOCUMENTS[SELECTORS[selector]]
    pages = pdf_pages(data, 1, pdf_page_count(data))
    profinet_only = check_document("\n".join(pages), document)
    known = headings(pages)
    sections = document["sections"]
    require(set(sections) <= known, "Janitza: section headings missing from the table of contents")

    found = {}
    headers = set()
    section = None
    for number, page in enumerate(pages[3:], start=4):
        for line in page.splitlines():
            heading = heading_of(line, known)
            if heading is not None:
                if document["end"] and heading.startswith(document["end"]):
                    section = "end"
                else:
                    section = sections.get(heading) if section != "end" else "end"
                continue
            if section in (None, "end"):
                continue
            if re.match(document["header"], line.strip()):
                headers.add(section)
                continue
            match = ROW.match(line)
            if not match:
                continue
            address, kind, access, unit, label, index, resolution = match.groups()
            key = (section, " ".join(label.split()), index)
            if key not in SELECTED:
                continue
            require(key not in found, f"Janitza: duplicate row {key}")
            found[key] = (number, int(address), kind, access, unit, resolution)
    missing = sorted(set(SELECTED) - found.keys(), key=str)
    require(not missing, f"Janitza: missing rows {missing}")
    require(headers >= {section for section, _, _ in SELECTED}, "Janitza: table header missing in a section")

    names = {value: name for name, value in sections.items()}
    points = []
    for key, (point_id, kind, vendor_unit, description) in SELECTED.items():
        number, address, found_kind, access, unit, resolution = found[key]
        require((found_kind, unit) == (kind, vendor_unit), f"Janitza {key}: unexpected format or unit")
        require(access in ("RD", "RD/WR"), f"Janitza {key}: not readable")
        point = {"id": point_id, "address": address, "type": TYPES[kind]}
        if kind == "SHORT":
            require(resolution in EXPONENTS, f"Janitza {key}: unexpected resolution {resolution!r}")
            if profinet_only is not None:
                require(any(low <= address <= high for low, high in profinet_only),
                        f"Janitza {key}: outside the ranges the UMG 96RM-PN note covers")
            if EXPONENTS[resolution]:
                point["conversion"] = {"exponent10": EXPONENTS[resolution]}
        else:
            require(resolution is None, f"Janitza {key}: unexpected resolution column")
        if vendor_unit in UNITS:
            point["unit"] = UNITS[vendor_unit]
        notes = [text for text in (description, NOT_UCUM.get(vendor_unit)) if text]
        if notes:
            point["description"] = " ".join(notes)
        label, index = key[1], key[2]
        point["aliases"] = [f"{label} [{index}]" if index is not None else label]
        point["source"] = {"address": str(address), "page": number, "reference": names[key[0]]}
        points.append(point)
    return sorted(points, key=lambda point: point["address"])
