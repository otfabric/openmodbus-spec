# openmodbus-spec

An open, vendor-neutral, machine-readable **device contract** for Modbus: what a device exposes, how values are encoded and
scaled, what they mean, what may be written, and which constraints a client must respect. Think OpenAPI, but for Modbus devices.

> **Status: v0.1.0 draft, not yet agreed.** Start with [`docs/PROPOSAL.md`](docs/PROPOSAL.md).

| Path | What |
|---|---|
| [`docs/PROPOSAL.md`](docs/PROPOSAL.md) | Goals, prior art, the 16 decisions to agree, tooling plan, roadmap, risks. |
| [`spec/openmodbus-0.1-draft.md`](spec/openmodbus-0.1-draft.md) | Draft specification: addressing, decoding/encoding, conversion, validity, constraints, writes, validation rules. |
| [`schema/0.1/contract.schema.json`](schema/0.1/contract.schema.json) | JSON Schema 2020-12 for the document structure. |
| [`examples/`](examples) | Three complete contracts for fictional devices (power meter, inverter with scale factors, I/O module). |
| [`conformance/decode-vectors.yaml`](conformance/decode-vectors.yaml) | Language-neutral decode/encode test vectors. |

## At a glance

```yaml
openmodbus: 0.1.0
info:   { id: acme/pm100, title: Acme PM-100 power meter, version: 0.1.0 }
device: { manufacturer: Acme Metering, model: PM-100 }
defaults: { table: input_register, wordOrder: little, byteOrder: big }
points:
  - { id: frequency, address: 20, type: f32, unit: Hz }
  - id: power_factor
    address: 30
    type: i16
    conversion: { multiplier: 0.001 }
    invalid: [-32768]
```

A contract describes the device, not the deployment: no IP addresses, serial settings, polling schedules or credentials.

## Planned layout

Tooling lives in separate repositories (see the proposal, §4): `go-openmodbus` (model, validator, runtime, `omb` CLI),
`py-openmodbus`, `openmodbus-studio` (editor), `openmodbus-devices` (catalog).

## Licence

MIT for the specification, schema, vectors and tools (decision D15, maintainer, 2026-10-30): see [LICENSE](LICENSE).
