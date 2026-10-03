"""Validate data/*.yaml (schema, duplicates, categories). Exit 1 on any error."""

from __future__ import annotations

import sys

from common import ROOT, load_config, load_papers, load_resources, validate_all


def main() -> None:
    config = load_config()
    papers, resources = load_papers(), load_resources()
    errors = validate_all(papers, resources, config)

    # The issue form must offer every category, or contributors cannot pick it.
    form = (ROOT / ".github" / "ISSUE_TEMPLATE" / "add-paper.yml").read_text(encoding="utf-8")
    errors += [f"category `{c['id']}` is missing from the add-paper issue form"
               for c in config["categories"] if f"\"{c['id']}:" not in form]

    if errors:
        print(f"❌ {len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"✅ {len(papers)} papers and {len(resources)} resources look good.")


if __name__ == "__main__":
    main()
