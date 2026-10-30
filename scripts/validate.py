#!/usr/bin/env python3
"""Structural checks of the draft: schema, examples and conformance vectors.

  validate.py fmt    text files use LF, end in a newline, no trailing whitespace
  validate.py lint   the schema is valid JSON Schema 2020-12; YAML files parse
  validate.py test   every example validates against the schema

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
VECTORS = ROOT / "conformance/decode-vectors.yaml"
TEXT_DIRS = ("conformance", "docs", "examples", "schema", "spec")


def check_fmt():
    errors = []
    for directory in TEXT_DIRS:
        for path in sorted((ROOT / directory).rglob("*")):
            if not path.is_file():
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
    for path in [*EXAMPLES, VECTORS]:
        try:
            yaml.safe_load(path.read_text())
        except yaml.YAMLError as err:
            errors.append(f"{path.relative_to(ROOT)}: {err}")
    return errors


def check_test():
    errors = []
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()))
    if not EXAMPLES:
        errors.append("examples: no *.omb.yaml files")
    for path in EXAMPLES:
        document = yaml.safe_load(path.read_text())
        for err in validator.iter_errors(document):
            where = "/".join(str(part) for part in err.absolute_path)
            errors.append(f"{path.relative_to(ROOT)}: {where}: {err.message}")
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
