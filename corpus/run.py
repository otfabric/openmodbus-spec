#!/usr/bin/env python3
"""Extract and verify catalog contracts from checksum-pinned vendor sources."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml

CORPUS = Path(__file__).resolve().parent
sys.path.insert(0, str(CORPUS.parent / "scripts"))
from validate import ROOT, contract_validator, validate_contract  # noqa: E402
from sourcelib import CorpusError, require  # noqa: E402

# Some publishers reject the default Python client string. This one names the
# tool honestly without identifying the repository or its maintainer.
USER_AGENT = "corpus-fetch/1"
EXTRACTORS = CORPUS / "extractors"
WIDTHS = {"bool": 1, "u16": 1, "i16": 1, "u32": 2, "i32": 2, "f32": 2, "u64": 4, "i64": 4, "f64": 4}
BIT_TABLES = ("coil", "discrete_input")
REGISTER_TABLES = ("holding_register", "input_register")
NOT_UCUM = {"kWh", "Wh", "MWh", "kVAh", "kvarh", "varh", "kVArh", "degC", "°C", "rpm", "RPM", "VA", "kVA",
            "var", "kvar", "VAr", "kVAr", "sec", "hrs", "W/m²", "Ω", "% RH", "%RH"}
# Fields of a row dump, in output order. Values other than table and address are the document's own text.
ROW_KEYS = ("table", "address", "vendor_address", "registers", "type", "label", "unit", "scale", "access",
            "notes", "page", "reference")


class ContractDumper(yaml.SafeDumper):
    """PyYAML resolves scalars by YAML 1.1. Quote any string that a YAML 1.2 Core
    parser would read as a number, boolean or null, so contracts mean the same
    to every conforming parser (e.g. a vendor address "00508")."""


YAML12_NON_STRING = re.compile(
    r"[-+]?(0o[0-7]+|0x[0-9a-fA-F]+|[0-9]+|(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?)"
    r"|[-+]?\.(inf|Inf|INF)|\.(nan|NaN|NAN)|true|True|TRUE|false|False|FALSE|null|Null|NULL|~|")


def _represent_str(dumper, data):
    style = "'" if YAML12_NON_STRING.fullmatch(data) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


ContractDumper.add_representer(str, _represent_str)


def dump_contract(document):
    return yaml.dump(document, Dumper=ContractDumper, sort_keys=False, allow_unicode=True)


def read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def cloudflare_injections(data):
    """Remove what Cloudflare adds per response: email-obfuscation keys and the analytics beacon."""
    data = re.sub(rb"/cdn-cgi/l/email-protection#[0-9a-f]+", b"/cdn-cgi/l/email-protection#", data)
    data = re.sub(rb'data-cfemail="[0-9a-f]+"', b'data-cfemail=""', data)
    return re.sub(rb"<script[^>]*static\.cloudflareinsights\.com/beacon[^>]*></script>\n?", b"", data)


# A normalisation removes bytes that a publisher's CDN randomises or injects per
# response. The lock names it, and its `size` and `sha256` describe the
# normalised bytes. Raw responses may exceed `size` by at most NORMALIZE_SLACK.
NORMALIZERS = {"cloudflare": cloudflare_injections}
NORMALIZE_SLACK = 64 * 1024


def normalized(data, lock):
    name = lock.get("normalize")
    require(name is None or name in NORMALIZERS, f"Unknown source normalisation {name!r}")
    return NORMALIZERS[name](data) if name else data


def read_limit(lock):
    return lock["size"] + (NORMALIZE_SLACK if lock.get("normalize") else 0) + 1


def verify(data, lock, origin):
    require(len(data) < read_limit(lock), f"{origin}: response larger than the lock allows")
    data = normalized(data, lock)
    require(len(data) == lock["size"], f"{origin}: byte size differs from lock ({len(data)} bytes)")
    actual = hashlib.sha256(data).hexdigest()
    require(actual == lock["sha256"], f"{origin}: SHA-256 differs from lock ({actual})")


def read_source(path, lock):
    with path.open("rb") as source:
        data = source.read(read_limit(lock))
    verify(data, lock, path)
    return data


def https_url(url):
    parts = urlsplit(url)
    require(parts.scheme == "https" and parts.hostname and parts.username is None,
            "Expected an HTTPS vendor URL without credentials")


class HTTPSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def cached_source(source, lock, cache, offline):
    urls = source.get("download_urls")
    require(isinstance(urls, list) and urls, "Source needs a direct public download URL")
    for url in urls:
        https_url(url)
    cache = cache.expanduser().resolve()
    require(not cache.is_relative_to(ROOT), "Corpus cache must be outside the checkout")
    digest = lock["sha256"]
    path = cache / digest
    if path.exists():
        require(path.is_file() and not path.is_symlink(), "Corpus cache entry must be a regular file")
        try:
            return read_source(path, lock)
        except CorpusError:
            if offline:
                raise
    require(not offline, f"Locked source is missing from the offline cache: {digest}")

    failures = []
    for url in urls:
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with build_opener(HTTPSRedirects()).open(request, timeout=60) as response:
                data = response.read(read_limit(lock))
            verify(data, lock, url)
        except (CorpusError, OSError) as exc:
            failures.append(f"{url}: {exc}")
            continue

        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as staging:
            temp_path = Path(staging) / "source"
            with temp_path.open("wb") as temp:
                temp.write(data)
            temp_path.replace(path)
        return data

    raise CorpusError("No vendor URL returned the locked source: " + " | ".join(failures))


def load_extractor(name):
    require(isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]*", name), f"Invalid extractor name {name!r}")
    path = EXTRACTORS / f"{name}.py"
    require(path.is_file(), f"Extractor module missing: {path.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location(f"corpus_extractor_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(callable(getattr(module, "extract", None)), f"{name}: no extract(data, selector) function")
    require(not hasattr(module, "all_rows") or callable(module.all_rows), f"{name}: all_rows is not a function")
    return module


def link(document):
    result = {"title": document["title"], "url": document.get("documentation_url", document["download_urls"][0])}
    if "revision" in document:
        result["revision"] = document["revision"]
    return result


def build_contract(source_id, source, contract, extracted):
    if isinstance(extracted, list):
        extracted = {"points": extracted}
    require(set(extracted) <= {"points", "components", "constraints"}, "Unexpected extractor result keys")
    documentation = [link(source), *(link(item) for item in source.get("evidence", []))]
    document = {
        "openmodbus": "0.1.0",
        "info": {
            **contract["info"],
            "source": "integrator",
            "verification": "documented",
            "x-otfabric-corpus-source": source_id,
        },
        "device": {**contract["device"], "documentation": documentation},
    }
    for key in ("defaults", "constraints"):
        if key in contract or key in extracted:
            document[key] = {**contract.get(key, {}), **extracted.get(key, {})}
    if "components" in extracted:
        document["components"] = extracted["components"]
    document["points"] = extracted["points"]
    return document


def register_bits(point, defaults, width):
    mask = point.get("mask")
    if mask is None:
        return [0xFFFF] * width
    words = [(mask >> (16 * (width - 1 - index))) & 0xFFFF for index in range(width)]
    if point.get("wordOrder", defaults.get("wordOrder", "big")) == "little":
        words.reverse()
    return words


def verify_contract(validator, document, path):
    """Schema validation plus the structural rules the corpus relies on.

    Corpus contracts are flat lists of read-only points. This is a subset of the
    draft's level-2 rules, not a full semantic validator.
    """
    errors = validate_contract(validator, document, path)
    require(not errors, "\n".join(errors))
    defaults = document.get("defaults", {})
    points = document["points"]
    require(points, "Contract has no points")
    ids = {point["id"] for point in points}
    require(len(ids) == len(points), "Duplicate point ID")
    occupied = {}
    for point in points:
        point_id = point["id"]
        kind = point["type"]
        table = point.get("table", defaults.get("table"))
        require(table is not None, f"{point_id}: no table")
        require(table in (BIT_TABLES if kind == "bool" else REGISTER_TABLES),
                f"{point_id}: type {kind} does not fit table {table}")
        require(point.get("access", defaults.get("access", "r")) == "r" and "write" not in point,
                f"{point_id}: corpus contracts are read-only")
        if kind in ("string", "bytes"):
            require("registers" in point, f"{point_id}: {kind} needs registers")
            width = point["registers"]
        else:
            require("registers" not in point, f"{point_id}: registers is only for string and bytes")
            width = WIDTHS[kind]
        count = point.get("count", 1)
        end = point["address"] + width * count - 1
        require(end <= 65535, f"{point_id}: address range exceeds address space")
        if "mask" in point:
            require(kind in ("u16", "u32", "u64"), f"{point_id}: mask on {kind}")
            mask = point["mask"]
            require(mask < (1 << (16 * width)), f"{point_id}: mask wider than the type")
            shifted = mask >> ((mask & -mask).bit_length() - 1)
            require(shifted & (shifted + 1) == 0, f"{point_id}: mask is not contiguous")
        no_conversion = kind in ("bool", "string", "bytes") or "enum" in point or "flags" in point
        require(not (no_conversion and "conversion" in point), f"{point_id}: conversion not allowed")
        exponent = point.get("conversion", {}).get("exponent10")
        if isinstance(exponent, dict):
            require(exponent["point"] in ids, f"{point_id}: exponent10 refers to unknown point")
        unit = point.get("unit")
        require(unit is None or unit not in NOT_UCUM, f"{point_id}: unit {unit!r} is not a UCUM code")
        bits = [1] * (width * count) if kind == "bool" else register_bits(point, defaults, width) * count
        for index, mask in enumerate(bits):
            key = (table, point["address"] + index)
            require(not occupied.get(key, 0) & mask, f"{point_id}: address range overlaps another point")
            occupied[key] = occupied.get(key, 0) | mask


def select_sources(manifest, lock, args):
    sources = manifest["sources"]
    if args.source:
        unknown = sorted(set(args.source) - sources.keys())
        if unknown:
            raise CorpusError(f"Unknown source IDs: {unknown}")
        return list(args.source)
    if args.changed_from:
        return changed_sources(manifest, lock, args.changed_from)
    if args.source_set == "all":
        return list(sources)
    require(args.source_set in manifest["sets"], f"Unknown corpus set {args.source_set!r}")
    return manifest["sets"][args.source_set]


def changed_sources(manifest, lock, ref):
    """Sources whose manifest entry, lock pin, extractor or contracts differ from ref."""
    base = subprocess.run(["git", "merge-base", ref, "HEAD"], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()

    def show(path):
        result = subprocess.run(["git", "show", f"{base}:{path}"], cwd=ROOT, capture_output=True, text=True)
        return yaml.safe_load(result.stdout) if result.returncode == 0 else {}

    changed_files = subprocess.run(["git", "diff", "--name-only", base, "--"], cwd=ROOT, capture_output=True,
                                   text=True, check=True).stdout.split()
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.split()
    changed_files = set(changed_files) | set(untracked)
    if changed_files & {"corpus/run.py", "corpus/sourcelib.py", "scripts/validate.py",
                        "schema/0.1/contract.schema.json"}:
        return list(manifest["sources"])
    old_sources = (show("corpus/sources.yaml") or {}).get("sources", {})
    old_lock = (show("corpus/sources.lock.yaml") or {}).get("sources", {})
    selected = []
    for source_id, source in manifest["sources"].items():
        files = {f"corpus/extractors/{source.get('extractor')}.py",
                 *(contract["path"] for contract in source.get("contracts", []))}
        pins = [source_id, *(item["id"] for item in source.get("evidence", []))]
        if (old_sources.get(source_id) != source or any(old_lock.get(pin) != lock.get(pin) for pin in pins)
                or files & changed_files):
            selected.append(source_id)
    return selected


def check_manifest(manifest, lock):
    """Offline consistency of manifest, lock, extractors and catalog files. No downloads."""
    errors = []
    sources = manifest.get("sources") or {}
    pins = lock.get("sources") or {}
    for set_name, members in (manifest.get("sets") or {}).items():
        errors += [f"set {set_name}: unknown source {member}" for member in members if member not in sources]
    paths, contract_ids, used_pins = set(), set(), set()
    for source_id, source in sources.items():
        def fail(message):
            errors.append(f"{source_id}: {message}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", source_id):
            fail("invalid source ID")
        missing = [key for key in ("publisher", "title", "download_urls", "format", "extractor", "contracts")
                   if key not in source]
        if missing:
            fail(f"missing keys {missing}")
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(source["extractor"])) or \
                not (EXTRACTORS / f"{source['extractor']}.py").is_file():
            fail(f"extractor module missing: {source['extractor']}")
        for item in [{"id": source_id, **source}, *source.get("evidence", [])]:
            if item is not source and not all(key in item for key in ("id", "title", "download_urls", "format")):
                fail(f"evidence {item.get('id')}: needs id, title, download_urls and format")
                continue
            for url in item["download_urls"]:
                try:
                    https_url(url)
                except CorpusError as exc:
                    fail(f"{url}: {exc}")
            used_pins.add(item["id"])
            pin = pins.get(item["id"])
            if not isinstance(pin, dict):
                fail(f"no lock entry for {item['id']}")
            elif not (re.fullmatch(r"[a-f0-9]{64}", str(pin.get("sha256"))) and type(pin.get("size")) is int
                      and pin["size"] > 0 and pin.get("verified_on")
                      and pin.get("normalize", None) in (None, *NORMALIZERS)):
                fail(f"invalid lock entry for {item['id']}")
        for contract in source["contracts"]:
            path = (ROOT / contract["path"]).resolve()
            if not (path.is_relative_to(ROOT / "devices") and path.name.endswith(".omb.yaml")):
                fail(f"{contract['path']}: not a .omb.yaml under devices/")
            elif not path.is_file():
                fail(f"{contract['path']}: contract file missing")
            if path in paths or contract["info"]["id"] in contract_ids:
                fail(f"{contract['path']}: duplicate path or catalog ID")
            paths.add(path)
            contract_ids.add(contract["info"]["id"])
    errors += [f"lock entry without source or evidence: {pin}" for pin in pins if pin not in used_pins]
    errors += [f"{path.relative_to(ROOT)}: not produced by any corpus source"
               for path in sorted((ROOT / "devices").rglob("*.omb.yaml")) if path.resolve() not in paths]
    return errors


def checked_rows(rows, where):
    """The rows an extractor's all_rows() returned, each checked for the row-dump fields."""
    require(isinstance(rows, list) and rows, f"{where}: all_rows() returned no list of rows")
    for index, row in enumerate(rows):
        ref = f"{where}: row {index}"
        require(isinstance(row, dict) and row and set(row) <= set(ROW_KEYS), f"{ref}: unexpected fields")
        require("label" in row or "vendor_address" in row, f"{ref}: needs a label or a vendor address")
        for key, value in row.items():
            require(type(value) in (str, int, float) or value is None, f"{ref}: {key} is not a scalar")
        require(row.get("table", REGISTER_TABLES[0]) in BIT_TABLES + REGISTER_TABLES, f"{ref}: unknown table")
        require("address" not in row or type(row["address"]) is int and 0 <= row["address"] <= 0xFFFF,
                f"{ref}: address must be a protocol address from 0 to 65535")
        require(all(type(row.get(key, 1)) is int and row.get(key, 1) >= 1 for key in ("registers", "page")),
                f"{ref}: registers and page must be positive integers")
    return rows


