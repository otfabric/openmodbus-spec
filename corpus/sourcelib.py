"""Helpers for corpus extractors. Source bytes are untrusted input.

Extractors parse vendor documents into OpenModbus points. They never execute
document content: PDFs go through Poppler's pdftotext, spreadsheets are read
as cached cell values from the workbook XML (.xlsx) or from the BIFF8 records
of the OLE2 workbook stream (.xls), and archives are read member by member in
memory.
"""
import csv
import io
import math
import re
import struct
import subprocess
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree

MAX_MEMBER_BYTES = 64 * 1024 * 1024


class CorpusError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise CorpusError(message)


def pdf_pages(data, first, last=None, layout=True):
    """Return the text of PDF pages first..last (1-based, inclusive) as a list."""
    last = first if last is None else last
    require(1 <= first <= last, f"Invalid PDF page range {first}-{last}")
    command = ["pdftotext", "-f", str(first), "-l", str(last), "-enc", "UTF-8"]
    if layout:
        command.append("-layout")
    result = subprocess.run([*command, "-", "-"], input=data, capture_output=True, check=True, timeout=60)
    pages = result.stdout.decode("utf-8").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    require(len(pages) == last - first + 1, f"PDF pages {first}-{last}: got {len(pages)} pages")
    return pages


def pdf_page_count(data):
    result = subprocess.run(["pdfinfo", "-"], input=data, capture_output=True, check=True, timeout=60)
    match = re.search(r"^Pages:\s+(\d+)$", result.stdout.decode("utf-8", "replace"), re.MULTILINE)
    require(match, "pdfinfo did not report a page count")
    return int(match.group(1))


def csv_rows(data, encoding="utf-8", **kwargs):
    """Yield (line_number, row) pairs from CSV bytes."""
    reader = csv.reader(io.StringIO(data.decode(encoding), newline=""), **kwargs)
    for row in reader:
        yield reader.line_num, row


