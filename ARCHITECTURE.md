# Architecture

This repository is a set of documents and has no runtime. Who decides what:

```
docs/PROPOSAL.md              goals and decisions D1 to D16
        │
spec/openmodbus-0.1-draft.md  addressing, decoding, conversion, validity, validation rules
        │
        ├── schema/0.1/contract.schema.json   document structure (JSON Schema 2020-12)
        ├── examples/*.omb.yaml               three contracts for fictional devices
        ├── conformance/decode-vectors.yaml   expected decode and encode results
        ├── devices/                         reviewed device contracts
        └── corpus/                          vendor provenance and source checks
```

The specification, schema, examples and vectors change together. Wire behaviour of Modbus itself comes from the Modbus specification, never from here.

## Checks

`scripts/validate.py`, through `make check`:

| Command | Checks |
|---|---|
| `fmt` | text files use LF, end in a newline, have no trailing whitespace |
| `lint` | the schema is valid JSON Schema 2020-12; YAML files parse |
| `test` | every example and device contract validates against the schema |

Nothing here reads the vectors against an implementation.

## Versioning

The schema lives under its version (`schema/0.1/`). Versioning rules are in section 10 of the specification.

## Tooling

The [corpus runner](corpus/README.md) checks reviewed mappings against vendor files stored outside the checkout.
Runtime and editor tooling lives in the repositories the proposal plans: `go-openmodbus`, `py-openmodbus` and `openmodbus-studio`.
