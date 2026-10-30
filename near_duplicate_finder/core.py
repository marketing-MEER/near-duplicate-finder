"""Find exact and near-duplicate pages with 5-word shingles and Jaccard similarity.

Thresholds (general practice for shingle-based duplicate detection):
- exact duplicate: identical main text,
- near duplicate: 80% or more of the 5-word shingles shared (--near),
- similar: 30% or more (--similar), worth a look: shared paragraphs, often fine (e.g. product variants).
NP Digital (keyword-cannibalization): duplicate-keyword overlap grows with site age, and the insight is to
consolidate competing URLs into one stronger page. Each cluster gets a suggested page to keep.
"""
import hashlib
import re
import time
from collections import deque
from pathlib import Path
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlsplit
from xml.etree import ElementTree

import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import similarity

USER_AGENT = "near-duplicate-finder/1.0 (+https://github.com/marketing-MEER/near-duplicate-finder)"
BOILERPLATE = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "template"]
THIN_WORDS = 100  # very little main text; a common rule of thumb, not a Google rule


class Fetcher:
    """Polite GETs: own user agent, at least 0.5 s between requests."""

    def __init__(self, delay=0.5, timeout=20, session=None):
        self.delay, self.timeout = max(delay, 0.5), timeout
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last, self.requests = 0.0, 0

    def get(self, url):
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0 and self.requests:
            time.sleep(wait)
        self._last = time.monotonic()
        self.requests += 1
        try:
            return self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            return exc


