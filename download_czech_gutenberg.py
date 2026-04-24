import argparse
import csv
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE_URL = "https://www.gutenberg.org"
USER_AGENT = "Mozilla/5.0 (compatible; BookAnalysisDownloader/1.0)"


class GutenbergListParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = None
        for name, value in attrs:
            if name == "href":
                href = value
                break
        if not href:
            return
        if href.startswith("/ebooks/") and href[8:].isdigit():
            self.links.append(href)


class GutenbergBookParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.plain_text_url = None
        self.title = None
        self.author = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
            return

        if tag == "meta":
            attrs = dict(attrs)
            name = attrs.get("name", "").lower()
            content = attrs.get("content", "").strip()
            if name == "title" and content:
                self.title = content
            elif name in ("creator", "author") and content:
                self.author = content
            return

        if tag != "a" or self.plain_text_url:
            return

        href = None
        for name, value in attrs:
            if name == "href":
                href = value
                break
        if not href:
            return

        href_lower = href.lower()
        if ".txt" in href_lower and ("plain" in href_lower or "utf-8" in href_lower or "txt" in href_lower):
            self.plain_text_url = href

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            title = data.strip()
            if title:
                self.title = title


def fetch_url(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset("utf-8")
        return response.read().decode(charset, errors="replace")


def download_bytes(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def decode_text(content):
    for encoding in ("utf-8", "iso-8859-2", "windows-1250", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def parse_ebook_links(html):
    parser = GutenbergListParser()
    parser.feed(html)
    unique = []
    seen = set()
    for href in parser.links:
        if href not in seen:
            seen.add(href)
            unique.append(href)
    return unique


def find_text_link(html, base_url):
    parser = GutenbergBookParser()
    parser.feed(html)
    href = parser.plain_text_url
    if href:
        return urllib.parse.urljoin(base_url, href)
    for match in re.finditer(r'href=["\']([^"\']+\.txt)["\']', html, re.IGNORECASE):
        return urllib.parse.urljoin(base_url, match.group(1))
    return None


def safe_filename(text):
    clean = re.sub(r"[\\/:*?\"<>|]+", "-", text)
    clean = re.sub(r"\s+", "_", clean).strip("_-")
    if not clean:
        return "ebook"
    return clean


def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_header_metadata(text):
    metadata = {}
    for line in text.splitlines()[:200]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            continue
        if key in ("Title", "Author", "Translator", "Language", "Release Date", "Release-Date"):
            metadata[key] = value
        if len(metadata) >= 5:
            break
    return metadata


def clean_gutenberg_text(text):
    text = normalize_newlines(text)
    start_patterns = [
        r"\*\*\*\s*start of (this|the) project gutenberg ebook.*?\*\*\*",
        r"\*\*\*\s*start of project gutenberg.*?\*\*\*",
        r"start of the project gutenberg e?book",
    ]
    end_patterns = [
        r"\*\*\*\s*end of (this|the) project gutenberg ebook.*?\*\*\*",
        r"\*\*\*\s*end of project gutenberg.*?\*\*\*",
        r"end of the project gutenberg e?book",
    ]

    start_index = 0
    for pattern in start_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            start_index = match.end()
            break

    end_index = len(text)
    for pattern in end_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            end_index = match.start()
            break

    body = text[start_index:end_index].strip()

    # Remove repeated Gutenberg header/footer text that may remain
    body = re.sub(r"^\s*project gutenberg[^\n]*\n", "", body, flags=re.IGNORECASE)
    body = re.sub(r"\n\s*project gutenberg[^\n]*$", "", body, flags=re.IGNORECASE)
    return body.strip()


def summarize_text(text, metadata):
    clean = clean_gutenberg_text(text)
    metadata = metadata.copy()
    header_metadata = extract_header_metadata(text)
    metadata.update(header_metadata)

    title = metadata.get("Title") or metadata.get("title") or "Unknown"
    author = metadata.get("Author") or metadata.get("creator") or "Unknown"
    word_count = len(clean.split())
    char_count = len(clean)
    return {
        "title": title,
        "author": author,
        "word_count": word_count,
        "char_count": char_count,
        "clean_text": clean,
    }


def download_book(ebook_path, output_dir, skip_existing=True):
    ebook_id = ebook_path.split("/")[-1]
    book_url = urllib.parse.urljoin(BASE_URL, ebook_path)
    print(f"Fetching metadata for ebook {ebook_id}...")

    try:
        book_html = fetch_url(book_url)
    except urllib.error.HTTPError as exc:
        print(f"  Skipped {ebook_id}: HTTP error {exc.code}")
        return None
    except urllib.error.URLError as exc:
        print(f"  Skipped {ebook_id}: URL error {exc.reason}")
        return None

    book_parser = GutenbergBookParser()
    book_parser.feed(book_html)
    title_guess = book_parser.title or f"ebook_{ebook_id}"
    author_guess = book_parser.author or "Unknown"
    filename_base = safe_filename(f"{ebook_id}_{title_guess}")[:200]
    output_path = os.path.join(output_dir, f"{filename_base}.txt")

    if skip_existing and os.path.exists(output_path):
        print(f"  Skipped {ebook_id}: already downloaded as {output_path}")
        return {
            "ebook_id": ebook_id,
            "title": title_guess,
            "author": author_guess,
            "filename": os.path.basename(output_path),
            "skipped": True,
        }

    text_url = find_text_link(book_html, book_url)
    if not text_url:
        fallback = f"https://www.gutenberg.org/cache/epub/{ebook_id}/pg{ebook_id}.txt"
        print(f"  No direct text link found, trying fallback {fallback}")
        text_url = fallback

    try:
        print(f"  Downloading text from {text_url}")
        raw_bytes = download_bytes(text_url)
    except urllib.error.HTTPError as exc:
        print(f"  Skipped {ebook_id}: HTTP error {exc.code} for text file")
        return None
    except urllib.error.URLError as exc:
        print(f"  Skipped {ebook_id}: URL error {exc.reason} for text file")
        return None

    raw_text = decode_text(raw_bytes)
    summary = summarize_text(raw_text, {"title": title_guess, "author": author_guess})

    with open(output_path, "w", encoding="utf-8", newline="\n") as out_file:
        out_file.write(summary["clean_text"])

    print(f"  Saved cleaned text to {output_path}")
    return {
        "ebook_id": ebook_id,
        "title": summary["title"],
        "author": summary["author"],
        "word_count": summary["word_count"],
        "char_count": summary["char_count"],
        "filename": os.path.basename(output_path),
        "source_url": text_url,
        "skipped": False,
    }


def write_summary(output_dir, rows, summary_file):
    summary_path = os.path.join(output_dir, summary_file)
    fieldnames = [
        "ebook_id",
        "title",
        "author",
        "word_count",
        "char_count",
        "filename",
        "source_url",
        "skipped",
    ]
    with open(summary_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Summary written to {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Download Czech Project Gutenberg ebooks from https://www.gutenberg.org/browse/languages/cs"
    )
    parser.add_argument("--output-dir", required=True, help="Directory to save downloaded text files")
    parser.add_argument("--max-books", type=int, default=None, help="Maximum number of ebooks to download")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between requests")
    parser.add_argument("--no-skip", action="store_true", help="Redownload files even if they already exist")
    parser.add_argument(
        "--summary-file",
        default="summary.csv",
        help="CSV file name to store the ebook metadata summary",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("Fetching Czech Gutenberg language page...")
    try:
        index_html = fetch_url(f"{BASE_URL}/browse/languages/cs")
    except Exception as exc:
        print(f"Failed to fetch the language index: {exc}")
        sys.exit(1)

    ebook_links = parse_ebook_links(index_html)
    if not ebook_links:
        print("No ebook links found on the Czech Gutenberg page.")
        sys.exit(1)

    if args.max_books:
        ebook_links = ebook_links[: args.max_books]

    print(f"Found {len(ebook_links)} Czech ebooks. Starting download...")
    rows = []
    for idx, ebook_path in enumerate(ebook_links, start=1):
        print(f"[{idx}/{len(ebook_links)}] {ebook_path}")
        book_summary = download_book(ebook_path, args.output_dir, skip_existing=not args.no_skip)
        if book_summary is not None:
            rows.append(book_summary)
        time.sleep(args.delay)

    if rows:
        write_summary(args.output_dir, rows, args.summary_file)

    downloaded = len([row for row in rows if not row.get("skipped")])
    print(f"Downloaded or processed {downloaded}/{len(rows)} books.")


if __name__ == "__main__":
    main()
