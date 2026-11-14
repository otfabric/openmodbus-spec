#!/usr/bin/env python3
"""Render the vendor roster (roster.yaml) into coverage and work-item pages.

  roster.py          write corpus/ROSTER.md and docs/findings/corpus-work-items.md
  roster.py --check  fail if either page is stale or the roster disagrees with the manifest
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml

CORPUS = Path(__file__).resolve().parent
ROOT = CORPUS.parent
ROSTER = CORPUS / "roster.yaml"
COVERAGE = CORPUS / "ROSTER.md"
WORK_ITEMS = ROOT / "docs/findings/corpus-work-items.md"
STATUSES = ("mapped", "needs-check", "blocked")
KINDS = {
    "spec-gap": "Spec-gap candidates",
    "question": "Questions on the draft",
    "doc-ambiguity": "Document ambiguities",
    "vendor-erratum": "Vendor errata",
    "model-scope": "Model scope",
    "source-access": "Source access",
    "extraction": "Extraction",
    "tooling": "Tooling",
}
THEMED = ("spec-gap", "question")


def classes_of(item):
    value = item.get("class")
    return value if isinstance(value, list) else [value]


def class_label(item):
    numbers = classes_of(item)
    return f"Class {numbers[0]}" if len(numbers) == 1 else "Classes " + ", ".join(str(n) for n in numbers)


def cell(text):
    return " ".join(str(text or "").split()).replace("|", "\\|")


def first_sentence(text):
    text = " ".join(str(text or "").split())
    for index, char in enumerate(text):
        if char in ".;" and (index + 1 == len(text) or text[index + 1] == " ") and index > 20:
            return text[:index + 1]
    return text


def points(path):
    document = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    return len(document["points"])


def check(roster, manifest):
    errors = []
    produced = {contract["path"]: source_id for source_id, source in manifest["sources"].items()
                for contract in source["contracts"]}
    claimed = set()
    entries = [(f"class {klass['id']} {vendor['vendor']} {model['model']}", model)
               for klass in roster["classes"] for vendor in klass["vendors"] for model in vendor["models"]]
    entries += [(f"extra {extra['vendor']} {extra['model']}", extra) for extra in roster.get("extras", [])]
    names = Counter(where for where, _ in entries)
    errors += [f"{where}: listed {count} times" for where, count in names.items() if count > 1]
    for where, model in entries:
        if model["status"] not in STATUSES:
            errors.append(f"{where}: unknown status {model['status']!r}")
        contracts = model.get("contracts") or []
        if model["status"] == "mapped" and not contracts:
            errors.append(f"{where}: mapped without a contract")
        if model["status"] != "mapped" and contracts:
            errors.append(f"{where}: contracts listed but status is {model['status']}")
        if model["status"] != "mapped" and not model.get("notes"):
            errors.append(f"{where}: {model['status']} needs a reason in notes")
        for path in contracts:
            if path not in produced:
                errors.append(f"{where}: {path} is not produced by any corpus source")
            if path in claimed:
                errors.append(f"{where}: {path} is claimed twice")
            claimed.add(path)
    errors += [f"{path}: catalog contract missing from the roster" for path in sorted(set(produced) - claimed)]
    ids = Counter(item["id"] for item in roster.get("work_items", []))
    errors += [f"duplicate work item {item_id}" for item_id, count in ids.items() if count > 1]
    for item in roster.get("work_items", []):
        if item["kind"] not in KINDS:
            errors.append(f"{item['id']}: unknown kind {item['kind']!r}")
    items = {item["id"]: item for item in roster.get("work_items", [])}
    for item in roster.get("work_items", []):
        errors += [f"{item['id']}: related item {ref} does not exist" for ref in item.get("related", [])
                   if ref not in items]
    themed = Counter()
    for theme in roster.get("themes", []):
        for ref in theme["items"]:
            themed[ref] += 1
            if ref not in items:
                errors.append(f"theme {theme['id']}: work item {ref} does not exist")
            elif items[ref]["kind"] not in THEMED:
                errors.append(f"theme {theme['id']}: {ref} is a {items[ref]['kind']}, not a spec-gap or question")
    errors += [f"theme item {ref} appears in {count} themes" for ref, count in themed.items() if count > 1]
    errors += [f"{item_id}: {item['kind']} item in no theme" for item_id, item in items.items()
               if item["kind"] in THEMED and not themed[item_id]]
    return errors


def render_coverage(roster):
    lines = ["# Vendor roster coverage", "",
             f"Generated from [roster.yaml](roster.yaml) by `corpus/roster.py`; do not edit by hand. "
             f"Status on {roster['updated']}.", "",
             "A model is **mapped** when a contract generated from a checksum-pinned public vendor document exists "
             "under [devices/](../devices/). Mapped contracts are reviewed, read-only subsets (`verification: "
             "documented`), not complete register maps. **needs-check** and **blocked** models have no contract; "
             "the notes give the reason, and [work items](../docs/findings/corpus-work-items.md) say what would "
             "unblock them.", "",
             "| Class | Vendors | Models | Mapped | Needs check | Blocked | Unique layouts | Points |",
             "|---|---|---|---|---|---|---|---|"]
    totals = Counter()
    for klass in roster["classes"]:
        status = Counter(model["status"] for vendor in klass["vendors"] for model in vendor["models"])
        layouts = {model.get("layout") for vendor in klass["vendors"] for model in vendor["models"]
                   if model["status"] == "mapped"}
        count = sum(points(path) for vendor in klass["vendors"] for model in vendor["models"]
                    for path in model.get("contracts") or [])
        models = sum(status.values())
        row = Counter(vendors=len(klass["vendors"]), models=models, mapped=status["mapped"],
                      check=status["needs-check"], blocked=status["blocked"], layouts=len(layouts), points=count)
        totals.update(row)
        lines.append(f"| {klass['id']}. {klass['name']} | {row['vendors']} | {models} | {row['mapped']} | "
                     f"{row['check']} | {row['blocked']} | {row['layouts']} | {count} |")
    lines.append(f"| **Total** | {totals['vendors']} | {totals['models']} | {totals['mapped']} | {totals['check']} | "
                 f"{totals['blocked']} | {totals['layouts']} | {totals['points']} |")
    extras = roster.get("extras", [])
    if extras:
        status = Counter(extra["status"] for extra in extras)
        layouts = {extra.get("layout") or extra["model"] for extra in extras if extra["status"] == "mapped"}
        count = sum(points(path) for extra in extras for path in extra.get("contracts") or [])
        lines.append(f"| Outside the target roster | {len({extra['vendor'] for extra in extras})} | {len(extras)} | "
                     f"{status['mapped']} | {status['needs-check']} | {status['blocked']} | {len(layouts)} | {count} |")
    for klass in roster["classes"]:
        lines += ["", f"## {klass['id']}. {klass['name']}", "",
                  "| Vendor | Model | Status | Contract | Points | Notes |", "|---|---|---|---|---|---|"]
        for vendor in klass["vendors"]:
            for model in vendor["models"]:
                contracts = model.get("contracts") or []
                links = "<br>".join(f"[{Path(path).relative_to('devices')}](../{path})" for path in contracts)
                count = sum(points(path) for path in contracts) if contracts else ""
                lines.append(f"| {cell(vendor['vendor'])} | {cell(model['model'])} | {model['status']} | {links} | "
                             f"{count} | {cell(first_sentence(model.get('notes')))} |")
    if extras:
        lines += ["", "## Outside the target roster", "",
                  "Models that are not among the 150 roster targets, mapped from the same kind of pinned public "
                  "vendor sources.", "",
                  "| Class | Vendor | Model | Status | Contract | Points | Notes |", "|---|---|---|---|---|---|---|"]
        for extra in extras:
            contracts = extra.get("contracts") or []
            links = "<br>".join(f"[{Path(path).relative_to('devices')}](../{path})" for path in contracts)
            count = sum(points(path) for path in contracts) if contracts else ""
            lines.append(f"| {extra['class']} | {cell(extra['vendor'])} | {cell(extra['model'])} | {extra['status']} | "
                         f"{links} | {count} | {cell(first_sentence(extra.get('notes')))} |")
    return "\n".join(line.rstrip() for line in lines) + "\n"


def render_work_items(roster):
    items = roster.get("work_items", [])
    lines = ["# Corpus work items", "",
             "Generated from [corpus/roster.yaml](../../corpus/roster.yaml) by `corpus/roster.py`; do not edit by "
             "hand. Each item names its evidence (document, page or row, vendor address) and who has to act.", "",
             "Spec-gap candidates are inputs to the maintainer's decisions in [PROPOSAL.md](../PROPOSAL.md); none "
             "is agreed. A candidate shows a reviewed source row and a case the current draft cannot express.", "",
             "| Kind | Open items |", "|---|---|"]
    by_kind = Counter(item["kind"] for item in items)
    lines += [f"| {title} | {by_kind[kind]} |" for kind, title in KINDS.items() if by_kind[kind]]
    themes = roster.get("themes", [])
    if themes:
        index = {item["id"]: item for item in items}
        lines += ["", "## Themes", "",
                  "The spec-gap candidates and questions, grouped by the draft decision they bear on. A theme that "
                  "recurs across classes is stronger evidence than a single vendor.", "",
                  "| Theme | Decisions | Classes | Items |", "|---|---|---|---|"]
        for theme in themes:
            numbers = sorted({n for ref in theme["items"] for n in classes_of(index[ref])})
            lines.append(f"| {cell(theme['title'])} | {cell(theme['decisions'])} | "
                         f"{', '.join(str(n) for n in numbers)} | {len(theme['items'])} |")
        for theme in themes:
            lines += ["", f"### {theme['title']}", "", cell(theme["summary"]), ""]
            for ref in theme["items"]:
                item = index[ref]
                lines.append(f"- `{ref}` ({item['kind']}, {class_label(item).lower()}, "
                             f"{cell(item.get('vendor'))}): {cell(item['summary'])}")
    for kind, title in KINDS.items():
        selected = [item for item in items if item["kind"] == kind]
        if not selected:
            continue
        lines += ["", f"## {title}", ""]
        for item in selected:
            models = ", ".join(item.get("models") or [])
            head = f"### `{item['id']}`: {cell(item['summary'])}"
            lines += [head, "",
                      f"- **{class_label(item)}, vendor:** {cell(item.get('vendor'))}"
                      + (f" ({cell(models)})" if models else ""),
                      f"- **Owner:** {item.get('owner', 'maintainer')}"]
            if item.get("decision"):
                lines.append(f"- **Decision:** {cell(item['decision'])}")
            lines.append(f"- **Evidence:** {cell(item.get('evidence'))}")
            if item.get("detail"):
                lines.append(f"- **Detail:** {cell(item['detail'])}")
            if item.get("regression"):
                lines.append(f"- **Proposed regression:** {cell(item['regression'])}")
            if item.get("related"):
                lines.append("- **Related:** " + ", ".join(f"`{ref}`" for ref in item["related"]))
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    return "\n".join(line.rstrip() for line in lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    roster = yaml.safe_load(ROSTER.read_text(encoding="utf-8"))
    manifest = yaml.safe_load((CORPUS / "sources.yaml").read_text(encoding="utf-8"))
    errors = check(roster, manifest)
    pages = {COVERAGE: render_coverage(roster), WORK_ITEMS: render_work_items(roster)}
    for path, content in pages.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                errors.append(f"{path.relative_to(ROOT)} is stale: run corpus/roster.py")
        else:
            path.write_text(content, encoding="utf-8")
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        sys.exit(1)
    print("roster ok" if args.check else "roster pages written")


if __name__ == "__main__":
    main()
