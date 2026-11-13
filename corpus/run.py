#!/usr/bin/env python3
"""Extract and verify catalog contracts from checksum-pinned vendor sources."""
import argparse
import csv
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from decimal import Decimal
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate import ROOT, contract_validator, validate_contract


class CorpusError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise CorpusError(message)


def read_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def verify(data, lock, origin):
    require(len(data) == lock["size"], f"{origin}: byte size differs from lock")
    actual = hashlib.sha256(data).hexdigest()
    require(actual == lock["sha256"], f"{origin}: SHA-256 differs from lock ({actual})")


def read_source(path, lock):
    with path.open("rb") as source:
        data = source.read(lock["size"] + 1)
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
            with build_opener(HTTPSRedirects()).open(url, timeout=20) as response:
                data = response.read(lock["size"] + 1)
            verify(data, lock, url)
        except (CorpusError, OSError) as exc:
            failures.append(str(exc))
            continue

        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as staging:
            temp_path = Path(staging) / "source"
            with temp_path.open("wb") as temp:
                temp.write(data)
            temp_path.replace(path)
        return data

    raise CorpusError("No vendor URL returned the locked source: " + " | ".join(failures))


def extract_victron(data):
    point_ids = {
        "/Dc/Battery/Voltage": "battery_voltage",
        "/Dc/Battery/Current": "battery_current",
        "/Dc/Battery/Power": "battery_power",
        "/Dc/Battery/Soc": "battery_state_of_charge",
    }
    points = {}
    rows = csv.reader(io.StringIO(data.decode("utf-8"), newline=""))
    for service, path, _, raw_unit, address, raw_type, divisor, access in rows:
        if service != "com.victronenergy.system" or path not in point_ids:
            continue
        require(path not in points, f"Duplicate Victron point {path}")
        require(access == "R", f"Unexpected Victron access for {path}: {access}")
        point = {
            "id": point_ids[path],
            "address": int(address),
            "type": {"uint16": "u16", "int16": "i16"}[raw_type],
            "unit": {"V DC": "V", "A DC": "A", "W": "W", "%": "%"}[raw_unit],
        }
        if Decimal(divisor) != 1:
            multiplier = Decimal(1) / Decimal(divisor)
            encoded = float(multiplier)
            require(Decimal(str(encoded)) * Decimal(divisor) == 1, f"{path}: scale needs review")
            point["conversion"] = {"multiplier": encoded}
        point["source"] = {"address": address, "reference": f"attributes.csv:{rows.line_num}"}
        points[path] = point
    require(points.keys() == point_ids.keys(), f"Missing Victron rows: {sorted(point_ids.keys() - points.keys())}")
    return sorted(points.values(), key=lambda point: point["address"])


def extract_eastron(data):
    result = subprocess.run(
        ["pdftotext", "-f", "5", "-l", "5", "-enc", "UTF-8", "-layout", "-", "-"],
        input=data, capture_output=True, check=True, timeout=20,
    )
    page = result.stdout.decode("utf-8")
    require(re.search(r"Function code\s+04\s+to read input parameters", page, re.IGNORECASE),
            "Eastron PDF page 5: input register table header missing")
    selected = {
        "Voltage": ("voltage", "Volts", "V"),
        "Current": ("current", "Amps", "A"),
        "Active power": ("active_power", "Watts", "W"),
        "Frequency": ("frequency", "Hz", "Hz"),
        "Import active energy": ("import_active_energy", "kWh", "kW.h"),
    }
    rows = re.findall(
        r"^[ \t]*(3\d{4})[ \t]+([^\n]+?)[ \t]+(\d+)[ \t]+(\S+)[ \t]+(\w+)[ \t]+"
        r"([0-9A-F]{2})[ \t]+([0-9A-F]{2})[ \t]*$",
        page, re.MULTILINE,
    )
    points = {}
    for reference, label, size, raw_unit, kind, high, low in rows:
        label = " ".join(label.split())
        if label not in selected:
            continue
        point_id, expected_unit, unit = selected[label]
        require(point_id not in points, f"Duplicate Eastron point {point_id}")
        address = int(high + low, 16)
        require(int(reference) - 30001 == address and address % 2 == 0,
                f"Eastron {label}: conflicting register addresses")
        require((size, raw_unit, kind) == ("4", expected_unit, "Float"),
                f"Eastron {label}: unexpected width, unit or encoding")
        points[point_id] = {
            "id": point_id,
            "address": address,
            "type": "f32",
            "unit": unit,
            "source": {"address": reference, "page": 5, "reference": "Input register map"},
        }
    missing = {point_id for point_id, _, _ in selected.values()} - points.keys()
    require(not missing, f"Missing Eastron rows: {sorted(missing)}")
    return sorted(points.values(), key=lambda point: point["address"])


