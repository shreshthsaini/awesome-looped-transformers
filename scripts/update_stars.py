"""Refresh GitHub star counts for every entry with a GitHub code link (run daily by CI)."""

from __future__ import annotations

import os

from common import github_stars, load_papers, load_resources, save_papers, save_resources


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    papers, resources = load_papers(), load_resources()
    changed = 0
    for entry, key in [(p, "code_url") for p in papers] + [(r, "url") for r in resources]:
        if "github.com" not in (entry.get(key) or ""):
            continue
        stars = github_stars(entry[key], token)
        if stars is not None and stars != entry.get("stars"):
            entry["stars"] = stars
            changed += 1
    save_papers(papers)
    save_resources(resources)
    print(f"Updated star counts for {changed} entries.")


if __name__ == "__main__":
    main()
