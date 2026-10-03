"""Shared helpers: loading/saving the YAML database, validation and small utilities."""

from __future__ import annotations

import datetime as dt
import os
import re
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG_PATH = DATA / "config.yaml"
PAPERS_PATH = DATA / "papers.yaml"
RESOURCES_PATH = DATA / "resources.yaml"

FIELD_ORDER = [
    "id", "title", "authors", "date", "venue", "type", "category", "tags",
    "arxiv", "paper_url", "code_url", "project_url", "tldr", "added",
]
RESOURCE_FIELD_ORDER = ["name", "kind", "url", "date", "description", "related_arxiv"]

ARXIV_RE = re.compile(r"(?:arxiv\.org/(?:abs|pdf|html)/|arxiv:\s*)?(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
GITHUB_RE = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------- io

class _Dumper(yaml.SafeDumper):
    """Indent lists under their key and keep plain scalars unquoted where YAML allows it."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


# Records are block mappings; short lists (authors, tags) stay inline for readability.
_Dumper.add_representer(list, lambda d, v: d.represent_sequence(
    "tag:yaml.org,2002:seq", v, flow_style=all(not isinstance(x, (dict, list)) for x in v)))


def load_yaml(path: Path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def load_config() -> dict:
    return load_yaml(CONFIG_PATH)


def load_papers() -> list[dict]:
    papers = load_yaml(PAPERS_PATH) if PAPERS_PATH.exists() else []
    for p in papers:
        for key in ("date", "added"):
            if isinstance(p.get(key), (dt.date, dt.datetime)):
                p[key] = p[key].strftime("%Y-%m-%d")
    return papers


def load_resources() -> list[dict]:
    return load_yaml(RESOURCES_PATH) if RESOURCES_PATH.exists() else []


def _ordered(record: dict, order: list[str]) -> dict:
    out = {k: record[k] for k in order if record.get(k) not in (None, "", [])}
    out.update({k: v for k, v in record.items() if k not in order and v not in (None, "", [])})
    return out


HEADER = (
    "# Single source of truth for the list. README.md and the plots are generated from this file.\n"
    "# Add papers through the \"Add a paper\" issue form, or edit by hand and run `make build`.\n"
    "# Field reference: CONTRIBUTING.md\n\n"
)


def save_papers(papers: list[dict]) -> None:
    papers = sorted(papers, key=lambda p: (p.get("date", ""), p.get("title", "")), reverse=True)
    body = yaml.dump([_ordered(p, FIELD_ORDER) for p in papers], Dumper=_Dumper, sort_keys=False,
                     allow_unicode=True, width=110, default_flow_style=False)
    body = re.sub(r"\n- id:", "\n\n- id:", body)
    PAPERS_PATH.write_text(HEADER + body, encoding="utf-8")


def save_resources(resources: list[dict]) -> None:
    resources = sorted(resources, key=lambda r: (r.get("kind", ""), (r.get("name") or "").lower()))
    body = yaml.dump([_ordered(r, RESOURCE_FIELD_ORDER) for r in resources], Dumper=_Dumper,
                     sort_keys=False, allow_unicode=True, width=110, default_flow_style=False)
    body = re.sub(r"\n- name:", "\n\n- name:", body)
    RESOURCES_PATH.write_text(
        "# Code, checkpoints, blogs, talks and other non-paper resources.\n\n" + body, encoding="utf-8")


# ---------------------------------------------------------------------- utilities

def repo_slug(config: dict | None = None) -> str:
    return os.environ.get("GITHUB_REPOSITORY") or (config or load_config())["repository"]


def today() -> str:
    return dt.date.today().strftime("%Y-%m-%d")


def normalize_title(title: str) -> str:
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def parse_arxiv_id(text: str | None) -> str | None:
    if not text:
        return None
    m = ARXIV_RE.search(text)
    return m.group(1) if m else None


def parse_github(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    m = GITHUB_RE.match(url.strip())
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    repo = re.sub(r"\.git$", "", repo)
    return owner, repo


def make_id(paper: dict, existing: set[str]) -> str:
    first = (paper.get("authors") or ["anon"])[0]
    last = normalize_title(first.split()[-1]) or "anon"
    year = (paper.get("date") or "0000")[:4]
    words = [w for w in re.findall(r"[a-z0-9]+", paper.get("title", "").lower())
             if w not in {"a", "an", "the", "of", "on", "for", "with", "and", "in", "to", "via", "is", "are"}]
    base = f"{last}{year}-{'-'.join(words[:3])}" if words else f"{last}{year}"
    slug, n = base, 2
    while slug in existing:
        slug, n = f"{base}-{n}", n + 1
    return slug


def find_duplicate(paper: dict, papers: list[dict]) -> dict | None:
    key_t = normalize_title(paper.get("title", ""))
    for other in papers:
        if other is paper:
            continue
        if paper.get("arxiv") and paper.get("arxiv") == other.get("arxiv"):
            return other
        if key_t and key_t == normalize_title(other.get("title", "")):
            return other
    return None


def http_get(url: str, token: str | None = None, accept: str | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "awesome-looped-transformers-bot"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# --------------------------------------------------------------------- validation

def validate_paper(p: dict, config: dict) -> list[str]:
    errors = []
    cats = {c["id"] for c in config["categories"]}
    where = p.get("id") or p.get("title", "<untitled>")
    for field in ("id", "title", "authors", "date", "venue", "type", "category", "paper_url", "tldr"):
        if not p.get(field):
            errors.append(f"{where}: missing `{field}`")
    if p.get("date") and not DATE_RE.match(str(p["date"])):
        errors.append(f"{where}: date must be YYYY-MM-DD, got {p['date']!r}")
    if p.get("category") and p["category"] not in cats:
        errors.append(f"{where}: unknown category {p['category']!r}")
    if p.get("type") and p["type"] not in config["types"]:
        errors.append(f"{where}: unknown type {p['type']!r}")
    for tag in p.get("tags") or []:
        if tag not in config["tags"]:
            errors.append(f"{where}: unknown tag {tag!r} (add it to data/config.yaml first)")
    if not isinstance(p.get("authors", []), list):
        errors.append(f"{where}: authors must be a list")
    for field in ("paper_url", "code_url", "project_url"):
        if p.get(field) and not str(p[field]).startswith("https://"):
            errors.append(f"{where}: {field} must be an https URL")
    if p.get("code_url") and "github.com" in p["code_url"] and not parse_github(p["code_url"]):
        errors.append(f"{where}: code_url is not a valid GitHub repository URL")
    if p.get("tldr") and ("—" in p["tldr"] or len(p["tldr"]) > 260):
        errors.append(f"{where}: tldr must be one short sentence without em-dashes")
    return errors


def validate_all(papers: list[dict], resources: list[dict], config: dict) -> list[str]:
    errors = []
    seen_ids, seen_arxiv, seen_titles = {}, {}, {}
    for p in papers:
        errors += validate_paper(p, config)
        for key, seen, label in ((p.get("id"), seen_ids, "id"),
                                 (p.get("arxiv"), seen_arxiv, "arXiv id"),
                                 (normalize_title(p.get("title", "")), seen_titles, "title")):
            if key and key in seen:
                errors.append(f"duplicate {label}: {p.get('id')} and {seen[key]}")
            elif key:
                seen[key] = p.get("id")
    kinds = {k["id"] for k in config["resource_kinds"]}
    for r in resources:
        if not r.get("name") or not r.get("url") or not r.get("description"):
            errors.append(f"resource {r.get('name')!r}: needs name, url and description")
        if r.get("kind") not in kinds:
            errors.append(f"resource {r.get('name')!r}: unknown kind {r.get('kind')!r}")
    return errors
