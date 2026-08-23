#!/usr/bin/env python3
"""
CCAS Automatic Blog RSS Generator
Discovers CCAS blog posts and generates docs/rss.xml.
Designed for GitHub Actions + GitHub Pages.
"""

from __future__ import annotations
import html
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

SITE = "https://ccas.global"
BLOG_PAGE = "https://ccas.global/ccas-%7C-blogs-%26-media"
OUTPUT = Path("docs/rss.xml")
MAX_ITEMS = 50

HEADERS = {
    "User-Agent": "CCAS-RSS-Bot/1.0 (+https://ccas.global/)",
    "Accept-Language": "en-US,en;q=0.9",
}

BLOG_PATH_RE = re.compile(r"/ccas-(?:%7C|\|)-blogs-(?:%26|&)-media/f/", re.I)

def fetch(url: str) -> requests.Response:
    r = requests.get(url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    return r

def canonicalize(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))

def discover_from_sitemaps() -> set[str]:
    urls: set[str] = set()
    candidates = [
        f"{SITE}/sitemap.xml",
        f"{SITE}/sitemap_index.xml",
        f"{SITE}/sitemap1.xml",
    ]
    seen_sitemaps = set()

    def parse_sitemap(url: str, depth: int = 0):
        if depth > 3 or url in seen_sitemaps:
            return
        seen_sitemaps.add(url)
        try:
            r = fetch(url)
        except Exception:
            return
        soup = BeautifulSoup(r.content, "xml")
        # sitemap index
        for loc in soup.find_all("loc"):
            val = (loc.get_text() or "").strip()
            if not val:
                continue
            if val.lower().endswith(".xml"):
                parse_sitemap(val, depth + 1)
            elif BLOG_PATH_RE.search(val):
                urls.add(canonicalize(val))

    for s in candidates:
        parse_sitemap(s)
    return urls

def discover_from_blog_page() -> set[str]:
    urls: set[str] = set()
    try:
        r = fetch(BLOG_PAGE)
    except Exception as e:
        print(f"Blog page discovery failed: {e}", file=sys.stderr)
        return urls
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = urljoin(r.url, a["href"])
        if BLOG_PATH_RE.search(href):
            urls.add(canonicalize(href))
    # Also catch links embedded in script/JSON data.
    for m in re.findall(r'https?://[^"\'<>\s]+/ccas-(?:%7C|\|)-blogs-(?:%26|&)-media/f/[^"\'<>\s?]+', r.text, re.I):
        urls.add(canonicalize(html.unescape(m)))
    return urls

def text_meta(soup: BeautifulSoup, *selectors: tuple[str, str]) -> str:
    for attr, key in selectors:
        tag = soup.find("meta", attrs={attr: key})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""

