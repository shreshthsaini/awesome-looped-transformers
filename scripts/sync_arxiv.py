"""Re-sync title, authors, first-submission date and code/venue hints from the arXiv API.

Run by the build workflow so hand-written or bot-written entries always match arXiv. Only fields that
arXiv is authoritative for are overwritten (title, authors, date). Venue is only filled in when the entry
still says "arXiv" and arXiv's journal_ref/comments name a venue; code_url is only filled when empty.

Usage: python scripts/sync_arxiv.py [--dry-run]
"""

from __future__ import annotations

import sys
import time

import arxiv_api
from common import load_papers, save_papers

BATCH = 50


def main() -> None:
    papers = load_papers()
    ids = [p["arxiv"] for p in papers if p.get("arxiv")]
    meta: dict[str, dict] = {}
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        try:
            for m in arxiv_api._query({"id_list": ",".join(chunk), "max_results": len(chunk)}):
                meta[m["arxiv"]] = m
        except Exception as exc:  # noqa: BLE001
            print(f"warning: arXiv batch {i // BATCH} failed: {exc}", file=sys.stderr)
        time.sleep(3)  # arXiv asks for at most one request every 3 seconds

    changes = []
    for p in papers:
        m = meta.get(p.get("arxiv") or "")
        if not m:
            continue
        for field in ("title", "authors", "date"):
            if m.get(field) and m[field] != p.get(field):
                changes.append(f"{p['id']}: {field} {p.get(field)!r} -> {m[field]!r}")
                p[field] = m[field]
        if p.get("venue") == "arXiv" and m.get("venue") not in (None, "arXiv"):
            changes.append(f"{p['id']}: venue arXiv -> {m['venue']!r}")
            p["venue"] = m["venue"]
        if not p.get("code_url") and m.get("code_url"):
            changes.append(f"{p['id']}: code_url -> {m['code_url']}")
            p["code_url"] = m["code_url"]

    missing = [i for i in ids if i not in meta]
    print(f"Fetched {len(meta)}/{len(ids)} arXiv records, {len(changes)} field updates.")
    for c in changes:
        print("  " + c)
    if missing and meta:
        print(f"Not found on arXiv (check these ids): {', '.join(missing)}")
    if changes and "--dry-run" not in sys.argv:
        save_papers(papers)


if __name__ == "__main__":
    main()
