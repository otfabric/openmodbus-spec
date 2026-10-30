# Security Policy

This repository holds a draft specification, a JSON Schema, example documents and test vectors. It has no network runtime, and no supported release: nothing has been released.

## Reporting

Do not open a public issue for a security problem. Email **security@otfabric.io**, or open a private advisory on the repository's GitHub Security tab, with a description, the affected file and the possible impact.

## What is in scope

- A rule of the draft that would make a conforming implementation unsafe, for example around writes (specification section 8) or input limits.
- `scripts/validate.py` and its pinned dependencies in `scripts/requirements.txt`, which run only in checks. `make vuln` audits those dependencies with pip-audit.

## What a contract must not hold

A contract describes the device, not the deployment: no IP addresses, serial parameters, polling schedules or credentials (specification section 1). Treat a contract from an unknown source as untrusted input. Examples in this repository are fictional devices.
