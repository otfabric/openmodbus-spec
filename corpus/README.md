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
`devices/` contract comes from a corpus source. It never downloads.

## Extractors

An extractor is `corpus/extractors/<name>.py` with `extract(data, selector)`.
It receives the verified source bytes and the contract's optional `selector`
(for documents that cover several models) and returns the points, or a mapping
with `points` and optional `components` and `constraints`. Extractors select
rows by their vendor label and parse address, width, type and scale from the
document. They fail on anything unexpected. [sourcelib.py](sourcelib.py) reads
PDF pages through `pdftotext`, HTML tables, CSV, ZIP members in memory, and XLSX
cached cell values. It never evaluates formulas or macros.

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

## Findings

Record vendor behavior with a document locator and a proposed regression.
The [Eastron alignment finding](../docs/findings/eastron-sdm120-read-alignment.md)
shows how the existing point widths and gap policy cover its register pairs.