def cell_text(parts):
    return " ".join("".join(parts).split())


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.heading = None
        self.heading_text = None
        self.context = {}
        self.stack = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and not self.stack:
            self.heading = {"tag": tag, "id": attrs.get("id"), "text": []}
            self.heading_text = self.heading["text"]
        elif tag == "table":
            self.stack.append({"heading": self.heading, "context": dict(self.context), "rows": []})
        elif tag == "tr" and self.stack:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        elif self.heading_text is not None:
            self.heading_text.append(data)

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self.heading_text is not None:
            self.heading = {**self.heading, "text": cell_text(self.heading_text)}
            self.heading_text = None
            level = int(self.heading["tag"][1])
            self.context = {key: value for key, value in self.context.items() if int(key[1]) < level}
            self.context[self.heading["tag"]] = {"id": self.heading["id"], "text": self.heading["text"]}
        elif tag in ("td", "th") and self.cell is not None:
            self.row.append(cell_text(self.cell))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.stack[-1]["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.stack:
            table = self.stack.pop()
            heading = table["heading"] or {}
            self.tables.append({
                "heading_id": heading.get("id"),
                "heading": heading.get("text") if isinstance(heading.get("text"), str) else None,
                "context": table["context"],
                "rows": table["rows"],
            })


def html_tables(data, encoding="utf-8"):
    """Return every HTML table as {heading_id, heading, context, rows} in document order.

    `heading` is the nearest preceding h1-h6 outside any table; `context` maps
    each open heading level ("h2", "h3", ...) to its {id, text}. Cell text is
    whitespace-normalised; nested tables are returned separately.
    """
    parser = _Tables()
    parser.feed(data.decode(encoding))
    parser.close()
    return parser.tables


def zip_member(data, name):
    """Return the bytes of one archive member, by exact name or regex fullmatch."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        matches = [info for info in infos if info.filename == name] or \
                  [info for info in infos if re.fullmatch(name, info.filename)]
        require(len(matches) == 1, f"Archive member {name!r}: {len(matches)} matches")
        info = matches[0]
        require(info.file_size <= MAX_MEMBER_BYTES, f"Archive member {info.filename}: too large")
        with archive.open(info) as member:
            content = member.read(MAX_MEMBER_BYTES + 1)
        require(len(content) == info.file_size, f"Archive member {info.filename}: size mismatch")
        return content


def zip_names(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return [info.filename for info in archive.infolist() if not info.is_dir()]


_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


def xlsx_sheets(data):
    """Return the workbook's sheet names in order."""
    workbook = ElementTree.fromstring(zip_member(data, "xl/workbook.xml"))
    return [sheet.get("name") for sheet in workbook.find("m:sheets", _NS)]


def xlsx_rows(data, sheet):
    """Yield (row_number, {column_letter: text}) for one worksheet.

    Reads cached values only: formulas are never evaluated and macros never run.
    Shared strings and inline strings are resolved; numbers stay as text.
    """
    workbook = ElementTree.fromstring(zip_member(data, "xl/workbook.xml"))
    rels = ElementTree.fromstring(zip_member(data, "xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels.findall("rel:Relationship", _NS)}
    sheet_ids = {node.get("name"): node.get(f"{{{_NS['r']}}}id") for node in workbook.find("m:sheets", _NS)}
    require(sheet in sheet_ids, f"Workbook has no sheet {sheet!r}")
    target = targets[sheet_ids[sheet]].lstrip("/")
    target = target if target.startswith("xl/") else "xl/" + target
    shared = []
    try:
        strings = ElementTree.fromstring(zip_member(data, "xl/sharedStrings.xml"))
        shared = ["".join(node.itertext()) for node in strings.findall("m:si", _NS)]
    except CorpusError:
        pass
    root = ElementTree.fromstring(zip_member(data, target))
    for row in root.iter(f"{{{_NS['m']}}}row"):
        values = {}
        for cell in row.findall("m:c", _NS):
            reference = cell.get("r")
            kind = cell.get("t")
            if kind == "inlineStr":
                text = "".join(cell.find("m:is", _NS).itertext())
            else:
                value = cell.find("m:v", _NS)
                if value is None or value.text is None:
                    continue
                text = shared[int(value.text)] if kind == "s" else value.text
            column = re.match(r"[A-Z]+", reference).group()
            values[column] = " ".join(text.split())
        if values:
            yield int(row.get("r")), values


def column_letter(index):
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


_OLE_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
_OLE_END_OF_CHAIN = 0xFFFFFFFE
_OLE_NO_ENTRY = 0xFFFFFFFF
_BIFF_BOF, _BIFF_EOF, _BIFF_CONTINUE = 0x0809, 0x000A, 0x003C
_BIFF_GLOBALS, _BIFF_WORKSHEET = 0x0005, 0x0010
# Cell records of BIFF2 to BIFF4: a BIFF8 worksheet must not hold them, and skipping them would lose cells.
_BIFF_OLD_CELLS = (0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0007, 0x007E, 0x0206, 0x0406)


def _unpack(layout, data, offset=0):
    require(offset + struct.calcsize(layout) <= len(data), "Workbook is truncated or malformed")
    return struct.unpack_from(layout, data, offset)


def _ole_chain(source, base, size, table, start, what, length=None):
    """Join the sectors of one chain; sector n is source[base + n * size:][:size]."""
    blocks, seen = [], set()
    while start != _OLE_END_OF_CHAIN and (length is None or len(blocks) * size < length):
        require(start < len(table) // 4 and start not in seen, f"OLE2 {what}: broken sector chain")
        seen.add(start)
        blocks.append(source[base + start * size:base + (start + 1) * size])
        start = struct.unpack_from("<I", table, 4 * start)[0]
    content = b"".join(blocks)
    require(length is None or len(content) >= length, f"OLE2 {what}: broken sector chain")
    return content if length is None else content[:length]


def _ole_stream(data, names):
    """Return one top-level stream of an OLE2 compound file: the first of `names` (upper case) that exists."""
    require(data[:8] == _OLE_MAGIC, "Not an OLE2 compound file")
    major, order, shift, mini_shift = _unpack("<4H", data, 26)
    require(order == 0xFFFE and (major, shift, mini_shift) in ((3, 9, 6), (4, 12, 6)), "Unsupported OLE2 header")
    fat_count, directory_start, _, cutoff, minifat_start, _, difat_start, _ = _unpack("<8I", data, 44)
    size = 1 << shift
    require(fat_count <= len(data) // size, "OLE2 header: more FAT sectors than the file holds")
    difat = list(_unpack("<109I", data, 76))
    while len(difat) < fat_count:
        block = _unpack(f"<{size // 4}I", data, (difat_start + 1) * size)
        difat += block[:-1]
        difat_start = block[-1]
    sectors = difat[:fat_count]
    require(len(set(sectors)) == fat_count, "OLE2 FAT: a sector is listed twice")
    fat = b"".join(data[(sector + 1) * size:(sector + 2) * size] for sector in sectors)
    require(len(fat) == fat_count * size, "OLE2 FAT: a sector is outside the file")
    used = -(-len(fat.rstrip(b"\xff")) // 4)  # free sectors are 0xFFFFFFFF, so this counts up to the last one in use
    require((used + 1) * size <= len(data), f"OLE2 file is truncated: it ends before sector {used - 1}")
    directory = _ole_chain(data, size, size, fat, directory_start, "directory")

    def entry(index):
        name_size, kind, _, left, right, child = _unpack("<HBB3I", directory, index * 128 + 64)
        start, length = _unpack("<IQ", directory, index * 128 + 116)
        name = directory[index * 128:index * 128 + max(min(name_size, 64) - 2, 0)].decode("utf-16-le", "replace")
        return name.upper(), kind, left, right, child, start, length if major == 4 else length & 0xFFFFFFFF

    _, kind, _, _, child, ministream_start, _ = entry(0)
    require(kind == 5, "OLE2 directory has no root entry")
    streams, todo, seen = {}, [child], set()
    while todo:
        index = todo.pop()
        if index != _OLE_NO_ENTRY:
            require(index not in seen, "OLE2 directory: broken tree")
            seen.add(index)
            name, kind, left, right, _, start, length = entry(index)
            todo += [left, right]
            if kind == 2 and name in names:
                require(name not in streams, f"OLE2 file has two {name} streams")
                streams[name] = (start, length)
    name = next((name for name in names if name in streams), None)
    require(name, f"OLE2 file has no {' or '.join(names)} stream")
    start, length = streams[name]
    require(length <= MAX_MEMBER_BYTES, f"OLE2 {name} stream: too large")
    if length >= cutoff:
        return _ole_chain(data, size, size, fat, start, f"{name} stream", length)
    ministream = _ole_chain(data, size, size, fat, ministream_start, "mini stream")
    minifat = _ole_chain(data, size, size, fat, minifat_start, "mini FAT")
    return _ole_chain(ministream, 0, 1 << mini_shift, minifat, start, f"{name} stream", length)


def _biff_records(stream, pos, end, content):
    """Yield (record_id, [payload, CONTINUE payloads...]) for the BIFF8 substream in stream[pos:end].

    `content` is the substream type the BOF record must state. Nested
    substreams (charts embedded in a worksheet) are skipped.
    """
    kind, _, version, found = _unpack("<4H", stream, pos)
    require(kind == _BIFF_BOF and version == 0x0600, f"Not BIFF8: BOF 0x{kind:04X}, version 0x{version:04X}")
    require(found == content, f"BIFF substream is of type 0x{found:04X}, expected 0x{content:04X}")
    depth, held = 0, None
    while True:
        kind, size = _unpack("<HH", stream, pos)
        pos += 4 + size
        require(pos <= end, "BIFF substream has no end")
        if kind == _BIFF_CONTINUE and held:
            held[1].append(stream[pos - size:pos])
            continue
        if held:
            yield held
        depth += (kind == _BIFF_BOF) - (kind == _BIFF_EOF)
        if not depth:
            return
        held = (kind, [stream[pos - size:pos]]) if depth == 1 and kind not in (_BIFF_BOF, _BIFF_EOF) else None


def _biff_string(parts, index=0, pos=0, wide_count=True):
    """Decode the BIFF8 string at parts[index][pos:]; return (text, index, pos) with the position after it.

    Characters, rich-text runs and phonetic data may run on into the next part
    (a CONTINUE record); continued characters restate the 8-bit/16-bit flag.
    An 8-bit string holds the low bytes of UTF-16 units, whatever CODEPAGE says.
    """
    if pos == len(parts[index]) and index + 1 < len(parts):
        index, pos = index + 1, 0
    part = parts[index]
    length, = _unpack("<H" if wide_count else "<B", part, pos)
    pos += 2 if wide_count else 1
    if not length and pos == len(part):
        return "", index, pos  # some writers leave the flags out of an empty string
    flags, = _unpack("<B", part, pos)
    pos += 1
    runs = phonetic = 0
    if flags & 0x08:
        runs, = _unpack("<H", part, pos)
        pos += 2
    if flags & 0x04:
        phonetic, = _unpack("<I", part, pos)
        pos += 4
    units = []
    while True:
        wide = flags & 0x01
        count = min(length, (len(part) - pos) >> wide)
        chunk = part[pos:pos + (count << wide)]
        units.append(chunk if wide else chunk.decode("latin-1").encode("utf-16-le"))
        pos += count << wide
        length -= count
        if not length:
            break
        require(pos == len(part) and index + 1 < len(parts), "BIFF string runs past its record")
        index, part = index + 1, parts[index + 1]
        flags, = _unpack("<B", part)
        pos = 1
    skip = 4 * runs + phonetic
    while skip > len(part) - pos and index + 1 < len(parts):
        skip -= len(part) - pos
        index, part, pos = index + 1, parts[index + 1], 0
    require(skip <= len(part) - pos, "BIFF string runs past its record")
    try:
        return b"".join(units).decode("utf-16-le"), index, pos + skip
    except UnicodeDecodeError as error:
        raise CorpusError(f"BIFF string is not UTF-16: {error}") from error


def _xls_workbook(data):
    """Return (workbook stream, {worksheet name: (start, end) of its substream}, shared strings)."""
    stream = _ole_stream(data, ("WORKBOOK", "BOOK"))
    bound, strings = [], []
    for kind, parts in _biff_records(stream, 0, len(stream), _BIFF_GLOBALS):
        require(kind != 0x002F, "Workbook is encrypted")  # FILEPASS
        if kind == 0x0085:  # BOUNDSHEET: substream offset, visibility, sheet type, name
            offset, _, sheet_type = _unpack("<IBB", parts[0])
            bound.append((offset, sheet_type, _biff_string(parts, 0, 6, wide_count=False)[0]))
        elif kind == 0x00FC:  # SST: total count, unique count, then the unique strings
            index, pos = 0, 8
            for _ in range(_unpack("<I", parts[0], 4)[0]):
                text, index, pos = _biff_string(parts, index, pos)
                strings.append(text)
    starts = sorted(offset for offset, _, _ in bound)
    require(len(set(starts)) == len(starts) and (not starts or starts[-1] < len(stream)),
            "Workbook has sheets that share a substream or start outside the stream")
    ends = dict(zip(starts, starts[1:] + [len(stream)]))  # a substream ends where the next one starts
    sheets = {}
    for offset, sheet_type, name in bound:
        if sheet_type == 0:  # a worksheet or a dialog sheet; bit 4 of WSBOOL tells them apart
            records = _biff_records(stream, offset, ends[offset], _BIFF_WORKSHEET)
            wsbool = next((body[0] for found, body in records if found == 0x0081), b"\0\0")
            if not _unpack("<H", wsbool)[0] & 0x0010:
                require(name not in sheets, f"Workbook has two sheets named {name!r}")
                sheets[name] = (offset, ends[offset])
    return stream, sheets, strings


def _number_text(value):
    require(math.isfinite(value), "Workbook holds a number that is not finite")
    return str(int(value)) if value == int(value) else repr(value)


def _rk_number(rk):
    """Decode an RK value: a 30-bit integer or the top 30 bits of a double, either one optionally in hundredths."""
    number = float(rk >> 2) if rk & 2 else struct.unpack("<d", struct.pack("<Ii", 0, rk & -4))[0]
    return number / 100 if rk & 1 else number


def xls_sheets(data):
    """Return the worksheet names of a legacy .xls workbook in order; chart, macro and dialog sheets are left out."""
    return list(_xls_workbook(data)[1])


def xls_rows(data, sheet):
    """Yield (row_number, {column_letter: text}) for one worksheet of a legacy .xls workbook (BIFF8 in OLE2).

    Same contract as xlsx_rows. Reads cached values only: formulas are never
    evaluated (their stored result is used) and macro or VBA streams are never
    read. Numbers are text: an integral value has no fraction ("3000"), any
    other is its shortest round-trip repr ("0.1"). Booleans are "TRUE" or
    "FALSE"; error cells are omitted. Anything but an unencrypted BIFF8
    workbook raises CorpusError.
    """
    stream, sheets, strings = _xls_workbook(data)
    require(sheet in sheets, f"Workbook has no sheet {sheet!r}")
    rows, awaiting = {}, None

    def put(row, column, text):
        cells = rows.setdefault(row, {})
        require(column not in cells, f"Sheet {sheet!r}: cell {column_letter(column)}{row + 1} is stored twice")
        cells[column] = " ".join(text.split())

    for kind, parts in _biff_records(stream, *sheets[sheet], _BIFF_WORKSHEET):
        body = parts[0]
        require(kind not in _BIFF_OLD_CELLS, f"Sheet {sheet!r}: cell record 0x{kind:04X} is not BIFF8")
        require(awaiting is None or kind in (0x0207, 0x04BC, 0x0221, 0x0236), f"Sheet {sheet!r}: formula without text")
        if kind == 0x0207 and awaiting is not None:  # STRING: cached text of the FORMULA before it
            put(*awaiting, _biff_string(parts)[0])
            awaiting = None
        elif kind == 0x00FD:  # LABELSST
            row, column, _, index = _unpack("<HHHI", body)
            require(index < len(strings), f"Sheet {sheet!r}: shared string {index} does not exist")
            put(row, column, strings[index])
        elif kind in (0x0204, 0x00D6):  # LABEL, RSTRING
            put(*_unpack("<HH", body), _biff_string(parts, 0, 6)[0])
        elif kind == 0x0203:  # NUMBER
            row, column, _, number = _unpack("<HHHd", body)
            put(row, column, _number_text(number))
        elif kind == 0x027E:  # RK
            row, column, _, rk = _unpack("<HHHi", body)
            put(row, column, _number_text(_rk_number(rk)))
        elif kind == 0x00BD:  # MULRK: row, first column, (format, RK) per column, last column
            row, first = _unpack("<HH", body)
            last, = _unpack("<H", body, len(body) - 2)
            require(len(body) == 6 * (last - first + 1) + 6, f"Sheet {sheet!r}: malformed MULRK record")
            for column in range(first, last + 1):
                put(row, column, _number_text(_rk_number(_unpack("<i", body, 6 * (column - first) + 6)[0])))
        elif kind == 0x0205:  # BOOLERR
            row, column, _, value, is_error = _unpack("<HHHBB", body)
            if not is_error:
                put(row, column, "TRUE" if value else "FALSE")
        elif kind == 0x0006:  # FORMULA: the cached result is a double or, marked 0xFFFF, a typed value
            row, column, _, result, value, marker = _unpack("<HHHBxB3xH", body)
            if marker != 0xFFFF:
                put(row, column, _number_text(_unpack("<d", body, 6)[0]))
            elif result == 0:  # text, in the STRING record that follows
                awaiting = (row, column)
            elif result == 1:
                put(row, column, "TRUE" if value else "FALSE")
            elif result == 3:  # empty text
                put(row, column, "")
            else:
                require(result == 2, f"Sheet {sheet!r}: unknown formula result type {result}")
    require(awaiting is None, f"Sheet {sheet!r}: formula without text")
    for row in sorted(rows):
        yield row + 1, {column_letter(column): rows[row][column] for column in sorted(rows[row])}


def modicon_reference(reference, table):
    """Resolve a five- or six-digit Modicon reference (40001, 300001) to a zero-based address.

    Only for documents that state this notation; the caller passes the expected table.
    """
    text = str(reference).strip()
    require(re.fullmatch(r"[0134]\d{4,5}", text), f"Not a Modicon reference: {reference!r}")
    prefix = {"coil": "0", "discrete_input": "1", "input_register": "3", "holding_register": "4"}[table]
    require(text[0] == prefix, f"Reference {reference} is not in the {table} table")
    address = int(text[1:]) - 1
    require(0 <= address <= 65535, f"Reference {reference} is outside the address space")
    return address
