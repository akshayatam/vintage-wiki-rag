import os, re, json, time, pathlib, requests
from urllib.parse import urlparse, parse_qs, unquote
from dotenv import load_dotenv
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()
API_KEY = os.getenv("ANYCRAWL_API_KEY")
if not API_KEY:
    raise SystemExit("❌ ANYCRAWL_API_KEY missing in .env")

SCRAPE_URL = "https://api.anycrawl.dev/v1/scrape"
JOB_URL    = "https://api.anycrawl.dev/v1/jobs/{job_id}"

OUT_DIR = pathlib.Path("data");  OUT_DIR.mkdir(exist_ok=True)
ERR_DIR = pathlib.Path("errors"); ERR_DIR.mkdir(exist_ok=True)

# Session with retries for 429/5xx
session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=Retry(
    total=5, backoff_factor=0.8, status_forcelist=(429,500,502,503,504),
    allowed_methods=frozenset(["GET","POST"])
)))
HEADERS = {"Content-Type":"application/json","Accept":"application/json","Authorization":f"Bearer {API_KEY}"}

def title_from_url(url: str) -> str:
    u = urlparse(url)
    if u.path.startswith("/index.php"):
        q = parse_qs(u.query)
        if "title" in q: return unquote(q["title"][0])
        if "/index.php/" in u.path: return unquote(u.path.split("/index.php/",1)[-1])
    if "/wiki/" in u.path:
        return unquote(u.path.split("/wiki/",1)[-1])
    return unquote(u.path.strip("/"))

def safe_name(s: str) -> str:
    return re.sub(r"[^\w\-.]+","_", s).strip("_")[:150] or "page"

def write_error_blob(url, resp_or_text, suffix="txt"):
    name = safe_name(title_from_url(url)) + f".{suffix}"
    p = ERR_DIR / name
    try:
        if isinstance(resp_or_text, requests.Response):
            head = resp_or_text.text[:2000]
            ct   = resp_or_text.headers.get("Content-Type","")
            st   = resp_or_text.status_code
            p.write_text(f"URL: {url}\nSTATUS: {st}\nCT: {ct}\n--- BODY HEAD ---\n{head}", encoding="utf-8")
        else:
            p.write_text(resp_or_text, encoding="utf-8")
    except Exception:
        pass

def poll_job(job_id, timeout_s=90, interval_s=2.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = session.get(JOB_URL.format(job_id=job_id), headers=HEADERS, timeout=30)
        if "application/json" in r.headers.get("Content-Type",""):
            data = r.json()
            status = data.get("data",{}).get("status") or data.get("status")
            if status == "completed": return data
            if status in ("failed","errored"): return data
        time.sleep(interval_s)
    return {"success": False, "error": "poll_timeout", "jobId": job_id}

def scrape_page(url):
    payload = {
        "url": url,
        "engine": "playwright",
        "formats": ["markdown","json"],
        # optional stabilizers:
        # "wait_until": "networkidle",
        # "timeout": 60000
    }
    r = session.post(SCRAPE_URL, headers=HEADERS, json=payload, timeout=60)

    # Guard 1: must be JSON and non-empty
    ct = r.headers.get("Content-Type","")
    if "application/json" not in ct or not r.text.strip():
        write_error_blob(url, r)
        return None

    # Guard 2: JSON decode with retries (handles empty/partial bodies)
    for attempt in range(3):
        try:
            data = r.json()
            break
        except ValueError:
            time.sleep(0.8 * (attempt+1))
    else:
        write_error_blob(url, r)
        return None

    # If job not completed yet, poll
    job_id = data.get("jobId") or data.get("data",{}).get("jobId")
    status = data.get("status") or data.get("data",{}).get("status")
    if job_id and status and status != "completed":
        data = poll_job(job_id)

    return data

if __name__ == "__main__":
    # Load links and filter for Alps (case-insensitive), skip namespaces like File:
    with open("links.json","r",encoding="utf-8") as f:
        all_links = json.load(f)
    def is_namespaced(title): return bool(re.match(r"^(File|Talk|Special|Help|Template|User|Portal):", title, flags=re.I))
    alps_links = []
    seen = set()
    for u in all_links:
        if u in seen: continue
        seen.add(u)
        t = title_from_url(u)
        if "alps" not in (u.lower()+t.lower()): continue
        if is_namespaced(t): continue
        alps_links.append(u)
    print(f"Found {len(alps_links)} Alps-related links.")

    # Resume: skip already-saved files
    to_fetch = []
    for link in alps_links:
        out_path = OUT_DIR / (safe_name(title_from_url(link)) + ".json")
        if not out_path.exists():
            to_fetch.append(link)
    if len(to_fetch) != len(alps_links):
        print(f"Resuming: {len(alps_links)-len(to_fetch)} already saved, {len(to_fetch)} remaining.")

    for link in tqdm(to_fetch, desc="Scraping Alps pages"):
        try:
            data = scrape_page(link)
            if not data:
                continue
            if data.get("success") is False:
                # Save failure JSON for inspection
                (ERR_DIR / (safe_name(title_from_url(link)) + ".json")).write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                continue
            # Save success
            (OUT_DIR / (safe_name(title_from_url(link)) + ".json")).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            # Last-resort catch; log minimal info and continue
            (ERR_DIR / (safe_name(title_from_url(link)) + ".txt")).write_text(
                f"Unhandled: {e}", encoding="utf-8"
            )
        finally:
            time.sleep(1.2)
