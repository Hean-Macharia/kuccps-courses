"""Build a local JSONL knowledge corpus from public KUCCPS pages.

Run: python scripts/ingest_kuccps_knowledge.py [--max-pages 250]
Only HTTPS URLs on the official allowlist are fetched. No login or form data
is used. Review the resulting corpus and run this command periodically.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kuccps_knowledge import DEFAULT_CORPUS, OFFICIAL_HOSTS  # noqa: E402

SOURCES_FILE = ROOT / "knowledge" / "kuccps_sources.json"
USER_AGENT = "CoursesCheckerKnowledgeIndexer/1.0 (public education reference index)"
MAX_BYTES = 4 * 1024 * 1024


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.title_parts = [], [], []
        self.skip_depth = 0
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript", "svg", "iframe", "nav", "footer"}:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in {"p", "br", "li", "tr", "h1", "h2", "h3", "h4", "div", "section", "td", "th"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "iframe", "nav", "footer"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "title":
            self.in_title = False
        if tag in {"p", "li", "tr", "h1", "h2", "h3", "h4", "section", "td", "th"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if not self.skip_depth:
            self.parts.append(data)


def allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and host in OFFICIAL_HOSTS and host != "students.kuccps.net"


def fetch_public(session, url):
    """Fetch with normal certificate validation; use Windows curl/Schannel if certifi lacks OS roots."""
    try:
        response = session.get(url, timeout=18, stream=True, allow_redirects=True)
        if not allowed(response.url) or response.status_code != 200:
            return response.status_code, response.url, response.headers.get("Content-Type", ""), b""
        body = response.raw.read(MAX_BYTES + 1)
        return response.status_code, response.url, response.headers.get("Content-Type", ""), body
    except requests.exceptions.SSLError:
        if sys.platform != "win32":
            raise
        marker = b"\n__CC_META__"
        command = [
            "curl.exe", "--fail", "--silent", "--show-error", "--location",
            "--max-time", "12", "--max-filesize", str(MAX_BYTES),
            "--proto", "=https", "--proto-redir", "=https",
            "--user-agent", USER_AGENT, "--write-out", "\n__CC_META__%{url_effective}\n%{http_code}\n%{content_type}", url,
        ]
        result = subprocess.run(command, capture_output=True, timeout=15, check=False)
        if result.returncode:
            raise requests.exceptions.RequestException(result.stderr.decode("utf-8", errors="replace")[-400:])
        body, metadata = result.stdout.rsplit(marker, 1)
        final_url, status, content_type = metadata.decode("utf-8", errors="replace").splitlines()[:3]
        return int(status), final_url, content_type, body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=80)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--output", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args()
    config = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    seeds = [url for url in config["sources"] if allowed(url)]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml"})
    queue = list(dict.fromkeys(seeds))
    # Follow official-site links from the reviewed seed pages. This avoids stale
    # and legacy portal URLs often present in broad site maps.
    seen, pages = set(), []
    fetched_at = datetime.now(timezone.utc).isoformat()
    while queue and len(seen) < max(1, args.max_pages):
        url = urldefrag(queue.pop(0))[0]
        if url in seen or not allowed(url):
            continue
        seen.add(url)
        try:
            status, final_url, content_type, body = fetch_public(session, url)
            if not allowed(final_url) or status != 200:
                continue
            content_type = content_type.lower()
            if len(body) > MAX_BYTES:
                continue
            parser_html = TextExtractor()
            if "html" in content_type:
                parser_html.feed(body.decode("utf-8", errors="replace"))
                text = re.sub(r"\s+", " ", " ".join(parser_html.parts)).strip()
                title = re.sub(r"\s+", " ", " ".join(parser_html.title_parts)).strip()
            elif "pdf" in content_type or final_url.lower().endswith(".pdf"):
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(BytesIO(body))
                    text = re.sub(r"\s+", " ", " ".join(page.extract_text() or "" for page in reader.pages)).strip()
                    title = urlparse(final_url).path.rsplit("/", 1)[-1].replace("%20", " ")
                except Exception as error:
                    print(f"Skipped PDF text extraction for {final_url}: {error}", file=sys.stderr)
                    continue
            else:
                continue
            title = title or urlparse(final_url).path.strip("/") or "KUCCPS"
            if len(text) >= 180:
                pages.append({"url": final_url, "title": title, "content": text[:30000], "fetched_at": fetched_at})
            for href in parser_html.links:
                link = urldefrag(urljoin(final_url, href))[0]
                if allowed(link) and not urlparse(link).query and link not in seen and len(queue) < args.max_pages * 6:
                    queue.append(link)
        except requests.RequestException as error:
            print(f"Skipped {url}: {error}", file=sys.stderr)
        time.sleep(max(0, args.delay))
    if not pages:
        raise SystemExit("No official content was indexed; the existing corpus was left unchanged.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    chunk_count = 0
    with temporary.open("w", encoding="utf-8") as corpus:
        for page in pages:
            text = page.pop("content")
            start = 0
            while start < len(text):
                chunk = text[start:start + 1800]
                if len(chunk) >= 180:
                    record = dict(page, content=chunk)
                    corpus.write(json.dumps(record, ensure_ascii=False) + "\n")
                    chunk_count += 1
                if start + 1800 >= len(text):
                    break
                start += 1500
    temporary.replace(args.output)
    print(f"Indexed {chunk_count} passages from {len(pages)} official pages ({len(seen)} URLs visited) into {args.output}")


if __name__ == "__main__":
    main()
