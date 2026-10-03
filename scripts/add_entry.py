"""Add a paper or resource to the database. Used by the GitHub Actions bots and by hand.

Examples
  python scripts/add_entry.py paper --issue-body-env ISSUE_BODY
  python scripts/add_entry.py paper --arxiv 2502.05171 --category language-models --type Method
  python scripts/add_entry.py command --text "/add-paper 2502.05171 language-models Method"
  python scripts/add_entry.py resource --issue-body-env ISSUE_BODY

On success it prints a Markdown summary and, inside GitHub Actions, writes `id`, `title` and
`summary_file` to $GITHUB_OUTPUT. On a user-facing problem (duplicate, bad link) it exits with code 2
after writing the explanation to the summary file, so the workflow can post it as a comment.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import arxiv_api
from common import (find_duplicate, load_config, load_papers, load_resources, make_id,
                    parse_arxiv_id, save_papers, save_resources, today, validate_all)

SUMMARY = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "add_entry_summary.md"
NO_RESPONSE = {"", "_no response_", "none", "n/a", "-"}


class UserError(Exception):
    """A problem the submitter should fix; reported back on the issue."""


def parse_issue_form(body: str) -> dict[str, str]:
    """Issue forms render as '### Label' headings followed by the answer."""
    fields, current, buf = {}, None, []
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.*)$", line)
        if m:
            if current is not None:
                fields[current] = "\n".join(buf).strip()
            current, buf = m.group(1).strip().lower(), []
        else:
            buf.append(line)
    if current is not None:
        fields[current] = "\n".join(buf).strip()
    return {k: ("" if v.strip().lower() in NO_RESPONSE else v.strip()) for k, v in fields.items()}


def pick(fields: dict, *prefixes: str) -> str:
    for key, val in fields.items():
        if any(key.startswith(p) for p in prefixes):
            return val
    return ""


def first_sentence(text: str, max_words: int = 28) -> str:
    sent = re.split(r"(?<=[.!?])\s+", (text or "").strip())[0]
    words = sent.split()
    out = " ".join(words[:max_words])
    return out if len(words) <= max_words else out.rstrip(",;:") + "..."


def emit(summary: str, **outputs: str) -> None:
    SUMMARY.write_text(summary, encoding="utf-8")
    print(summary)
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            for k, v in {**outputs, "summary_file": str(SUMMARY)}.items():
                fh.write(f"{k}={v}\n")


def build_paper(raw: dict, config: dict) -> dict:
    link = raw.get("paper_url", "").strip()
    arxiv_id = parse_arxiv_id(link)
    meta: dict = {}
    if arxiv_id:
        try:
            meta = arxiv_api.fetch(arxiv_id) or {}
        except Exception as exc:  # noqa: BLE001
            print(f"warning: arXiv lookup failed ({exc}); relying on submitted fields", file=sys.stderr)
        if not meta and not raw.get("title"):
            raise UserError(f"Could not find arXiv paper `{arxiv_id}`. Please double-check the link.")
    elif not link.startswith("https://"):
        raise UserError("The paper link must be an arXiv id/URL or an https URL.")

    cat_field = raw.get("category", "")
    category = cat_field.split(":")[0].strip()
    if category not in {c["id"] for c in config["categories"]}:
        raise UserError(f"Unknown category `{cat_field}`.")
    ptype = raw.get("type") or "Method"
    if ptype not in config["types"]:
        raise UserError(f"Unknown type `{ptype}`. Use one of: {', '.join(config['types'])}.")

    tags = [t.strip().lower() for t in re.split(r"[,\s]+", raw.get("tags", "")) if t.strip()]
    unknown = [t for t in tags if t not in config["tags"]]
    tags = [t for t in tags if t in config["tags"]]

    authors = meta.get("authors") or [a.strip() for a in raw.get("authors", "").split(",") if a.strip()]
    paper = {
        "title": raw.get("title") or meta.get("title"),
        "authors": authors,
        "date": raw.get("date") or meta.get("date"),
        "venue": raw.get("venue") or meta.get("venue") or "arXiv",
        "type": ptype,
        "category": category,
        "tags": tags,
        "arxiv": arxiv_id,
        "paper_url": meta.get("paper_url") or link,
        "code_url": (raw.get("code_url") or meta.get("code_url") or None),
        "project_url": raw.get("project_url") or None,
        "tldr": (raw.get("tldr") or first_sentence(meta.get("abstract", ""))).replace("—", ", ").strip(),
        "added": today(),
    }
    if paper["code_url"]:
        paper["code_url"] = paper["code_url"].rstrip("/")
    if unknown:
        paper["_unknown_tags"] = unknown
    return paper


def add_paper(raw: dict) -> None:
    config = load_config()
    papers = load_papers()
    paper = build_paper(raw, config)
    dup = find_duplicate(paper, papers)
    if dup:
        raise UserError(f"This paper is already in the list as **{dup['title']}** (`{dup['id']}`, "
                        f"category `{dup['category']}`). If something about it is wrong, please open a "
                        f"\"Fix an entry\" issue instead.")
    unknown = paper.pop("_unknown_tags", [])
    paper["id"] = make_id(paper, {p["id"] for p in papers})
    papers.append(paper)
    errors = validate_all(papers, load_resources(), config)
    if errors:
        raise UserError("The entry did not pass validation:\n" + "\n".join(f"- {e}" for e in errors))
    save_papers(papers)

    lines = [
        f"### ✅ Added: {paper['title']}",
        "",
        "| Field | Value |", "|---|---|",
        f"| Authors | {', '.join(paper['authors'])} |",
        f"| Date | {paper['date']} |",
        f"| Venue | {paper['venue']} |",
        f"| Category | `{paper['category']}` |",
        f"| Type | `{paper['type']}` |",
        f"| Paper | {paper['paper_url']} |",
        f"| Code | {paper.get('code_url') or 'none found'} |",
        f"| TL;DR | {paper['tldr']} |",
    ]
    if unknown:
        lines += ["", f"Ignored unknown tags: {', '.join(unknown)}."]
    if not raw.get("tldr"):
        lines += ["", "⚠️ The TL;DR was taken from the abstract; a maintainer may want to shorten it."]
    emit("\n".join(lines) + "\n", id=paper["id"], title=paper["title"][:80].replace("\n", " "))


def add_resource(raw: dict) -> None:
    config = load_config()
    resources = load_resources()
    url = raw.get("url", "").strip()
    if not url.startswith("https://"):
        raise UserError("The resource link must be an https URL.")
    if any(r["url"].rstrip("/") == url.rstrip("/") for r in resources):
        raise UserError("This resource is already in the list.")
    res = {"name": raw.get("name"), "kind": raw.get("kind"), "url": url,
           "description": raw.get("description", "").replace("—", ", ")}
    resources.append(res)
    errors = validate_all(load_papers(), resources, config)
    if errors:
        raise UserError("The entry did not pass validation:\n" + "\n".join(f"- {e}" for e in errors))
    save_resources(resources)
    emit(f"### ✅ Added resource: [{res['name']}]({url})\n", id=re.sub(r"\W+", "-", res["name"].lower()),
         title=res["name"][:80])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["paper", "resource", "command"])
    ap.add_argument("--issue-body-env", help="name of the env var holding an issue-form body")
    ap.add_argument("--text", help="comment text containing /add-paper ...")
    ap.add_argument("--arxiv")
    ap.add_argument("--category")
    ap.add_argument("--type", default="Method")
    ap.add_argument("--code")
    ap.add_argument("--tldr")
    args = ap.parse_args()

    try:
        if args.mode == "resource":
            f = parse_issue_form(os.environ.get(args.issue_body_env or "", ""))
            add_resource({"name": pick(f, "name"), "url": pick(f, "link"), "kind": pick(f, "kind"),
                          "description": pick(f, "one-sentence")})
        elif args.mode == "command":
            text = args.text or os.environ.get("COMMENT_BODY", "")
            m = re.search(r"^/add-paper\s+(\S+)\s+(\S+)(?:\s+(\S+))?(?:\s+(https://github\.com/\S+))?", text, re.M)
            if not m:
                raise UserError("Usage: `/add-paper <arxiv-id-or-url> <category> [type] [code-url]`")
            add_paper({"paper_url": m.group(1), "category": m.group(2), "type": m.group(3) or "Method",
                       "code_url": m.group(4) or ""})
        elif args.issue_body_env:
            f = parse_issue_form(os.environ.get(args.issue_body_env, ""))
            add_paper({
                "paper_url": pick(f, "paper link"), "category": pick(f, "category"), "type": pick(f, "type"),
                "code_url": pick(f, "official code"), "project_url": pick(f, "project page"),
                "venue": pick(f, "venue"), "title": pick(f, "title"), "authors": pick(f, "authors"),
                "date": pick(f, "date"), "tags": pick(f, "tags"), "tldr": pick(f, "one-sentence"),
            })
        else:
            add_paper({"paper_url": args.arxiv or "", "category": args.category or "", "type": args.type,
                       "code_url": args.code or "", "tldr": args.tldr or ""})
    except UserError as err:
        emit(f"### ⚠️ Could not add this entry automatically\n\n{err}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
