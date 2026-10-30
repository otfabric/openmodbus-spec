# Contributing

## Before you start

The draft is not agreed. [docs/PROPOSAL.md](docs/PROPOSAL.md) holds the decisions D1 to D16: propose changes to them there, in an issue or a pull request. Only the maintainer settles a decision.

## Prerequisites

Python 3 and network access for the first run: the Makefile creates `.venv` from `scripts/requirements.txt`.

## Workflow

1. Work on a branch and open a pull request. Nothing goes directly to `main`.
2. Change the specification, schema, examples and vectors together, so that they agree.
3. Run `make check` (`fmt-check`, `lint`, `test`). It is structural: it does not run the semantic rules or the vectors, which need an implementation. Say so in the pull request if your change depends on them.

## Rules

- Never invent Modbus semantics: wire behaviour is defined by the Modbus specification, never here.
- Never claim conformance or certification.
- Examples stay fictional devices.
- No tooling beyond the checks in `scripts/`: it belongs in the repositories the proposal names.
- Agents follow [AGENTS.md](AGENTS.md).
