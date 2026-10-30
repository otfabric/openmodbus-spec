# AGENTS.md — openmodbus-spec

## What this is

A pre-0.1 draft of an open, machine-readable device contract for Modbus: specification, JSON Schema, three examples for fictional devices and language-neutral decode/encode vectors. Nothing is agreed yet, and nothing is implemented here. Profile: information-model.

## Organisation standards

This repository follows **otfabric/engineering policy 1.1**, profile **information-model** (`.otfabric/policy.yaml`). Remaining debt is in `.otfabric/baseline.yaml`. Where this file and the organisation standards disagree, this file wins for this repository; say so in your report.

## Where the truth lives

| Question | Source of truth |
|---|---|
| Goals and the decisions to agree (D1 to D16) | `docs/PROPOSAL.md` |
| Addressing, decoding, conversion, validation rules | `spec/openmodbus-0.1-draft.md` |
| Document structure | `schema/0.1/contract.schema.json` |
| Expected decode and encode results | `conformance/decode-vectors.yaml` |
| Wire behaviour of Modbus itself | the Modbus specification; never this repository |

## Hard rules

1. Never mark a decision as agreed: only the maintainer settles D1 to D16.
2. Never invent Modbus semantics, and never claim conformance or certification.
3. The specification, schema, examples and vectors change together.
4. Examples stay fictional devices.
5. No tooling beyond these checks: it belongs in the repositories `docs/PROPOSAL.md` names.
6. The licence is MIT (D15, the maintainer's decision); do not change it.

## Commands

| When you change… | Run |
|---|---|
| anything | `make check` |

`make check` is structural (`fmt-check`, `lint`, `test`): the schema is valid, the examples satisfy it, the YAML parses. It does not run the semantic rules or the vectors, which need an implementation.

## Definition of Done

- `make check` green.
- Spec, schema, examples and vectors agree.
- Failing or skipped steps reported explicitly.

## Git and releases

Work on a branch and open a PR. Do not push to `main` or create tags unless the maintainer asks for it in the session.
