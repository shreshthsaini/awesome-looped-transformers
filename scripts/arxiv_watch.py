"""Search arXiv for recent looped-transformer papers that are not in the list yet.

Writes a Markdown triage report (used as the body of a weekly issue) to the path given by --out.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re

import arxiv_api
from common import load_papers

PHRASES = [
    "looped transformer", "looped transformers", "looped language model", "looped language models",
    "recurrent depth", "recurrent-depth", "depth recurrence", "depth-recurrent", "universal transformer",
    "recursive transformer", "recursive transformers", "mixture-of-recursions", "mixture of recursions",
    "weight-tied transformer", "layer looping", "looped model", "recursive reasoning",
    "tiny recursive model", "hierarchical reasoning model", "latent recurrent", "loop transformer",
    "parameter-shared transformer", "deep equilibrium transformer",
]
CATEGORIES = "(cat:cs.LG OR cat:cs.CL OR cat:cs.AI OR cat:cs.CV OR cat:stat.ML OR cat:cs.NE)"


def score(entry: dict) -> int:
    text = f"{entry['title']} {entry['abstract']}".lower()
    s = sum(text.count(p) for p in PHRASES)
    s += 3 * sum(p in entry["title"].lower() for p in PHRASES)
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--out", default="arxiv_candidates.md")
    args = ap.parse_args()

    known = {p.get("arxiv") for p in load_papers() if p.get("arxiv")}
    cutoff = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    query = "(" + " OR ".join(f'abs:"{p}"' for p in PHRASES) + f") AND {CATEGORIES}"
    seen, found = set(), []
    for entry in arxiv_api.search(query, max_results=200):
        if entry["date"] < cutoff or entry["arxiv"] in known or entry["arxiv"] in seen:
            continue
        seen.add(entry["arxiv"])
        entry["score"] = score(entry)
        if entry["score"] > 0:
            found.append(entry)
    found.sort(key=lambda e: -e["score"])

    lines = [f"Candidate papers from arXiv submitted since **{cutoff}** that mention looped / recurrent-depth "
             "transformers and are not in the list yet. Ranked by keyword relevance; many will be false "
             "positives.", "",
             "To add one, comment `/add-paper <arxiv-id> <category> [type]` "
             "(maintainers only). Close this issue when triaged.", ""]
    if not found:
        lines.append("_No new candidates this week._")
    for e in found:
        authors = ", ".join(a for a in e["authors"][:3] if a != "et al.") + (" et al." if len(e["authors"]) > 3 else "")
        abstract = re.sub(r"\s+", " ", e["abstract"])[:400]
        lines += [
            f"- [ ] **[{e['title']}]({e['paper_url']})** ({e['date']}, relevance {e['score']})",
            f"  <sub>{authors}</sub>",
            "  <details><summary>abstract</summary>",
            "",
            f"  {abstract}...",
            "  </details>",
            "",
            f"  `/add-paper {e['arxiv']} <category>`",
            "",
        ]
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{len(found)} candidates written to {args.out}")


if __name__ == "__main__":
    main()
