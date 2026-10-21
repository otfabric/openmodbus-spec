# OpenModbus Device Contract Specification — 0.1 DRAFT

> **Status: draft for agreement.** Normative-style text for the parts that decide interoperability
> (addressing, decoding, conversion, validity, validation). Sections marked **[proposed]** are
> choices that need sign-off, see [`docs/PROPOSAL.md`](../docs/PROPOSAL.md) §5. Structure is in
> [`schema/0.1/contract.schema.json`](../schema/0.1/contract.schema.json); worked examples in
> [`examples/`](../examples); executable test cases in [`conformance/`](../conformance).

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted as in RFC 2119 / RFC 8174.

## 1. Scope

An OpenModbus **device contract** is a machine-readable description of what a Modbus device exposes and how to
interact with it correctly: its data points, their locations and encodings, their meaning, access rules,
and the constraints a client must respect.

A contract **describes the device. It does not describe a deployment or prescribe application behaviour.**
IP addresses, serial parameters, site unit IDs, credentials, polling schedules and control policy are out of scope.
OpenModbus does not redefine the Modbus protocol; it refers to the Modbus Application Protocol Specification
and the Modbus TCP/RTU implementation guides for everything on the wire.

Conformance classes:

| Class | Must |
|---|---|
| **Contract** | Validate at levels 1 and 2 (§9). |
| **Validator** | Implement level 1 and every level-2 rule marked *error*, with the stable codes in §9.2. |
| **Runtime** | Implement §4, §6, §7, §8 and pass all `conformance/` vectors. |
| **Generator** | Consume the canonical model (§3.3) and not alter the semantics of §6. |

## 2. Terminology

- **Table** — one of the four Modbus data tables: `coil`, `discrete_input`, `input_register`, `holding_register`.
- **Register / word** — a 16-bit unit of a register table. **Bit** — a unit of a coil or discrete-input table.
- **Point** — a logical, named value located in a table; may span several registers (e.g. a `u64`) or be a slice of one (`mask`).
- **Raw value** — the integer or float obtained by decoding the wire representation, before conversion.
- **Engineering value** — the raw value after conversion, in the point's `unit`.
- **Group** — a named collection of points and groups; may repeat at a fixed stride.
- **Variant** — a firmware/hardware subset to which points can be restricted.
- **Quality** — whether a decoded value is usable: `good` or `invalid` (§6.6).

## 3. Document model

### 3.1 Serialization

A contract is a single document, authored as YAML or JSON, using exactly the JSON data model
(objects, arrays, strings, numbers, booleans, null).

- YAML documents MUST be restricted to the JSON-compatible subset of **YAML 1.2 Core Schema**: no anchors,
  aliases, merge keys, custom tags or non-string keys. Reuse is provided by `components` and `$ref` (§5.5).
  **[proposed D2]**
- Consumers MUST NOT apply YAML 1.1 implicit typing. In particular the plain scalars `off`, `on`, `yes`, `no`, `y`, `n`
  are strings; authors SHOULD quote them anyway, because many parsers still read them as booleans
  (a real example is in `examples/acme-sx5000-inverter.omb.yaml`).
- Integers MAY be written in hexadecimal (`0x64`) in YAML; the canonical JSON form uses decimal.
- File extension: `.omb.yaml`, `.omb.yml`, `.omb.json`. **[proposed D1]**

### 3.2 Extensions

Unknown keys are errors, except keys beginning `x-`, which MUST be preserved by tools that rewrite documents and
MUST be ignored by consumers that do not understand them. Vendor and tool extensions SHOULD use
`x-<owner>-<name>`. Profiles (§10) reserve `x-<profile>-*`. **[proposed D12]**

### 3.3 Canonical model

Every conforming consumer MUST behave as if it first normalizes the document into the **canonical model**:
the JSON form with all `$ref`s resolved, `defaults` applied to every point, group `repeat`s expanded into
instances, and every address made absolute. Generators and runtimes are specified against this model, not against the YAML text.

## 4. Addressing

### 4.1 Address space

Addresses are **zero-based Modbus PDU addresses** (0–65535), exactly as carried in the request PDU, always qualified by a table.
Vendor notations (`40001`, `4x0001`, `400001`, 1-based offsets) MUST NOT appear in `address` or `offset`.
A contract MAY preserve them in `source.address` (a string) as documentation. Tools that import vendor documentation
are responsible for resolving the notation. **[proposed D4]**

