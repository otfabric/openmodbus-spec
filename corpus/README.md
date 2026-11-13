# Vendor corpus

Each [manifest](sources.yaml) entry records the publisher, source edition,
direct public download URL, and destination contract. The [source lock](sources.lock.yaml)
pins the download's size and SHA-256. Source files are temporary inputs. The
reviewed OpenModbus YAML in [devices/](../devices/) is the catalog.

## Verify or rebuild the pilot

Use Poppler's `pdftotext` for PDF extraction.

```sh
make corpus
make corpus CORPUS_ARGS=--write-catalog
```

Both commands download the locked source, extract the selected rows, generate
a contract and validate it against the draft schema. The pilot also checks
register width, address bounds, overlaps, and duplicate IDs. The first
command compares each generated contract with the checked-in YAML. The second
writes changed or missing contracts after every selected source passes validation.
Review the YAML diff before committing it.

The pilot covers four Victron Cerbo GX system battery points from CSV and five
Eastron SDM120-Modbus telemetry points from PDF. Each generated point records
its source row or page and the vendor's original address. These are documented
subsets. `make check` checks the schema and YAML without downloading vendor files.

## Source updates and spec findings

Each invocation uses a temporary directory that is removed when the run ends.
Set `CORPUS_CACHE` to a directory outside the checkout to keep the verified
bytes for a later offline run. CI uses a job-scoped cache to test both the live
URLs and offline replay.

If the same source moves, update its URL and keep the existing checksum. If
its bytes change, review the new edition, update the lock explicitly, and
review the regenerated catalog diff.

Record behavior that the draft cannot express with a document locator and a
proposed regression. The [Eastron alignment finding](../docs/findings/eastron-sdm120-read-alignment.md)
is the pilot's first input to D10.