def main_text(html: str):
    """(title, canonical href, main text) with navigation, header, footer and scripts removed."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    can = soup.find("link", rel="canonical", href=True)
    for tag in soup(BOILERPLATE):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    return title, (can["href"].strip() if can else ""), " ".join(root.get_text(" ").split())


def _sitemap(url, fetch):
    r = fetch.get(url)
    if isinstance(r, Exception) or r.status_code != 200:
        return []
    try:
        root = ElementTree.fromstring(r.content)
    except ElementTree.ParseError:
        return []
    locs = [e.text.strip() for e in root.iter() if e.tag.endswith("loc") and e.text]
    return [u for loc in locs for u in _sitemap(loc, fetch)] if root.tag.endswith("sitemapindex") else locs


def load(source: str, fetch: Fetcher, max_pages=500):
    """Yield page dicts (url, status, title, canonical, text) from a folder, URL list, sitemap or crawl."""
    path = Path(source)
    if not re.match(r"^https?://", source, re.I) and path.is_dir():
        for f in sorted(path.rglob("*"))[:max_pages * 3]:
            if f.suffix.lower() in (".html", ".htm"):
                title, can, text = main_text(f.read_text(encoding="utf-8", errors="replace"))
            elif f.suffix.lower() in (".txt", ".md"):
                title, can, text = f.stem, "", " ".join(f.read_text(encoding="utf-8", errors="replace").split())
            else:
                continue
            yield {"url": f.relative_to(path).as_posix(), "status": "file", "title": title, "canonical": can,
                   "text": text}
        return
    if not re.match(r"^https?://", source, re.I) and path.exists():
        urls = [m.group(0) for line in path.read_text(encoding="utf-8-sig").splitlines()
                for m in [re.search(r"https?://[^\s,;\"']+", line)] if m]
        yield from _fetch_all(list(dict.fromkeys(urls))[:max_pages], fetch)
    elif urlsplit(source).path.lower().endswith(".xml"):
        yield from _fetch_all(list(dict.fromkeys(_sitemap(source, fetch)))[:max_pages], fetch)
    else:
        yield from _crawl(source if re.match(r"^https?://", source, re.I) else "https://" + source, fetch, max_pages)


def _page(url, r):
    if isinstance(r, Exception):
        return {"url": url, "status": "failed", "title": "", "canonical": "", "text": ""}
    if r.status_code != 200 or "html" not in r.headers.get("Content-Type", "text/html"):
        return {"url": url, "status": r.status_code, "title": "", "canonical": "", "text": ""}
    title, can, text = main_text(r.text)
    return {"url": url, "status": 200, "title": title, "canonical": urljoin(url, can) if can else "", "text": text,
            "_html": r.text}


def _fetch_all(urls, fetch):
    for u in urls:
        p = _page(u, fetch.get(u))
        p.pop("_html", None)
        yield p


def _crawl(start, fetch, max_pages):
    host = urlsplit(start).netloc.lower()
    base = f"{urlsplit(start).scheme}://{host}"
    robots = robotparser.RobotFileParser()
    r = fetch.get(base + "/robots.txt")
    robots.parse(r.text.splitlines() if not isinstance(r, Exception) and r.status_code == 200 else [])
    queue, seen, count = deque([start]), {start}, 0
    while queue and count < max_pages:
        url = queue.popleft()
        if not robots.can_fetch(USER_AGENT, url):
            continue
        p = _page(url, fetch.get(url))
        count += 1
        html = p.pop("_html", "")
        if html:
            for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
                t = urldefrag(urljoin(url, a["href"].strip()))[0]
                if urlsplit(t).netloc.lower() == host and t.startswith(("http://", "https://")) and t not in seen \
                        and not re.search(r"\.(?:jpe?g|png|gif|webp|svg|pdf|zip|css|js|xml)$", t, re.I):
                    seen.add(t)
                    queue.append(t)
        yield p


def analyse(pages: list, near=0.8, similar=0.3, k=5):
    ok = [p for p in pages if p["text"]]
    words = {p["url"]: len(similarity.tokens(p["text"])) for p in ok}
    digest = {p["url"]: hashlib.sha1(" ".join(similarity.tokens(p["text"])).encode()).hexdigest() for p in ok}
    canon = {p["url"]: p.get("canonical") or "" for p in ok}
    docs = {p["url"]: similarity.shingles(p["text"], k) for p in ok}
    found = similarity.similar_pairs(docs, threshold=similar)
    pairs = []
    for a, b, j in found:
        kind = "exact duplicate" if digest[a] == digest[b] else ("near duplicate" if j >= near else "similar")
        handled = (bool(canon[a]) and canon[a] == canon[b]) or canon[a] == b or canon[b] == a
        pairs.append({"page_a": a, "page_b": b, "similarity": round(100 * j, 1), "type": kind,
                      "words_a": words[a], "words_b": words[b], "canonical_handles_it": "yes" if handled else "no"})
    pair_df = pd.DataFrame(pairs, columns=["page_a", "page_b", "similarity", "type", "words_a", "words_b",
                                           "canonical_handles_it"])
    dup = [(a, b, j) for a, b, j in found if j >= near]
    cl = similarity.clusters(dup, list(docs))
    cluster_rows = []
    for cid in sorted(set(cl.values())):
        members = sorted((u for u, c in cl.items() if c == cid), key=lambda u: (-words[u], len(u), u))
        sims = [100 * j for a, b, j in dup if cl[a] == cid]
        cluster_rows.append({"cluster": cid, "pages": len(members), "keep": members[0],
                             "merge_or_redirect": " | ".join(members[1:]),
                             "max_similarity": round(max(sims), 1), "min_similarity": round(min(sims), 1)})
    cluster_df = pd.DataFrame(cluster_rows, columns=["cluster", "pages", "keep", "merge_or_redirect",
                                                     "max_similarity", "min_similarity"])
    best = {}
    for a, b, j in found:
        for u, other in ((a, b), (b, a)):
            if j > best.get(u, (0, ""))[0]:
                best[u] = (j, other)
    rows = []
    for p in pages:
        u = p["url"]
        w = words.get(u, 0)
        if not p["text"]:
            verdict = "no text" if p["status"] in (200, "file") else f"not checked ({p['status']})"
        elif u in cl:
            verdict = "keep" if any(r["keep"] == u for r in cluster_rows) else "consolidate"
        elif u in best:
            verdict = "similar, review"
        else:
            verdict = "unique"
        rows.append({"url": u, "status": p["status"], "title": p["title"][:100], "words": w,
                     "thin": "yes" if p["text"] and w < THIN_WORDS else "no", "cluster": cl.get(u, ""),
                     "closest_page": best.get(u, (0, ""))[1],
                     "closest_similarity": round(100 * best[u][0], 1) if u in best else "", "verdict": verdict})
    page_df = pd.DataFrame(rows, columns=["url", "status", "title", "words", "thin", "cluster", "closest_page",
                                          "closest_similarity", "verdict"])
    return {"pairs": pair_df, "clusters": cluster_df, "pages": page_df}


def audit(source, delay=0.5, max_pages=500, near=0.8, similar=0.3, fetch=None):
    fetch = fetch or Fetcher(delay=delay)
    pages = list(load(source, fetch, max_pages))
    out = analyse(pages, near=near, similar=similar)
    out["requests"] = fetch.requests
    return out