def dump_rows(directory, source_id, contract, document, rows):
    """Write every parsed row next to the contract's catalog path, under a directory outside the checkout.

    A row with an address is marked selected when a contract point starts there in the same table (in
    any register table when the row names none).
    """
    default = document.get("defaults", {}).get("table")
    starts = {(point.get("table", default), point["address"]) for point in document["points"]}
    dumped = []
    for row in rows:
        entry = {key: row[key] for key in ROW_KEYS if key in row}
        if "address" in row:
            tables = [row["table"]] if "table" in row else REGISTER_TABLES
            entry["selected"] = any((table, row["address"]) in starts for table in tables)
        dumped.append(entry)
    relative = Path(contract["path"]).relative_to("devices")
    path = directory / relative.parent / relative.name.replace(".omb.yaml", ".rows.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    header = {"source": source_id, "contract": document["info"]["id"], "selector": contract.get("selector"),
              "count": len(dumped), "selected": sum(1 for entry in dumped if entry.get("selected"))}
    path.write_text(yaml.dump({**header, "rows": dumped}, Dumper=ContractDumper, sort_keys=False,
                              allow_unicode=True, width=120), encoding="utf-8")
    return path


def fetch_pinned(document, pin, cache, offline):
    require(re.fullmatch(r"[a-f0-9]{64}", pin["sha256"]), "Invalid SHA-256 in source lock")
    require(type(pin["size"]) is int and pin["size"] > 0, "Invalid byte size in source lock")
    return normalized(cached_source(document, pin, cache, offline), pin)