def build_contract(source_id, source, points):
    return {
        "openmodbus": "0.1.0",
        "info": {
            **source["info"],
            "source": "integrator",
            "verification": "documented",
            "x-otfabric-corpus-source": source_id,
        },
        "device": {
            **source["device"],
            "documentation": [{
                "title": source["title"],
                "url": source.get("documentation_url", source["download_urls"][0]),
                "revision": source["revision"],
            }],
        },
        "defaults": source["defaults"],
        "points": points,
    }


def verify_contract(validator, document, path):
    errors = validate_contract(validator, document, path)
    require(not errors, "\n".join(errors))
    # The pilot emits flat, scalar, read-only register maps.
    widths = {"i16": 1, "u16": 1, "f32": 2}
    require(document["defaults"]["table"] in ("holding_register", "input_register")
            and document["defaults"]["access"] == "r", "Expected a read-only register table")
    ids = set()
    occupied = set()
    for point in document["points"]:
        point_id = point["id"]
        width = widths[point["type"]]
        addresses = set(range(point["address"], point["address"] + width))
        require(point_id not in ids, f"{point_id}: duplicate point ID")
        require(max(addresses) <= 65535, f"{point_id}: register range exceeds address space")
        require(not occupied & addresses, f"{point_id}: register range overlaps another point")
        ids.add(point_id)
        occupied.update(addresses)


def build_catalog(source_ids, sources, lock, cache, offline, write):
    extractors = {
        "victron-cerbo-gx-system": extract_victron,
        "eastron-sdm120-modbus": extract_eastron,
    }
    validator = contract_validator()
    catalog = {}
    contract_ids = set()
    devices = ROOT / "devices"
    for source_id in source_ids:
        try:
            source = sources[source_id]
            pin = lock[source_id]
            require(re.fullmatch(r"[a-f0-9]{64}", pin["sha256"]), "Invalid SHA-256 in source lock")
            require(type(pin["size"]) is int and pin["size"] > 0, "Invalid byte size in source lock")
            path = (ROOT / source["contract"]).resolve()
            require(path.is_relative_to(devices) and path.name.endswith(".omb.yaml"),
                    "Contract path must be a .omb.yaml under devices/")
            require(path not in catalog, f"Duplicate catalog path: {path.relative_to(ROOT)}")
            data = cached_source(source, pin, cache, offline)
            document = build_contract(source_id, source, extractors[source_id](data))
            verify_contract(validator, document, path.relative_to(ROOT))
            contract_id = document["info"]["id"]
            require(contract_id not in contract_ids, f"Duplicate catalog ID: {contract_id}")
            contract_ids.add(contract_id)
            if not write:
                require(path.is_file() and read_yaml(path) == document,
                        f"{path.relative_to(ROOT)} differs from extraction. "
                        "Run with --write-catalog and review the diff.")
            catalog[path] = document
            print(f"{source_id}: extracted and verified {len(document['points'])} points")
        except (CorpusError, OSError, KeyError, ValueError, yaml.YAMLError, subprocess.SubprocessError) as exc:
            raise CorpusError(f"{source_id}: {exc}") from exc

    if write:
        for path, document in catalog.items():
            content = yaml.safe_dump(document, sort_keys=False)
            if path.is_file() and path.read_text(encoding="utf-8") == content:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=path.parent) as staging:
                temp = Path(staging) / path.name
                temp.write_text(content, encoding="utf-8")
                temp.replace(path)
    print(f"Catalog {'built' if write else 'verified'}: {len(catalog)} contracts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", default="pilot", dest="source_set")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--write-catalog", action="store_true")
    args = parser.parse_args()
    manifest = read_yaml(ROOT / "corpus/sources.yaml")
    lock = read_yaml(ROOT / "corpus/sources.lock.yaml")
    if manifest.get("version") != 1 or lock.get("version") != 1:
        parser.error("unsupported corpus manifest or lock version")
    if args.source_set not in manifest["sets"]:
        parser.error(f"unknown corpus set {args.source_set!r}")
    cache_dir = os.getenv("CORPUS_CACHE")
    if args.offline and not cache_dir:
        parser.error("--offline needs CORPUS_CACHE from a previous run")
    cache_context = nullcontext(cache_dir) if cache_dir else tempfile.TemporaryDirectory(prefix="openmodbus-")
    try:
        with cache_context as cache:
            build_catalog(manifest["sets"][args.source_set], manifest["sources"], lock["sources"],
                          Path(cache), args.offline, args.write_catalog)
    except (CorpusError, OSError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
