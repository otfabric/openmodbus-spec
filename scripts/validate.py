#!/usr/bin/env python3
"""Structural checks of the draft, examples, device contracts and corpus metadata.

  validate.py fmt    text files use LF, end in a newline, no trailing whitespace
  validate.py lint   the schema is valid JSON Schema 2020-12; YAML files parse
  validate.py test   examples and device contracts validate against the schema

This does not implement the semantic validation rules of the draft: those
belong to the tooling repositories (docs/PROPOSAL.md, section 4).
"""
import json
import pathlib
import sys

import jsonschema
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema/0.1/contract.schema.json"
EXAMPLES = sorted((ROOT / "examples").glob("*.omb.yaml"))
DEVICES = sorted((ROOT / "devices").rglob("*.omb.yaml"))
VECTORS = ROOT / "conformance/decode-vectors.yaml"
CORPUS_METADATA = sorted((ROOT / "corpus").glob("*.yaml"))
TEXT_DIRS = ("conformance", "corpus", "devices", "docs", "examples", "schema", "spec")


def check_fmt():
    errors = []
    for directory in TEXT_DIRS:
        for path in sorted((ROOT / directory).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            data = path.read_bytes()
            name = path.relative_to(ROOT)
            if b"\r" in data:
                errors.append(f"{name}: CR line ending")
            if data and not data.endswith(b"\n"):
                errors.append(f"{name}: no final newline")
            for number, line in enumerate(data.split(b"\n"), 1):
                if line != line.rstrip():
                    errors.append(f"{name}:{number}: trailing whitespace")
    return errors


def check_lint():
    errors = []
    try:
        schema = json.loads(SCHEMA.read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
    except (ValueError, jsonschema.SchemaError) as err:
        errors.append(f"{SCHEMA.relative_to(ROOT)}: {err}")
    for path in [*EXAMPLES, *DEVICES, *CORPUS_METADATA, VECTORS]:
        try:
            yaml.safe_load(path.read_text())
        except yaml.YAMLError as err:
            errors.append(f"{path.relative_to(ROOT)}: {err}")
    return errors


def contract_validator():
    return jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()))


def validate_contract(validator, document, path):
    return [
        f"{path}: {'/'.join(str(part) for part in err.absolute_path)}: {err.message}"
        for err in validator.iter_errors(document)
    ]


def check_test():
    if not EXAMPLES:
        return ["examples: no *.omb.yaml files"]
    errors = []
    validator = contract_validator()
    for path in [*EXAMPLES, *DEVICES]:
        document = yaml.safe_load(path.read_text())
        errors.extend(validate_contract(validator, document, path.relative_to(ROOT)))
    return errors


def main():
    checks = {"fmt": check_fmt, "lint": check_lint, "test": check_test}
    if len(sys.argv) != 2 or sys.argv[1] not in checks:
        sys.exit(f"usage: {sys.argv[0]} {{fmt|lint|test}}")
    errors = checks[sys.argv[1]]()
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        sys.exit(1)
    print(f"{sys.argv[1]} ok")


if __name__ == "__main__":
    main()