### 4.2 Tables and function codes

| Table | Read | Write |
|---|---|---|
| `coil` | FC 01 | FC 05, FC 15 |
| `discrete_input` | FC 02 | — |
| `input_register` | FC 04 | — |
| `holding_register` | FC 03 | FC 06, FC 16, FC 22 |

Default protocol limits per request: FC 03/04 ≤ 125 registers; FC 16 ≤ 123 registers; FC 01/02 ≤ 2000 bits;
FC 15 ≤ 1968 bits. `constraints.max*` may lower them, never raise them.
FC 23 (read/write multiple registers) is not used by contracts in 0.1.

### 4.3 Width

| Type | Registers |
|---|---|
| `bool` | 1 bit (coil/discrete input only) |
| `u16`, `i16` | 1 |
| `u32`, `i32`, `f32` | 2 |
| `u64`, `i64`, `f64` | 4 |
| `string`, `bytes` | `registers` (required) |

A point with `count: n` occupies `n × width` consecutive addresses.

## 5. Points, groups and structure

### 5.1 Identifiers

`id` values match `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`, at most 64 characters, and are unique among siblings.
Vendor names go in `aliases`. An `id` is the stable identity of a point: renaming one is a **breaking change** of the contract
and requires a new major `info.version`. **[proposed D8]**

### 5.2 Locating a point

A point has exactly one of `address` (absolute) or `offset` (relative to the base `address` of the nearest enclosing group
that declares one). The table is the point's `table`, else the nearest enclosing group's, else `defaults.table`.

### 5.3 Repeating groups

`repeat: { count, stride, indexBase }` creates `count` instances of the group. Instance *i* has base `address + i × stride`.
Instances appear in the canonical model as `<id>_<indexBase + i>` (`phase_1`, `phase_2`, …) and instance points as
`phase_1.voltage`. Instances MUST NOT overlap (E002).
Repeat counts are static in 0.1; counts read from a register are reserved for a later profile.

### 5.4 Reference resolution

References (`conversion.exponent10.point`, `write.verifyWith`) are dotted paths resolved **lexically**: first among the
siblings of the referring point, then among the siblings of its group, then outwards to the document root. Within a repeated group
a reference to a sibling resolves to the same instance. The reference graph MUST be acyclic (E006).

### 5.5 Components and `$ref`

`components.enums`, `components.flagSets` and `components.groups` hold reusable definitions. A `$ref` is a
JSON-Pointer-style URI reference, local (`#/components/enums/x`) or to another file (`common.omb.yaml#/components/groups/ac`).
A group entry of the form `{ $ref, id, address, … }` instantiates the component group; sibling keys override the component's.
**[proposed D7]**

### 5.6 Variants

`variants` declares named firmware/hardware subsets. A point or group with `variants: [a, b]` exists only on those variants;
without the key it exists on all of them. Points MAY occupy the same addresses if their variant sets are disjoint.

## 6. Decoding and encoding

This section is the heart of interoperability and is tested by `conformance/decode-vectors.yaml`.

### 6.1 Byte and word order **[proposed D5]**

Two orthogonal axes, both defaulting to `big`:

- `byteOrder` — order of the two bytes **inside each 16-bit register**. `big`: high byte first (the Modbus wire convention).
- `wordOrder` — order of the **registers** of a multi-register value. `big`: first register is most significant.

Decoding normalizes to a big-endian byte string: (1) reverse the register list if `wordOrder` is `little`;
(2) swap the two bytes of every register if `byteOrder` is `little`; (3) interpret the bytes as big-endian two's-complement
integer or IEEE-754 float of the point's width. Encoding is the exact inverse.

| Common name | `wordOrder` | `byteOrder` | 0x12345678 on the wire |
|---|---|---|---|
| ABCD | big | big | `1234 5678` |
| CDAB | little | big | `5678 1234` |
| BADC | big | little | `3412 7856` |
| DCBA | little | little | `7856 3412` |

The letter names are documentation only and never appear in a contract (one canonical spelling).
`byteOrder` and `wordOrder` may be set in `defaults` or per point; the point wins.

### 6.2 Types

Integers are two's complement. `f32`/`f64` are IEEE-754 binary32/binary64.
`string` is the bytes obtained after §6.1 normalization, interpreted as ASCII (UTF-8 if every byte is valid UTF-8),
terminated at the first NUL byte, with trailing 0x20 padding removed. **[proposed]**
`bytes` is returned as-is. Strings and bytes are read-only in 0.1.

