"""Generate README.md from templates/README.template.md and the YAML database.

Usage: python scripts/build_readme.py [--check]
  --check  exit non-zero if README.md is out of date (used in CI on pull requests)
"""

from __future__ import annotations

import collections
import re
import sys
import urllib.parse

from common import ROOT, load_config, load_papers, load_resources, repo_slug, validate_all

TEMPLATE = ROOT / "templates" / "README.template.md"
README = ROOT / "README.md"


def esc(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def anchor(title: str) -> str:
    """GitHub's heading anchor algorithm (good enough for our headings)."""
    a = title.strip().lower()
    a = re.sub(r"[^\w\- ]", "", a, flags=re.UNICODE)
    return a.replace(" ", "-")


def fmt_authors(authors: list[str]) -> str:
    names = [a for a in authors if a != "et al."]
    if len(names) > 3 or "et al." in authors:
        return ", ".join(names[:3]) + " et al."
    return ", ".join(names)


def stars_badge(url: str | None) -> str:
    if not url or "github.com" not in url:
        return ""
    path = urllib.parse.urlparse(url).path.strip("/").split("/")
    if len(path) < 2:
        return ""
    owner, repo = path[0], path[1]
    return (f"[![GitHub stars](https://img.shields.io/github/stars/{owner}/{repo}"
            f"?style=flat&logo=github&label=&color=4c1)]({url})")


def links(p: dict) -> str:
    out = []
    if p.get("arxiv"):
        out.append(f"[PDF](https://arxiv.org/pdf/{p['arxiv']})")
    if p.get("code_url") and "github.com" not in p["code_url"]:
        out.append(f"[Code]({p['code_url']})")
    if p.get("project_url"):
        out.append(f"[Project / Model]({p['project_url']})")
    return " · ".join(out)


def paper_row(p: dict) -> str:
    title = f"**[{esc(p['title'])}]({p['paper_url']})**"
    meta = f"<sub>{esc(fmt_authors(p['authors']))}</sub>"
    tldr = f"<br><sub>💡 {esc(p['tldr'])}</sub>" if p.get("tldr") else ""
    code = stars_badge(p.get("code_url")) or ("—" if not p.get("code_url") else f"[Code]({p['code_url']})")
    extra = f"<br><sub>{links(p)}</sub>" if links(p) else ""
    return (f"| {p['date'][:7]} | {title}<br>{meta}{tldr}{extra} | {esc(p['venue'])} | `{p['type']}` "
            f"| {code} |")


def section(cat: dict, papers: list[dict]) -> str:
    rows = sorted(papers, key=lambda p: (p["date"], p["title"]), reverse=True)
    head = f"### {cat['emoji']} {cat['title']}\n\n> {cat['blurb']}\n\n"
    if not rows:
        return head + "_No papers yet. [Add the first one!](#-contributing)_\n"
    table = ["| Date | Paper | Venue | Type | Code |", "|:---:|:---|:---:|:---:|:---:|"]
    table += [paper_row(p) for p in rows]
    body = "\n".join(table)
    if len(rows) > 12:
        body = (f"<details open>\n<summary><b>{len(rows)} papers</b> (click to collapse)</summary>\n\n"
                f"{body}\n\n</details>")
    return head + body + "\n\n<div align=\"right\"><a href=\"#-table-of-contents\">⬆ back to top</a></div>\n"


def news(papers: list[dict], n: int = 10) -> str:
    recent = sorted(papers, key=lambda p: (p.get("added", ""), p["date"]), reverse=True)[:n]
    lines = []
    for p in recent:
        lines.append(f"- **{p['date'][:7]}** · [{esc(p['title'])}]({p['paper_url']}) "
                     f"<sub>({esc(p['venue'])})</sub>")
    return "\n".join(lines)


def progress(papers: list[dict]) -> str:
    """A plain-text progress tracker: papers per year with a simple bar."""
    years = collections.Counter(p["date"][:4] for p in papers)
    if not years:
        return "_No papers yet._"
    top = max(years.values())
    rows = ["| Year | Papers | |", "|:---:|:---:|:---|"]
    for y in sorted(years, reverse=True):
        bar = "█" * max(1, round(28 * years[y] / top))
        rows.append(f"| {y} | {years[y]} | `{bar}` |")
    with_code = sum(1 for p in papers if p.get("code_url"))
    return (f"**{len(papers)} papers** · **{with_code}** with official code · newest "
            f"{max(p['date'] for p in papers)}\n\n" + "\n".join(rows))


def toc(config: dict, papers: list[dict], has_resources: bool) -> str:
    counts = collections.Counter(p["category"] for p in papers)
    cells = [f"{c['emoji']} [{c['title']}](#{anchor(c['emoji'] + ' ' + c['title'])}) `{counts.get(c['id'], 0)}`"
             for c in config["categories"] if counts.get(c["id"])]
    cols = 2
    while len(cells) % cols:
        cells.append("")
    rows = ["| " + " | ".join(["Papers by category"] + [""] * (cols - 1)) + " |",
            "|" + ":---|" * cols]
    for i in range(0, len(cells), cols):
        rows.append("| " + " | ".join(cells[i:i + cols]) + " |")
    links = ["[Recently added](#-recently-added)", "[Papers](#-papers)"]
    if has_resources:
        links.append("[Resources](#-resources)")
    links += ["[Contributing](#-contributing)", "[Progress](#-progress)", "[Citation](#-citation)"]
    return " · ".join(links) + "\n\n" + "\n".join(rows)


def resources_md(resources: list[dict], config: dict) -> str:
    out = []
    for kind in config["resource_kinds"]:
        items = [r for r in resources if r["kind"] == kind["id"]]
        if not items:
            continue
        out.append(f"### {kind['title']}\n")
        for r in sorted(items, key=lambda r: r["name"].lower()):
            badge = " " + stars_badge(r["url"]) if "github.com" in r["url"] else ""
            date = f" <sub>({r['date']})</sub>" if r.get("date") else ""
            out.append(f"- [{esc(r['name'])}]({r['url']}){badge}{date}: {esc(r['description'])}")
        out.append("")
    return "\n".join(out)


def render() -> str:
    config = load_config()
    papers = load_papers()
    resources = load_resources()
    errors = validate_all(papers, resources, config)
    if errors:
        sys.exit("Validation failed:\n  " + "\n  ".join(errors))

    slug = repo_slug(config)
    by_cat = collections.defaultdict(list)
    for p in papers:
        by_cat[p["category"]].append(p)
    # Empty categories (e.g. surveys, until a looped-transformer survey exists) are not rendered.
    sections = "\n".join(section(c, by_cat[c["id"]]) for c in config["categories"] if by_cat.get(c["id"]))
    years = sorted({p["date"][:4] for p in papers}) or ["—"]

    values = {
        "REPO": slug,
        "OWNER": slug.split("/")[0],
        "REPO_NAME": slug.split("/")[1],
        "TITLE": config["title"],
        "PAPER_COUNT": str(len(papers)),
        "CODE_COUNT": str(sum(1 for p in papers if p.get("code_url"))),
        "CATEGORY_COUNT": str(len(by_cat)),
        "YEAR_RANGE": f"{years[0]}–{years[-1]}",
        "LAST_PAPER_DATE": max((p["date"] for p in papers), default="—"),
        "TOC": toc(config, papers, bool(resources)),
        "NEWS": news(papers),
        "PROGRESS": progress(papers),
        "SECTIONS": sections,
        "RESOURCES": resources_md(resources, config),
        "MAINTAINER": config["maintainer"],
        "CITATION_KEY": config["citation_key"],
        "YEAR": str(config["year_started"]),
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", val)
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if leftover:
        sys.exit(f"Unfilled template placeholders: {leftover}")
    return "<!-- This file is generated by scripts/build_readme.py. Edit data/*.yaml or templates/ instead. -->\n" + text


def main():
    text = render()
    if "--check" in sys.argv:
        if README.read_text(encoding="utf-8") != text:
            sys.exit("README.md is out of date. Run `python scripts/build_readme.py` and commit the result.")
        print("README.md is up to date.")
        return
    README.write_text(text, encoding="utf-8")
    print(f"Wrote {README.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
