# Limitations

## Status

- **Pre-0.1 draft, not agreed.** Sections marked **[proposed]** need sign-off, and the decisions in [docs/PROPOSAL.md](docs/PROPOSAL.md) are open, except the licence (D15). Nothing has been released and the repository has no tags: expect breaking changes.
- **Nothing is certified**, and no conformance claim is made. The conformance classes in section 1 of the specification are definitions, not results.

## What has not been verified

- **No implementation is run here.** `make check` is structural: the schema is valid, the examples satisfy it, the YAML parses.
- The semantic validation rules (section 9) are not executed.
- The vectors in `conformance/decode-vectors.yaml` are not executed.
- The examples describe fictional devices. No contract in this repository has been checked against a real device.

## Scope

- A contract describes a device, not a deployment: no IP addresses, serial parameters, unit IDs of a site, credentials, polling schedules or control policy.
- OpenModbus does not redefine Modbus.
- Items in section 11 of the specification are reserved for later.