### 6.3 Masks

For `u16`, `u32`, `u64` only: `value = (raw & mask) >> trailing_zeros(mask)`. The mask MUST be one contiguous run of ones (E010).
Several points may share a register if their masks are disjoint.

### 6.4 Conversion **[proposed D6]**

```
engineering = raw × multiplier × 10^exponent10 + offset
```

`multiplier` (default 1) and `offset` (default 0) are **decimal literals**, `exponent10` an integer or a reference to a point
whose decoded engineering value is an integer (the SunSpec scale-factor pattern).

The result MUST be computed as if with exact decimal arithmetic and rounded **once** to the nearest binary64 (ties to even)
when a binary64 is required. Implementations MUST NOT compute `raw * 0.1` in binary floating point and accept the result.
Integer-typed raws that exceed 2^53 and have no conversion MUST remain exact; interchange formats MUST carry them as strings.

Conversion does not apply to `bool`, `string`, `bytes`, enumerations or flag sets (E011).

`f32` raw values are widened exactly to binary64 before any further processing (see vector `f32-widening`).

### 6.5 Enumerations and flags

An enumeration maps raw integers to identifiers. **Unknown raw values are not errors**: the value is retained, no name is produced.
Flags name individual bits (or bit ranges via `width`); undefined set bits remain in `value` and are not named.

### 6.6 Validity and quality **[proposed]**

Every decoded value carries a quality, `good` or `invalid`. A value is `invalid` and its engineering value is absent when:

1. its raw value (after mask, **before** conversion) is listed in `invalid`;
2. it is a float and not finite (NaN, ±∞);
3. a point it depends on (§5.4) is itself `invalid` or could not be read.

A dependency failure MUST yield `invalid`, never a value computed with a guessed or stale factor.
Runtimes MAY additionally report transport-level states (timeout, exception response) outside the contract's quality model.

### 6.7 Encoding for writes

Writing inverts §6.1–6.4: check `limits` on the engineering value, apply the inverse conversion, round the raw value to the
nearest integer (ties away from zero) **[proposed]**, apply the mask (a masked write is a read-modify-write that
a runtime MUST NOT perform with FC 06/16 unless the whole register is owned by the contract; FC 22 is preferred), order the bytes.
A value that does not map to an integer raw within the type's range MUST be rejected, not clamped.

## 7. Reading constraints

`constraints` states facts about the device; it is not a schedule.

- `max*` — per-request limits (§4.2 defaults apply when absent).
- `gaps` — whether a merged read may span addresses no point defines. **Default `forbid`**.
- `ranges[].policy`:
  `forbidden` never read or write; `isolated` only as a request of exactly that range;
  `side_effects` reading changes device state, read only on explicit request;
  `safe_gap` undefined but safe to include in merged reads.
- `blocks` — named ranges known to be safe as one request. `coherent: true` only if the vendor guarantees atomic sampling;
  runtimes MUST NOT assume atomicity otherwise.
- `minRequestIntervalMs` — minimum spacing between requests to the device; point `minReadIntervalMs` — do not read that
  point faster. Both are device limits, not recommendations of an application.

A **runtime** builds its read plan from the requested points, their dependencies and these constraints.
The planning strategy is deliberately unspecified.

## 8. Writing

- A point is read-only unless `access` is `w` or `rw` (or the document default says so). Writes to `input_register`/`discrete_input` are errors (E008).
- `write.safety` is `parameter` (configuration) or `control` (changes physical behaviour). Default: `parameter`.
  Generated APIs MUST make `control` writes explicit (distinct call or confirmation) and MUST NOT expose them in "bulk write all" operations. **[proposed D11]**
- `write.verifyWith` names a point to read back; `idempotent` says whether repeating the write is safe.
- Multi-step procedures (unlock keys, enable-then-set, mode changes) are **not** modelled in 0.1.
  Authors describe them in `write.effect`/`description`. A declarative command profile is reserved.
- Sequences of writes are not transactional; no part of this specification implies atomicity.

## 9. Validation

### 9.1 Levels