def build_source(source_id, source, lock, cache, offline, validator, catalog, contract_ids, rows_dir=None):
    devices = ROOT / "devices"
    extractor = load_extractor(source["extractor"])
    contracts = source.get("contracts")
    require(isinstance(contracts, list) and contracts, "Source needs at least one contract")
    data = fetch_pinned(source, lock[source_id], cache, offline)
    # Evidence documents state facts the extractor checks (address base, function code, word order)
    # but are not mapped themselves. They are pinned like sources.
    evidence = {}
    for item in source.get("evidence", []):
        require(item["id"] in lock, f"Evidence {item['id']} has no lock entry")
        evidence[item["id"]] = fetch_pinned(item, lock[item["id"]], cache, offline)
    extra = {"evidence": evidence} if evidence else {}
    built = []
    for contract in contracts:
        path = (ROOT / contract["path"]).resolve()
        require(path.is_relative_to(devices) and path.name.endswith(".omb.yaml"),
                "Contract path must be a .omb.yaml under devices/")
        require(path not in catalog, f"Duplicate catalog path: {path.relative_to(ROOT)}")
        document = build_contract(source_id, source, contract,
                                  extractor.extract(data, contract.get("selector"), **extra))
        verify_contract(validator, document, path.relative_to(ROOT))
        if rows_dir and hasattr(extractor, "all_rows"):
            rows = checked_rows(extractor.all_rows(data, contract.get("selector"), **extra),
                                f"{source_id}: {contract['path']}")
            written = dump_rows(rows_dir, source_id, contract, document, rows)
            print(f"{source_id}: {len(rows)} rows of {contract['path']} in {written}")
        contract_id = document["info"]["id"]
        require(contract_id not in contract_ids, f"Duplicate catalog ID: {contract_id}")
        contract_ids.add(contract_id)
        catalog[path] = document
        built.append((path, document))
    return built, hasattr(extractor, "all_rows")