def parse_date(soup: BeautifulSoup, page_text: str) -> datetime | None:
    candidates = []
    for attrs in (
        {"property": "article:published_time"},
        {"name": "date"},
        {"name": "pubdate"},
        {"itemprop": "datePublished"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            candidates.append(tag["content"].strip())

    time_tag = soup.find("time")
    if time_tag:
        candidates.extend([
            time_tag.get("datetime", "").strip(),
            time_tag.get_text(" ", strip=True),
        ])

    # GoDaddy blog pages visibly render dates such as "June 10, 2026"
    m = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"\d{1,2},\s+\d{4}\b",
        page_text,
        re.I,
    )
    if m:
        candidates.append(m.group(0))

    for raw in candidates:
        if not raw:
            continue
        try:
            s = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                pass
        try:
            dt = parsedate_to_datetime(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def clean_description(value: str, title: str) -> str:
    value = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return f"Read {title} from CA Corporate & Attorney Services Inc. on CCAS.global."
    if len(value) > 420:
        value = value[:417].rsplit(" ", 1)[0] + "..."
    return value

def get_post(url: str) -> dict | None:
    try:
        r = fetch(url)
    except Exception as e:
        print(f"Skipping {url}: {e}", file=sys.stderr)
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    canonical = ""
    can = soup.find("link", rel=lambda x: x and "canonical" in x)
    if can and can.get("href"):
        canonical = canonicalize(urljoin(r.url, can["href"]))
    url = canonical or canonicalize(r.url)

    title = (
        text_meta(soup, ("property", "og:title"), ("name", "twitter:title"))
        or (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
        or (soup.title.get_text(" ", strip=True) if soup.title else "")
    )
    title = re.sub(r"\s*\|\s*CCAS.*$", "", title, flags=re.I).strip()
    if not title:
        return None

    desc = text_meta(
        soup,
        ("property", "og:description"),
        ("name", "description"),
        ("name", "twitter:description"),
    )
    desc = clean_description(desc, title)

    date = parse_date(soup, soup.get_text(" ", strip=True))
    if date is None:
        date = datetime.now(timezone.utc)

    category = "CCAS Blog"
    # Try visible category links/tag metadata.
    cat = soup.find("meta", attrs={"property": "article:section"})
    if cat and cat.get("content"):
        category = cat["content"].strip()

    return {
        "title": title,
        "link": url,
        "description": desc,
        "pubdate": date,
        "category": category,
    }

def xml_escape(s: str) -> str:
    return html.escape(str(s), quote=True)

def build_feed(posts: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        '    <title>CCAS Global Compliance Blog</title>',
        f'    <link>{xml_escape(BLOG_PAGE)}</link>',
        '    <description>Corporate compliance news, UCC filing and search updates, apostille and consular legalization guidance, registered agent requirements, Secretary of State filing developments, Puerto Rico business compliance, public-record research, and legal support insights from CA Corporate &amp; Attorney Services Inc.</description>',
        '    <language>en-us</language>',
        f'    <lastBuildDate>{format_datetime(now)}</lastBuildDate>',
        '    <generator>CCAS Automatic RSS Generator</generator>',
        '    <copyright>CA Corporate &amp; Attorney Services Inc.</copyright>',
        '    <managingEditor>solutions@ccas.global (CCAS)</managingEditor>',
        '    <webMaster>solutions@ccas.global (CCAS)</webMaster>',
        '    <ttl>60</ttl>',
        '    <atom:link href="https://YOUR-GITHUB-PAGES-URL/rss.xml" rel="self" type="application/rss+xml" />',
    ]

    for p in posts[:MAX_ITEMS]:
        lines += [
            '    <item>',
            f'      <title>{xml_escape(p["title"])}</title>',
            f'      <link>{xml_escape(p["link"])}</link>',
            f'      <guid isPermaLink="true">{xml_escape(p["link"])}</guid>',
            f'      <pubDate>{format_datetime(p["pubdate"])}</pubDate>',
            f'      <category>{xml_escape(p["category"])}</category>',
            f'      <description>{xml_escape(p["description"])}</description>',
            '    </item>',
        ]

    lines += ['  </channel>', '</rss>', '']
    return "\n".join(lines)

def main():
    urls = discover_from_sitemaps()
    urls |= discover_from_blog_page()

    print(f"Discovered {len(urls)} candidate blog posts.")
    posts = []
    for i, url in enumerate(sorted(urls), 1):
        print(f"[{i}/{len(urls)}] {url}")
        p = get_post(url)
        if p:
            posts.append(p)

    if not posts:
        raise SystemExit(
            "No blog posts discovered. The site may have changed or blocked automated requests."
        )

    # Dedupe canonical URLs and sort newest first.
    deduped = {}
    for p in posts:
        deduped[p["link"]] = p
    posts = sorted(
        deduped.values(),
        key=lambda p: p["pubdate"],
        reverse=True,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_feed(posts), encoding="utf-8")
    print(f"Wrote {OUTPUT} with {min(len(posts), MAX_ITEMS)} items.")

if __name__ == "__main__":
    main()
