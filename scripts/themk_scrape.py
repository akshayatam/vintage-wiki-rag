import time
import requests
import xml.etree.ElementTree as ET
from pathlib import Path

API_URL = "https://wiki.themk.org/api.php"
EXPORT_URL = "https://wiki.themk.org/index.php?title=Special:Export&action=submit"

OUT_DIR = Path("themk_exports")
OUT_DIR.mkdir(exist_ok=True)

BATCH_SIZE = 25
SLEEP_BETWEEN_BATCHES = 4
MAX_RETRIES = 5
REQUEST_TIMEOUT = 120

session = requests.Session()
session.headers.update({
    "User-Agent": "themk-exporter/1.0 (personal archival/RAG research; respectful rate limiting)"
})

def is_valid_xml_file(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        ET.parse(path)
        return True
    except ET.ParseError:
        return False

def get_all_pages(namespace=0):
    titles = []
    params = {
        "action": "query",
        "list": "allpages",
        "aplimit": "max",
        "apnamespace": namespace,
        "format": "json",
        "maxlag": "5",
    }

    while True:
        r = session.get(API_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        for page in data["query"]["allpages"]:
            titles.append(page["title"])

        if "continue" not in data:
            break

        params["apcontinue"] = data["continue"]["apcontinue"]
        time.sleep(1)

    return titles

def export_batch(titles, batch_num):
    out_file = OUT_DIR / f"themk_batch_{batch_num:03d}.xml"
    part_file = OUT_DIR / f"themk_batch_{batch_num:03d}.xml.part"

    if is_valid_xml_file(out_file):
        print(f"Skipping existing valid batch: {out_file}")
        return True

    payload = {
        "pages": "\n".join(titles),
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.post(EXPORT_URL, data=payload, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()

            # Basic sanity checks before writing
            content = r.content
            if not content.strip():
                raise ValueError("Empty response")

            # Save temporary file first
            part_file.write_bytes(content)

            # Validate XML
            try:
                ET.parse(part_file)
            except ET.ParseError as e:
                text_preview = content[:500].decode("utf-8", errors="replace")
                raise ValueError(f"Invalid XML response. Preview:\n{text_preview}") from e

            part_file.replace(out_file)
            print(f"Saved {out_file} ({len(titles)} pages)")
            return True

        except Exception as e:
            wait = min(60, 2 ** attempt)
            print(f"Batch {batch_num} failed on attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"Giving up on batch {batch_num}")
                return False

def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

if __name__ == "__main__":
    titles = get_all_pages(namespace=0)
    print(f"Found {len(titles)} pages")

    all_batches = list(chunks(titles, BATCH_SIZE))

    for i, batch in enumerate(all_batches, start=1):
        ok = export_batch(batch, i)

        # Always pause, even after success
        time.sleep(SLEEP_BETWEEN_BATCHES)

        # Optional: stop on first hard failure so you can inspect
        if not ok:
            print(f"Stopped at batch {i}")
            break