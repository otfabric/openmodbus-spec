# OpenModbus — Proposal

**Status:** draft for agreement · **Date:** 2026-10-21 · **Repo:** `otfabric/openmodbus-spec`

OpenModbus is a vendor-neutral, machine-readable description of a Modbus device — what it exposes, how values are
encoded, what they mean, what may be written, and which constraints a client must respect — in the way OpenAPI
describes an HTTP API. It describes devices; it does not redefine Modbus.

This proposal builds on the earlier architecture review (kept for reference as the source of the layering and scope ideas)
and turns it into concrete, reviewable choices.

## 0. What I need from you

1. Go through the **16 decisions in §5**. Each has a recommendation; reply *accept*, *change to …*, or *discuss*.
   The ones that are hardest to reverse later are **D3 (scope), D5 (byte/word order), D6 (numeric model), D7 (structure), D8 (identifiers)**. Start there.
2. Confirm the **reference device set** (§9, M1). Real devices — ideally from your own fleet — expose gaps that invented ones cannot.
3. Answer the five questions in §11.

Once agreed, decisions are recorded as short ADRs in `docs/decisions/`, the draft is tagged `0.1.0-draft.1`, and tooling starts.

## 1. What is in this repository now

| Path | What |
|---|---|
| `spec/openmodbus-0.1-draft.md` | Normative-style draft: addressing, decode/encode pipeline, conversion, validity, constraints, writes, the 20+9 semantic validation rules. |
| `schema/0.1/contract.schema.json` | JSON Schema 2020-12 for the structure (validation level 1). |
| `examples/` | Three complete contracts for fictional devices: power meter, inverter with scale factors, I/O module. |
| `conformance/decode-vectors.yaml` | 47 language-neutral decode/encode test vectors. |

Checked so far: the schema is a valid 2020-12 schema; all three examples pass it and pass a prototype of the main level-2
rules (overlaps, references, table/type fit, forbidden ranges, write function fit); all 47 vectors decode and round-trip with an
independently written reference decoder. The prototype scripts are throwaway Python and not part of the repo; the real validator is the first tooling deliverable.

Testing already surfaced a real pitfall: in YAML 1.1 a bare `off` is the boolean `false`, which broke an enum named `off` in the inverter example (see D2).

## 2. Goals and non-goals

**Goals**

- One contract usable unchanged by a Go service, a Python script, a C# HMI, a simulator and a documentation generator.
- Correct by construction where Modbus is ambiguous: addressing base, byte/word order, scale factors, invalid markers, safe read ranges.
- Machine-checkable at four levels (structure → semantics → behaviour → real device).
- Small enough that a second language implementation is weeks, not months.
- A path to a community catalog of device contracts with provenance.

**Non-goals**

- Transport, connection management, polling engines, deployment config, credentials, SCADA orchestration.
- A programming language inside the contract (no scripts, no free-form expressions).
- A universal energy/industrial ontology. Points get stable identities and may *reference* external semantics (SunSpec, others).
- Modelling vendor control sequences in 0.x (explicitly deferred to a `commands` profile).

## 3. Prior art and positioning

