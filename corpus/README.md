# Vendor corpus

The [manifest](sources.yaml) lists public vendor documents. Each source records
the publisher, title, edition where available, direct public download URLs, the
format, the extractor module in [extractors/](extractors/), and the contracts it
produces. The [source lock](sources.lock.yaml) pins each download's size and
SHA-256. Source files are temporary inputs and never enter the checkout. The
reviewed OpenModbus YAML in [devices/](../devices/) is the catalog.

## Verify or rebuild

PDF extraction needs Poppler's `pdftotext` and `pdfinfo`.

```sh
make corpus                                   # the pilot set
make corpus CORPUS_SET=all                    # every source
make corpus CORPUS_ARGS="--source brainboxes-ed-tables --write-catalog"
```

Each run downloads the locked sources, checks size and SHA-256, runs the
extractor, builds the contracts, validates them against the draft schema and
checks the corpus rules: read-only flat points, type and table agree, address
bounds, overlaps (mask-aware), conversion placement, scale-factor references,
UCUM spellings. Without `--write-catalog` it compares each contract with the
checked-in YAML. With it, it writes changed or missing contracts. Every source is
attempted and all failures are reported together. Review the YAML diff before
committing it.

`make check` runs `corpus/run.py --check-manifest`: an offline check that every
source has a lock entry and an extractor, every contract file exists, and every
`devices/` contract comes from a corpus source. It never downloads. It also runs
`corpus/roster.py --check` (see [Roster](#roster)).

## Extractors

An extractor is `corpus/extractors/<name>.py` with `extract(data, selector)`.
It receives the verified source bytes and the contract's optional `selector`
(for documents that cover several models) and returns the points, or a mapping
with `points` and optional `components` and `constraints`. Extractors select
rows by their vendor label and parse address, width, type and scale from the
document. They fail on anything unexpected. [sourcelib.py](sourcelib.py) reads
PDF pages through `pdftotext`, HTML tables, CSV, ZIP members in memory, and the
cached cell values of XLSX and legacy XLS workbooks. It uses the standard
library only and never evaluates formulas or macros.

An extractor may also define `all_rows(data, selector)` (with `evidence` like
`extract`). It returns every row it parses, not only the selected ones, as
mappings with the vendor's own cell text: `vendor_address`, `registers`, `type`,
`label`, `unit`, `scale`, `access`, `notes`, `page` and `reference`, plus
`table` and the zero-based `address` where the document settles them as it does
for the contract. A row needs a label or a vendor address. With
`--dump-rows DIR`, a directory outside the checkout, `run.py` writes the rows
of each contract to `DIR/<vendor>/<model>/<name>.rows.yaml` and marks a row
`selected` when a contract point starts at its table and address. It lists the
sources whose extractor has no `all_rows`. The dump is for comparing a whole
register list with another transcription of the same document; it is never a
source, and it does not change the contracts. CI writes it for the sources a pull
request changes, so the hooks stay in working order.

```sh
CORPUS_CACHE=~/corpus-cache corpus/run.py --set all --offline --dump-rows ~/corpus-rows
```

Vendors often state a convention the mapping depends on, such as the address
base, the function code or the word order, in a companion manual rather than
in the register list. A source lists such documents under `evidence`. Each is
pinned in the lock like a source, passed to the extractor as
`extract(data, selector, evidence={id: bytes})`, and linked from the generated
contracts' `device.documentation`. The extractor must find the stated fact in
those bytes. A convention that is neither stated nor forced by the documents
leaves the model unmapped.

## Downloads and source changes

Each invocation uses a temporary directory that is removed when the run ends.
Set `CORPUS_CACHE` to a directory outside the checkout to keep the verified
bytes for a later `--offline` run. Requests send the generic `corpus-fetch/1`
user agent: some publishers reject Python's default one.

Pull-request CI fetches live only the sources the pull request changes
(`--changed-from`), then rebuilds them offline from the job-scoped cache and
compares the catalog. A change to `run.py`, `sourcelib.py`, the validator or the
schema selects every source. The weekly
[corpus health workflow](../.github/workflows/corpus-health.yml) re-fetches
every source, so schema checks never depend on vendor availability.

If the same source moves, update its URL and keep the existing checksum. If its
bytes change, review the new edition, update the lock explicitly, and review the
regenerated catalog diff.

Some CDNs alter each response. A lock entry may name a normalisation that
removes those bytes before hashing; `size` and `sha256` then describe the
normalised bytes. The only one is `cloudflare`: it blanks Cloudflare's
per-response email-obfuscation keys and removes its injected analytics beacon.
The Brainboxes ED tables need it.

## Roster

[roster.yaml](roster.yaml) tracks the target roster: ten device classes, five
vendors per class and three models per vendor. Each model is `mapped` (with its
contracts), `needs-check` or `blocked`, with the reason in its notes. It also
records the sources tried with their HTTP outcome, and work items with their
evidence, owner and draft decision. `corpus/roster.py` renders it into
[ROSTER.md](ROSTER.md) (coverage) and
[corpus-work-items.md](../docs/findings/corpus-work-items.md) (work items
grouped by kind, with spec-gap candidates and questions grouped by theme). With
`--check`, it fails when a page is stale, when a mapped model's contract is not
produced by the manifest, when a catalog contract is missing from the roster, or
when a spec-gap or question item is in no theme. The sets `class-01` to
`class-10` in the manifest select one class's sources.

Models outside the 150 targets are listed under `extras`; the sets
`extras-<group>` hold their sources. A third-party register map is never a
source or evidence: it may only be used to cross-check a contract, and the
vendor document decides.

## Findings

Record vendor behavior with a document locator and a proposed regression.
The [Eastron alignment finding](../docs/findings/eastron-sdm120-read-alignment.md)
shows how the existing point widths and gap policy cover its register pairs.
