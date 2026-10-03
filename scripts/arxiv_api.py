"""Tiny arXiv API client (stdlib only)."""

from __future__ import annotations

import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

from common import GITHUB_RE, http_get

API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom",
      "os": "http://a9.com/-/spec/opensearch/1.1/"}

VENUES = [
    "NeurIPS", "ICML", "ICLR", "CVPR", "ICCV", "ECCV", "ACL", "EMNLP", "NAACL", "COLM", "AAAI", "IJCAI",
    "TMLR", "JMLR", "AISTATS", "UAI", "COLT", "KDD", "WACV", "BMVC", "Interspeech", "ICASSP", "CoRL",
    "RSS", "ICRA", "LoG", "COLING", "EACL", "SIGGRAPH", "Nature", "Science",
]
VENUE_RE = re.compile(r"\b(" + "|".join(VENUES) + r")\b[\s'’]*(?:20)?(\d{2})\b")
WORKSHOP_RE = re.compile(r"workshop", re.I)
NOT_ACCEPTED_RE = re.compile(r"under review|submitted to|in submission|submission to|preprint", re.I)


def guess_venue(*texts: str | None) -> str | None:
    for text in texts:
        if not text or NOT_ACCEPTED_RE.search(text):
            continue
        m = VENUE_RE.search(text)
        if m:
            name = m.group(1)
            year = "20" + m.group(2)[-2:]
            suffix = " Workshop" if WORKSHOP_RE.search(text) else ""
            return f"{name} {year}{suffix}"
    return None


def _entry_to_dict(entry: ET.Element) -> dict:
    def text(tag):
        el = entry.find(tag, NS)
        return " ".join(el.text.split()) if el is not None and el.text else None

    arxiv_id = re.sub(r"v\d+$", "", text("a:id").rsplit("/abs/", 1)[-1])
    authors = [" ".join(a.find("a:name", NS).text.split()) for a in entry.findall("a:author", NS)]
    authors = [a.strip(" :;,") for a in authors if re.search(r"\w", a)]  # drop stray ":" tokens
    if len(authors) > 6:
        authors = authors[:5] + ["et al."]
    summary = text("a:summary") or ""
    comment = text("arxiv:comment")
    journal = text("arxiv:journal_ref")
    code = None
    for blob in (comment, summary):
        m = GITHUB_RE.search(blob or "")
        if m:
            code = f"https://github.com/{m.group(1)}/{re.sub(r'[.,;)]+$', '', m.group(2))}"
            break
    return {
        "title": text("a:title"),
        "authors": authors,
        "date": (text("a:published") or "")[:10],
        "venue": guess_venue(journal, comment) or "arXiv",
        "arxiv": arxiv_id,
        "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
        "code_url": code,
        "abstract": summary,
        "categories": [c.get("term") for c in entry.findall("a:category", NS)],
    }


def _query_page(params: dict, retries: int = 3) -> tuple[list[dict], int]:
    """One API call. Returns (entries, opensearch:totalResults)."""
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            root = ET.fromstring(http_get(url, timeout=60))
            total = int(root.findtext("os:totalResults", "0", NS) or 0)
            entries = [_entry_to_dict(e) for e in root.findall("a:entry", NS)
                       if e.find("a:title", NS) is not None and "api/errors" not in (e.findtext("a:id", "", NS))]
            return entries, total
        except Exception:  # noqa: BLE001 - arXiv is flaky; retry politely
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    return [], 0


def _query(params: dict, retries: int = 3) -> list[dict]:
    return _query_page(params, retries)[0]


def fetch(arxiv_id: str) -> dict | None:
    results = _query({"id_list": arxiv_id, "max_results": 1})
    return results[0] if results else None


def search(query: str, max_results: int = 100, stop_before: str | None = None, page: int = 200) -> list[dict]:
    """Newest-first search, paging until `max_results` or until entries are older than `stop_before`.

    arXiv occasionally returns an empty page in the middle of a result set, so an empty page before
    `totalResults` is reached is retried instead of being treated as the end.
    """
    out: list[dict] = []
    start = 0
    while start < max_results:
        params = {"search_query": query, "sortBy": "submittedDate", "sortOrder": "descending",
                  "start": start, "max_results": min(page, max_results - start)}
        for attempt in range(4):
            batch, total = _query_page(params)
            if batch or start >= total:
                break
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"arXiv kept returning empty pages at offset {start} of {total}")
        out += batch
        start += len(batch)
        if not batch or start >= total or (stop_before and batch[-1]["date"] < stop_before):
            break
        time.sleep(3)
    return out