| Project | What it is | Relation |
|---|---|---|
| [SunSpec models](https://github.com/sunspec/models) | Machine-readable (SMDX/JSON) models for DER devices, with scale factors, enums, repeating groups. | Closest in spirit and the best source of proven concepts. DER-only and tied to its own discovery chain. Plan: **import** as a profile, don't compete. |
| [W3C WoT Modbus binding](https://w3c.github.io/wot-binding-templates/bindings/protocols/modbus/index.html) | Vocabulary to describe Modbus access inside a Thing Description. | Per its own text: work in progress, Modbus TCP only, `entity`/`function`/`address`/`quantity`/`type`, byte/word flags, `pollingTime`; **no scale term**. Useful vocabulary, too thin for register maps. A TD *exporter* is a cheap future generator. |
| [Modbus Schema Toolkit](https://github.com/nielsbasjes/modbus-schema) (Niels Basjes) | A schema language for Modbus devices with Java tooling (Maven plugin, API adapters, SunSpec device generator); Apache-2.0. | The most direct competitor/ally I found. I have only read its repository front page, not the language. **Do this before freezing anything**: map the same devices in it and list what is lost (M0). If it already covers the need, extending it beats a new spec. |
| [evcc templates](https://github.com/evcc-io/evcc) | YAML device templates with Modbus addresses, types, decoders, scaling, some multi-step writes. | Large real-world corpus and a source of edge cases; application-specific. Candidate importer. |
| Modbus Monitor device maps (per the review; not verified by me) | JSON catalog with a published schema. | Shows demand for shareable maps. |

**Honest positioning:** nothing found is a *language-neutral, vendor-neutral contract plus conformance suite* that covers
non-energy devices. The open risk is that the Basjes toolkit is closer to that than I could verify, hence M0.

**Naming.** The repo is already `openmodbus-spec`. The review notes an existing "Open Modbus" project (open hardware/firmware);
a web search also lists a Gitee repository named "OpenModbus" (not examined). I could not load the GitHub organisation page to check either.
If the name matters for trademark or discoverability, a descriptive working title such as *Open Modbus Device Description (OMDD)* keeps
the repo name and avoids claiming the bare term. See D1.

## 4. Architecture

```
 device contract (YAML/JSON)          ← this repo: spec + schema + vectors + examples
        │  validate (L1 schema, L2 semantics)
        ▼
 canonical model (JSON, $refs resolved, repeats expanded, addresses absolute)
        │
        ├── runtime library: decode/encode, dependency resolution, read planner (per language)
        ├── generators (plugins): typed SDKs, docs, simulator config, TD export …
        ├── editor / importers
        └── conformance + device tests
        ▼
 transport adapters (go-modbus, pymodbus, …) → real devices / simulators
```

Three structural choices that shape everything else:

1. **The canonical model is the interface.** Runtimes and generators are specified against it, never against YAML text.
   That is what makes a third-party plugin in any language possible.
2. **Runtime first, generated code second.** A runtime that *interprets* a contract (`device.Read("ac_power")`) is the minimum
   viable product and is fully testable with the vectors. Generated typed SDKs are a thin facade over the runtime, not a second implementation of decoding.
3. **Constraints, not schedules.** The contract says what the device tolerates; the runtime plans reads (merging, splitting, caching scale factors).

### Repositories

| Repo | Contents | Notes |
|---|---|---|
| `openmodbus-spec` (this one) | spec, schema, vectors, examples, ADRs | language-neutral, no code except tiny scripts |
| `go-openmodbus` | model, loader, validator, codec/runtime, planner, `omb` CLI | follows the `go-modbus` / `go-sunspec` pattern; model package has no I/O dependency |
| `py-openmodbus` | second implementation: model + codec + runtime on pymodbus | the proof that the spec is language-neutral |
| `openmodbus-studio` | Wails v3 editor | same pattern as SunSpec Explorer / Trace Explorer |
| `openmodbus-devices` | catalog of contracts with CI | separate licence and provenance policy |

`go-modbus` supplies transports and the simulator server; `go-sunspec` becomes the SunSpec importer source;
`go-modbus-capture` data can seed a simulator's initial state (it stays raw and decoder-free, as you decided; a contract is what adds meaning on top).

## 5. Decisions to agree

Status of every row: **proposed**.

| # | Decision | Recommendation | Main alternative | Why |
|---|---|---|---|---|
| **D1** | Name, version key, file extension, CLI | Repo `openmodbus-spec`; top-level key `openmodbus: 0.1.0`; `*.omb.yaml/json`; CLI `omb`; descriptive subtitle "Device Contract". | Rename to *OMDD* | Mirrors `openapi: 3.1.0`; avoids claiming a contested bare name. |
| **D2** | Syntax | Authoring: YAML 1.2 Core, restricted to the JSON-compatible subset (no anchors, merge keys, tags). Interchange: JSON. Structure: JSON Schema 2020-12. | YAML with anchors; custom DSL; protobuf-style IDL | Editor support for free (LSP, SchemaStore); `$ref`/components replace anchors. Real pitfall found: `off`/`on`/`yes`/`no` are booleans in YAML 1.1 parsers. |
| **D3** | Scope | Device contract only: identity, points, encodings, access, constraints, variants. No deployment, no schedules, no scripts. Writes: parameters and controls, but no sequences in 0.x. | Include command workflows from the start | Smallest surface that is still useful; the review's central design test ("describes the device, does not prescribe how an application operates it") stays enforceable. |
| **D4** | Addressing | Zero-based PDU addresses + explicit table. Vendor notation only as a string annotation (`source.address`). | Allow 1-based/`4xxxx` modes | An ambiguity in the format becomes a bug in every client. Importers resolve notation once. |
| **D5** | Byte/word order | Two orthogonal axes, `byteOrder` and `wordOrder` (`big`/`little`), document default + per-point override. ABCD/CDAB names are docs only. | Enumerate `ABCD/BADC/CDAB/DCBA` (+ 64-bit variants) | Defined for any width (also 64-bit and strings) by two rules; one canonical spelling; no combinatorial enum. |
| **D6** | Numeric model | Raw typed decode → exact-decimal conversion (`raw × multiplier × 10^exponent10 + offset`) → one rounding to binary64. 64-bit ints > 2^53 are strings in interchange. `f32` is widened exactly. | Plain float64 arithmetic; tolerance-based tests | `2375 × 0.1` is not `237.5` in binary float in every language; a spec that tolerates this cannot have a cross-language conformance suite. Cost: implementers need decimal/big arithmetic (easy for decimal multipliers). |
| **D7** | Structure | Nested `groups` of `points`; a point has an absolute `address` or an `offset` from its group's base; static `repeat {count, stride, indexBase}`; reusable `components` with `$ref` (also cross-file). | Flat point list with explicit addresses only | Relative offsets are what make SunSpec models, repeated channels and shared vendor blocks expressible without copying thousands of lines. |
| **D8** | Identifiers | Lowercase `snake_case` ids, unique among siblings; vendor names in `aliases`; renaming an id is a breaking change. | Free-form names | Generators map to idiomatic names in any language from one neutral form; stable identity enables diffing and semantic links. |
| **D9** | Dependencies | Scale factors etc. by reference (`exponent10: {point: …}`), as a DAG with lexical scoping; `stability: constant|session|dynamic` tells runtimes how long a factor may be cached; failure ⇒ `invalid`, never a guess. | Implicit "next register" conventions | Statically checkable (existence, cycles, types); generalises SunSpec without inheriting its "scale factors are static" assumption. |
| **D10** | Read constraints | `constraints`: per-request limits, `gaps: forbid` by default, range policies (`forbidden`, `isolated`, `side_effects`, `safe_gap`), named safe `blocks`, `coherent` only if guaranteed, minimum request intervals. Planning strategy unspecified. | Prescribe read groups/polling | Safe by default; keeps scheduling in the application. |
| **D11** | Writes | Read-only unless declared; `write.safety: parameter|control`; `limits` (min/max/step/allowed); `verifyWith`; `idempotent`; `effect` text. Generated APIs make control writes explicit. | Single `writable` flag | Cheapest honest way to separate "set a label" from "curtail 5 MW", without modelling sequences yet. |
| **D12** | Extensibility | Unknown keys are errors except `x-<owner>-*`. Profiles (`sunspec@1`, later `commands`, `conditions`, `banks`, `discovery`) add `x-<profile>-*` keys and rules, never relax core rules. SunSpec starts as an *importer*, becomes a profile when the importer proves the mapping. | Open schema; or SunSpec as core dependency | Strictness keeps validators useful; the OpenAPI `x-` precedent is familiar. |
| **D13** | Semantics & units | Units are UCUM codes. Optional `semantics: [{scheme, id}]` links to external vocabularies; no built-in ontology. Sign conventions live in the external scheme or in descriptions for now. | Own ontology; free-text units | UCUM is machine-parsable; the semantic layer should be protocol-neutral and separate (also relevant for OPC UA / DNP3 later). |
| **D14** | Validation & conformance | Four levels (schema → 20 error/9 warning semantic rules with stable codes → vectors → device tests). A claim "conforms to OpenModbus 0.1" requires levels 1–3 for the relevant class. `omb diff` flags breaking changes. | Schema only | JSON Schema cannot detect overlaps, cycles or unsafe blocks; vectors are what make a second implementation credible. |
| **D15** | Governance & licensing | Spec, schema, vectors, tools: Apache-2.0. Catalog contracts: per-contract `info.license` (default CC0 or CC-BY-4.0 for facts-only maps), mandatory `info.source`/`verification`/`attribution`. Changes via short RFCs in `docs/rfcs/`; DCO sign-off. | CLA; single licence for everything | Matches OpenAPI/most OT ecosystems; separates tool licensing from vendor-documentation provenance. |
| **D16** | Implementation languages | Reference implementation and CLI in Go (static binaries for amd64/arm64/armv7 gateways); second implementation in Python; generators as out-of-process plugins consuming the canonical model JSON on stdin. | Single-language toolchain; JVM | Fits the OTFabric stack and your gateways; two languages from the start prevent Go-isms from leaking into the spec. |

### Smaller choices already made in the draft (flag any you dislike)

String decoding (NUL-terminated, trailing spaces trimmed); write rounding ties-away-from-zero; infinities treated like NaN (invalid);
`invalid` compared against the raw value *before* conversion; FC 23 unused; unknown enum values retained, not errors;
masks only on unsigned types; instance names `phase_1` with `indexBase`; contract `info.version` independent of firmware;
`transports`/`unitId` declare what the *device* supports, never what a site uses.

### Where this deliberately departs from the earlier review

- Byte/word order as two axes instead of an ABCD-style enum (D5).
- Exact-decimal numeric model made normative, because without it vectors cannot be exact (D6).
- Group-relative offsets in the core, not only arrays/strides, because SunSpec-style reusable models need them (D7).
- Default `gaps: forbid` and an explicit `safe_gap` policy, so unsafe merged reads cannot happen by omission (D10).
- Added WoT and the Basjes toolkit to the prior-art check, and made a bake-off against them a gate (M0).
- Codegen as plugins over the canonical model, with runtime interpretation first (§4, §8).

## 6. How a contract looks

A fragment of `examples/acme-sx5000-inverter.omb.yaml`:

```yaml
points:
  - { id: w_sf, address: 100, type: i16, stability: constant, label: Power scale factor }
  - id: ac_power
    address: 101
    type: i16
    conversion: { exponent10: { point: w_sf } }   # 2375 with w_sf = -1  →  237.5
    unit: W
    invalid: [-32768]
  - id: power_limit
    address: 300
    type: u16
    access: rw
    conversion: { multiplier: 0.1 }
    unit: "%"
    limits: { min: 0, max: 100, step: 0.1 }
    write: { functions: [6, 16], safety: control, verifyWith: power_limit_applied }
```

and a repeating block (`examples/acme-pm100-power-meter.omb.yaml`):

```yaml
groups:
  - id: phase
    address: 0
    repeat: { count: 3, stride: 6, indexBase: 1 }     # phase_1.voltage … phase_3.active_power
    points:
      - { id: voltage,      offset: 0, type: f32, unit: V }
      - { id: current,      offset: 2, type: f32, unit: A }
      - { id: active_power, offset: 4, type: f32, unit: W }
```

## 7. Validation architecture

| Level | Checks | Implemented by |
|---|---|---|
| 1 Structure | Required keys, types, enums, patterns | JSON Schema 2020-12 (any validator) |
| 2 Semantics | Overlaps (variant- and mask-aware), references, cycles, table/type/function fit, forbidden ranges, block safety, limits | `omb validate` |
| 3 Behaviour | Decode/encode vectors; later planner and error-handling vectors | each runtime's CI |
| 4 Reality | Contract vs simulator or real device (read every point, compare to expectations, report doc/firmware drift) | `omb test`, catalog CI |

Vectors are the second most important artifact after the prose: every runtime and every generator's output is tested against them.

## 8. Tooling plan

**`omb` CLI (Go)** — `validate`, `fmt`, `compile` (→ canonical model), `diff` (breaking-change detection, like oasdiff), `doc` (register tables in Markdown/HTML),
`gen`, `test`, `import`. One static binary; also usable as a library.

**Runtime libraries** — Go first, Python second. Decode/encode, dependency resolution, scale-factor caching by `stability`, read planning honouring `constraints`.
The planner is an interface; a simple correct one ships first, optimisation (batching, coalescing) comes after.

**Generators** — plugin protocol in the spirit of `protoc`: `omb gen --plugin ./gen-foo` pipes the canonical model JSON to the plugin and receives a list of files.
First-party: Go SDK, Python SDK, TypeScript SDK, documentation, simulator config. Later: C#, Rust, WoT Thing Description, Wireshark dissector hints.
Typed SDKs are facades over the runtime. Generated server skeletons expose the register mapping and serialisation only; device behaviour stays the implementer's job.

**Simulator** — a virtual device from a contract (initial values from `limits`/examples, optionally from a capture), served through `go-modbus`. Needed for level-4 tests and demos.

**Editor, in three steps**
1. *Schema-driven (days):* publish the schema to SchemaStore and document YAML language-server setup. Completion, hover and level-1 errors in VS Code/JetBrains with no custom software.
2. *`omb lint --lsp` (weeks):* level-2 diagnostics inline.
3. *Studio (months, Wails v3):* point table editor, group tree, live probe ("read this point from a device now and show raw words and decoded value"), import wizards, conflict view, doc preview.
   Local GUI plus CLI headless, as for your other apps.

**Importers** — SunSpec (SMDX/JSON → components + a profile), CSV/Excel register tables with an explicit addressing-notation step, evcc templates, pcap-derived hints via the trace-explorer engine.

**Catalog** — `openmodbus-devices` with CI (validate, diff vs previous release, simulator test), provenance (`source`: vendor/integrator/community/generated; `verification`: unverified/documented/simulated/device_tested), licence per contract, a takedown policy for vendor documentation concerns.

## 9. Roadmap

Sizes are relative effort: S ≈ days, M ≈ weeks, L ≈ a few months.

| Milestone | Deliverables | Exit criteria | Size |
|---|---|---|---|
| **M0 Agree** | Decisions D1–D16 resolved and recorded; prior-art bake-off (same 3 devices in the Basjes language and as WoT TDs; notes on gaps both ways). | ADRs merged; written go/no-go on "new spec vs extend existing". | S |
| **M1 Model proven on real devices** | Map ≥ 4 real devices: a meter, a complex vendor inverter, a SunSpec inverter, a non-energy I/O device. Revise spec/schema; grow vectors to ≥ 100 (add write encoding, arrays of strings, masks on 32-bit, error cases). | All four validate; no open question that would change the model; schema tagged `0.1.0-draft.n`. | M |
| **M2 Validator + runtime core** | `go-openmodbus`: loader, canonical model, `omb validate/compile/diff`, codec and dependency resolution passing 100% of vectors; `py-openmodbus` decoder passing the same vectors. | Two languages green on the same vectors in CI. | M–L |
| **M3 Generators + simulator** | Plugin protocol, Go/Python/TS/doc generators, simulator on `go-modbus`; `omb test` against simulator. | Generated SDKs read/write the simulator for all example contracts. | M |
| **M4 Editor, importers, catalog** | Schema-store integration, LSP diagnostics, SunSpec importer, Studio, `openmodbus-devices` with CI. | A third party can add a device contract by PR with green CI. | L |
| **1.0** | Freeze. | ≥ 10 devices from ≥ 5 vendors; two independent runtime implementations; no known breaking spec changes pending; at least one external reviewer outside OTFabric. | — |

Rule of thumb: do not freeze the schema before M1; do not start the editor before the validator.

## 10. Risks

| Risk | Mitigation |
|---|---|
| An existing format (Basjes toolkit) already covers the need | M0 gate; if so, contribute, extend, or interoperate through an importer instead. |
| Scope creep into command sequences, conditions, bank switching | Reserved profiles; core stays at "describes the device". Each addition needs an RFC with ≥ 2 real devices. |
| Decimal-exact conversion is a burden for implementers | Restricted to decimal literals and a power of ten; reference implementations in Go and Python with test vectors; fallback to IEEE-tolerance only through an RFC. |
| YAML parser differences (1.1 vs 1.2, duplicate keys, anchors) | Restricted subset, level-1 schema runs on the parsed JSON model, lint rule for risky scalars, test corpus of tricky YAML. |
| Vendor documentation copyright | Contracts record facts (addresses, types) with attribution; per-contract licence; takedown policy; vendor-authored contracts encouraged. |
| Adoption chicken-and-egg | Importers (SunSpec, evcc, CSV) seed the catalog; the simulator and docs generator make a contract valuable on day one even for a single user. |
| Documentation disagrees with firmware | Level-4 tests, `verification` and `testedWith` fields; contracts carry firmware ranges via variants. |
| Name clash | D1. |

## 11. Questions for you

1. Which **real devices** should anchor M1? (From your own deployments, if possible: a meter, a vendor inverter, a SunSpec inverter and an I/O or PLC module.)
2. Keep **"OpenModbus"** as the public name, or use a descriptive title (D1)?
3. Who is the **copyright holder and contributor policy** (OTFabric, individuals, employer): DCO or CLA (D15)?
4. Do you want the **Python implementation** inside the OTFabric org from day one (recommended, D16), and who would own it?
5. Is **exact-decimal conversion** (D6) acceptable as a hard requirement for conformance, or should the spec allow IEEE-tolerance mode?