def build_catalog(source_ids, sources, lock, cache, offline, write, rows_dir=None):
    validator = contract_validator()
    catalog = {}
    contract_ids = set()
    failures = []
    without_rows = []
    for source_id in source_ids:
        try:
            require(source_id in lock, "Source has no lock entry")
            built, has_rows = build_source(source_id, sources[source_id], lock, cache, offline,
                                           validator, catalog, contract_ids, rows_dir)
        except (CorpusError, OSError, KeyError, TypeError, ValueError, yaml.YAMLError,
                subprocess.SubprocessError) as exc:
            failures.append(f"{source_id}: {type(exc).__name__}: {exc}")
            print(f"{source_id}: FAILED: {exc}", file=sys.stderr)
            continue
        if not has_rows:
            without_rows.append(source_id)
        for path, document in built:
            relative = path.relative_to(ROOT)
            if not write and not (path.is_file() and read_yaml(path) == document):
                failures.append(f"{source_id}: {relative} differs from extraction. "
                                "Run with --write-catalog and review the diff.")
                continue
            print(f"{source_id}: {relative}: {len(document['points'])} points")

    if write:
        for path, document in catalog.items():
            content = dump_contract(document)
            if path.is_file() and path.read_text(encoding="utf-8") == content:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=path.parent) as staging:
                temp = Path(staging) / path.name
                temp.write_text(content, encoding="utf-8")
                temp.replace(path)
    print(f"Catalog {'built' if write else 'verified'}: {len(catalog)} contracts from "
          f"{len(source_ids) - len(failures)} of {len(source_ids)} sources")
    if rows_dir and without_rows:
        print(f"No row dump (extractor has no all_rows): {', '.join(without_rows)}")
    if failures:
        raise CorpusError("\n".join(["Failed sources:", *failures]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", default="pilot", dest="source_set", help="named set, or 'all'")
    parser.add_argument("--source", action="append", help="build only this source ID (repeatable)")
    parser.add_argument("--changed-from", metavar="REF", help="build only sources changed since a git ref")
    parser.add_argument("--manifest", default=CORPUS / "sources.yaml", type=Path)
    parser.add_argument("--lock", default=CORPUS / "sources.lock.yaml", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--write-catalog", action="store_true")
    parser.add_argument("--check-manifest", action="store_true", help="offline consistency check only")
    parser.add_argument("--dump-rows", metavar="DIR", type=Path,
                        help="also write every row the extractors parse, for cross-checks (outside the checkout)")
    args = parser.parse_args()
    manifest = read_yaml(args.manifest)
    lock = read_yaml(args.lock)
    if manifest.get("version") != 2 or lock.get("version") != 1:
        parser.error("unsupported corpus manifest or lock version")
    if args.check_manifest:
        errors = check_manifest(manifest, lock)
        for error in errors:
            print(error, file=sys.stderr)
        if errors:
            sys.exit(1)
        print(f"corpus manifest ok: {len(manifest['sources'])} sources")
        return
    cache_dir = os.getenv("CORPUS_CACHE")
    if args.offline and not cache_dir:
        parser.error("--offline needs CORPUS_CACHE from a previous run")
    cache_context = nullcontext(cache_dir) if cache_dir else tempfile.TemporaryDirectory(prefix="openmodbus-")
    rows_dir = args.dump_rows.expanduser().resolve() if args.dump_rows else None
    if rows_dir and rows_dir.is_relative_to(ROOT):
        parser.error("--dump-rows must name a directory outside the checkout")
    try:
        source_ids = select_sources(manifest, lock["sources"], args)
        if not source_ids:
            print("No corpus sources selected")
            return
        with cache_context as cache:
            build_catalog(source_ids, manifest["sources"], lock["sources"], Path(cache),
                          args.offline, args.write_catalog, rows_dir)
    except (CorpusError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