| Level | What | Who |
|---|---|---|
| 1 | Structure: JSON Schema 2020-12 (`schema/0.1/contract.schema.json`). | any JSON Schema validator |
| 2 | Semantics: the rules in §9.2. | OpenModbus validator |
| 3 | Behaviour: `conformance/` vectors. | runtimes, generators |
| 4 | Reality: contract vs. a real/simulated device. | integration tests, catalog CI |

### 9.2 Level-2 rules **[proposed D14]**

Codes are stable; text may improve.

| Code | Sev | Rule |
|---|---|---|
| E001 | error | Duplicate `id` among siblings (points, groups, flags, enum values/names, variants, blocks). |
| E002 | error | Two points overlap in the same table at a shared address, unless their variant sets are disjoint or their masks are disjoint. Applies to expanded repeats. |
| E003 | error | Any address, `offset + width × count`, or repeat extent outside 0–65535. |
| E004 | error | Type/table mismatch: `bool` only on `coil`/`discrete_input`; all other types only on register tables. |
| E005 | error | Unresolved reference: `$ref`, `exponent10.point`, `verifyWith`, `variants` ids. |
| E006 | error | Cycle in the dependency graph. |
| E007 | error | `exponent10.point` target is not an integer-typed point, or has `enum`, `flags` or a `conversion`. |
| E008 | error | Writable point on a read-only table; `write` on a read-only point. |
| E009 | error | `write.functions` incompatible with table or width (FC 05 only for coil; FC 06 only for single-register points; FC 15 only for coil; FC 16 for register tables; FC 22 only for u16 on holding registers). |
| E010 | error | `mask` on a non-unsigned type, wider than the type, zero, or non-contiguous. |
| E011 | error | `conversion` on `bool`, `string`, `bytes`, or on a point with `enum`/`flags`. |
| E012 | error | `limits`: min > max, step ≤ 0, `allowed` outside min/max, or values outside the type's range after inverse conversion. |
| E013 | error | Enum value outside the raw type's range or duplicated; flag bit outside the type's width or overlapping flags. |
| E014 | error | `registers` missing for `string`/`bytes`, or `count × width` inconsistent with an explicit `registers`. |
| E015 | error | `offset` used with no enclosing group base `address`, or `repeat` on a group without `address`. |
| E016 | error | A point lies, even partly, in a `forbidden` range; or a `block` overlaps one. |
| E017 | error | A `block` exceeds the request limits, or contains addresses that no point defines when `gaps` is `forbid` and no `safe_gap` covers them. |
| E018 | error | `invalid` value outside the raw type's range. |
| E019 | error | Point or group references a variant that is not declared; `variants` declared but unused is W008. |
| E020 | error | Cycle among component `$ref`s. |
| W001 | warn | Numeric point without `unit`. |
| W002 | warn | Writable numeric point without `limits`. |
| W003 | warn | `control` write without `verifyWith`. |
| W004 | warn | Point without `label` or `description`. |
| W005 | warn | Referenced scale-factor point is not `stability: constant` or `session`. |
| W006 | warn | `unit` is not a valid UCUM code. |
| W007 | warn | `info.verification` is `device_tested` but `testedWith` is empty. |
| W008 | warn | Declared variant or component never used. |
| W009 | warn | `deprecated` point without a replacement noted in `description`. |

Validators SHOULD emit machine-readable diagnostics (code, severity, JSON Pointer to the offending node, message).

## 10. Profiles and versioning

- `openmodbus: 0.1.x` names the specification version. Before 1.0 every minor release MAY break compatibility; patch releases MUST NOT.
  From 1.0, semantic versioning applies to the specification and to the schema.
- `info.version` is the revision of the contract itself. It MUST increase on any change and MUST increase the major number
  when an `id` is renamed/removed, an address or type changes, or a unit/conversion changes.
- A **profile** (`profiles: [sunspec@1]`) adds keys (prefixed `x-<profile>-`) and rules, never relaxes core rules.
  Planned profiles: `sunspec` (import of SunSpec models; runtime discovery of the model chain), `commands` (declarative multi-step writes),
  `conditions` (declarative conditional conversion/availability), `banks` (bank/page selectors), `discovery` (matching rules beyond FC 43/14).

## 11. Reserved for later

Dynamic repeat counts (count read from a register); conditional conversion and availability (`when`); command workflows;
bank/page switching; BCD, timestamp and structured types; protocol-neutral semantic layer; device-identification matching beyond FC 43/14;
exception-response semantics per range. None of these may be emulated with `x-` keys in a way that changes the meaning of core keys.
