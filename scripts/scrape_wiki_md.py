import os 
import json 
import time 
import re 
import pathlib 
import requests 

from urllib.parse import unquote, urlparse, parse_qs 
from dotenv import load_dotenv 

load_dotenv() 

OUT_DIR = pathlib.Path("data/alps") 
OUT_DIR.mkdir(parents=True, exist_ok=True) 

API_KEY = os.getenv("ANYCRAWL_API_KEY") 
if not API_KEY: 
    raise SystemExit("Set ANYCRAWL_API_KEY in your environment.") 

SCRAPE_URL = "https://api.anycrawl.dev/v1/scrape" 
HEADERS = { 
    "Content-Type": "application/json", 
    "Authorization": f"Bearer {API_KEY}", 
    "Accept": "application.json", 
} 

def title_from_url(url: str) -> str: 
    u = urlparse(url) 
    if u.path.startswith("/index.php"): 
        q = parse_qs(u.query) 
        if "title" in q: 
            return unquote(q["title"][0]) 
        if "/index.php/" in u.path: 
            return unquote(u.path.split("/index.php/", 1)[-1]) 
        if "/wiki/" in u.path: 
            return unquote(u.path.split("/wiki/", 1)[-1]) 
    return unquote(u.path.strip("/")) 

def slug(s: str) -> str: 
    s = s.strip().replace(" ", "_") 
    return re.sub(r"[^\w\-.]+", "_", s)[:150] or "page" 

def scrape_one(url: str) -> str | None: 
    payload = { 
        "url": url, 
        "engine": "playwright", 
        "formats": ["markdown"] 
    } 
    r = requests.post(SCRAPE_URL, headers=HEADERS, json=payload, timeout=60) 

    # Simple: assuming JSON and markdown present 
    try: 
        data = r.json().get("data", {}) 
        return data.get("markdown") 
    except: 
        return None 
    
if __name__ == "__main__": 
    with open("links.json", "r", encoding="utf-8") as f: 
        links = json.load(f) 

    # (Optional): Only for alps right now 
    links = [u for u in links if "alps" in (u.lower() + title_from_url(u).lower())] 

    print(f"Scraping {len(links)} pages to {OUT_DIR}/") 
    for u in links: 
        fn = OUT_DIR / f"{slug(title_from_url(u))}.md" 
        if fn.exists(): 
            continue 
        md = scrape_one(u) 
        if not md: 
            print(f"Skip (no md): {u}") 
            continue 
        fn.write_text(md, encoding="utf-8") 
        time.sleep(0.8) 
    print("Scraping complete!") 
