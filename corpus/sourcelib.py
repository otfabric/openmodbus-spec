"""Helpers for corpus extractors. Source bytes are untrusted input.

Extractors parse vendor documents into OpenModbus points. They never execute
document content: PDFs go through Poppler's pdftotext, spreadsheets are read
as cached cell values from the workbook XML, and archives are read member by
member in memory.
"""
import csv
import io
import re
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
