# scripts/normalize_anycrawl.py
import re, os, json, glob, pathlib
from urllib.parse import urlparse, parse_qs, unquote

IN_DIR  = "data"
OUT_DIR = "out"
os.makedirs(OUT_DIR, exist_ok=True)

# ---------- regexes ----------
H_SECTION = re.compile(r'^(#{2,3})\s*(.+?)\s*$', re.M)         # ##, ### headings
MD_LINK   = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')             # [text](url)
FOOTNOTE  = re.compile(r'\[\d+\]')                             # [1], [2], ...
HTML_TAGS = re.compile(r'<[^>]+>')                             # strip leftover html
# Heading "References" block to end
REF_BLOCK = re.compile(r'(?im)^references\s*[-\s]*\n.*$', re.S)

NAV_PATTERNS = [
    r'(?i)jump to navigation', r'(?i)jump to search',
    r'(?i)^navigation menu.*$', r'(?i)^page actions.*$', r'(?i)^personal tools.*$',
    r'(?i)^retrieved from.*$', r'(?i)^\[categories\].*$', r'(?i)^categories\s*:.*$'
]
NAV_RE = re.compile("|".join(NAV_PATTERNS), re.M)

# Helpers
def title_from_url(url: str) -> str:
    u = urlparse(url)
    if u.path.startswith("/index.php"):
        q = parse_qs(u.query)
        if "title" in q: return unquote(q["title"][0])
        if "/index.php/" in u.path: return unquote(u.path.split("/index.php/",1)[-1])
    if "/wiki/" in u.path:
        return unquote(u.path.split("/wiki/",1)[-1])
    return unquote(u.path.strip("/"))

def infer_doc_type(title, infobox):
    t = (title or "").lower()
    if t.startswith("category:"): return "category"
    if any(k in infobox for k in ("Manufacturer","FCC ID","Layouts","Interface")): return "keyboard_model"
    if re.search(r'\b(skcl|skcm|mx|alps|topre|buckling spring)\b', t): return "switch"
    if re.search(r'\b(series|mount|contact|stabilizer|doubleshot)\b', t): return "tech_concept"
    return "unknown"

def dedupe_list(lst, key):
    seen, out = set(), []
    for x in lst:
        k = x.get(key)
        if not k or k in seen: continue
        seen.add(k); out.append(x)
    return out

def serialize_infobox(md):
    """
    The AnyCrawl markdown for MediaWiki infobox often appears as stacked key/value pairs
    before 'Contents'. This naive pass works surprisingly well.
    """
    lines = md.splitlines()
    out = {}
    for i in range(min(len(lines), 150)):
        ln = lines[i].strip()
        if re.match(r'(?i)^contents\s*$', ln): break
        # Treat a line followed by a non-empty line as key/value
        if ln and i+1 < len(lines):
            nxt = lines[i+1].strip()
            if nxt and not nxt.startswith('#') and len(ln) <= 40 and re.match(r'^[A-Za-z][\w /()-]*$', ln):
                # Keep the first value; if multiple, last one wins
                out[ln] = nxt
    # Post processing values to remove markdown links
    for k,v in list(out.items()):
        out[k] = MD_LINK.sub(lambda m: m.group(1), v)
    return out

def extract_citations(md):
    cites = []
    refs = re.findall(r'<ref[^>]*>(.*?)</ref>', md, flags=re.I|re.S)
    for html in refs:
        m = re.search(MD_LINK, html)
        if m:
            cites.append({"label": m.group(1), "url": m.group(2)})
        else:
            for u in re.findall(r'https?://\S+', html):
                cites.append({"label": re.sub(r'https?://', '', u)[:80], "url": u})
    return dedupe_list(cites, key='url')

def clean_markdown(md):
    kept = []
    for ln in md.splitlines():
        if NAV_RE.search(ln): continue
        # "* Read", "* Edit"
        if ln.strip().startswith("* ") and re.search(r'\b(Read|Edit|Edit source|History|Tools|Discussion)\b', ln):
            continue
        kept.append(ln)
    body = "\n".join(kept)
    # Remove References block from body; we keep citations separately
    body = REF_BLOCK.sub('', body)
    # Strip footnote markers and html tags leftovers
    body = FOOTNOTE.sub('', body)
    body = HTML_TAGS.sub('', body)
    # Collapse excessive blank lines
    body = re.sub(r'\n{3,}', '\n\n', body).strip()
    return body

def split_sections(body):
    """Return list of {"section","text"} with 'Lead' for preface."""
    sections = []
    matches = list(H_SECTION.finditer(body))
    if not matches:
        if body.strip():
            sections.append({"section":"Lead","text":body.strip()})
        return sections

    lead = body[:matches[0].start()].strip()
    if lead:
        sections.append({"section":"Lead","text":lead})
    # H2/H3 block
    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(body)
        text = body[start:end].strip()
        if text:
            sections.append({"section":title, "text":text})
    return sections

def strip_urls_keep_anchors(text, links_out, via_section):
    def _repl(m):
        anchor, url = m.group(1), m.group(2)
        links_out.append({"text": anchor, "url": url, "via_section": via_section})
        return anchor
    return MD_LINK.sub(_repl, text)

def quality_score(text, infobox, sections_count):
    score = 0
    if infobox: score += 2
    score += min(sections_count, 5)
    wc = len(re.findall(r'\w+', text))
    if wc < 150 and sections_count <= 1: score -= 2
    return score

REDIRECT_HEADER = re.compile(r'\(Redirected from \[([^\]]+)\]\(([^)]+)\)\)', re.I)

def detect_redirect(md):
    m = REDIRECT_HEADER.search(md)
    if not m:
        return None
    return {"from_title": m.group(1).strip(), "from_url": m.group(2).strip()}

def normalize_file(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    data = raw.get("data", {})
    url  = data.get("url")
    title_full = data.get("title","")
    title = title_full.replace(" - Keyboard Wiki","").strip()
    md   = data.get("markdown","") or ""
    if not url or not md:
        return []

    # NEW: redirect detection
    redirect = detect_redirect(md)
    if redirect:
        alias_doc = {
            "url": url,
            "canonical_url": url,
            "title": title,                 # canonical title e.g., "Alps SKCL Lock"
            "doc_type": "alias",
            "is_redirect": True,
            "redirect_from": [{
                "title": redirect["from_title"],
                "url": redirect["from_url"]
            }],
        }
        return [alias_doc]

    citations = extract_citations(md)
    body = clean_markdown(md)
    sections = split_sections(body)
    infobox_all = serialize_infobox(body)

    doc_type = infer_doc_type(title, infobox_all)

    docs = []
    for sec in sections:
        links_out = []
        sec_text  = strip_urls_keep_anchors(sec["text"], links_out, sec["section"]).strip()
        sec_text  = re.sub(r'\s+\n', '\n', sec_text)

        q = quality_score(sec_text, infobox_all if sec["section"]=="Lead" else {}, len(sections))
        doc = {
            "url": url,
            "canonical_url": url,
            "title": title,
            "doc_type": doc_type,
            "hierarchy": [("Switch" if doc_type=="switch" else "Page"), title, sec["section"]],
            "section": sec["section"],
            "text": sec_text,
            "infobox": infobox_all if sec["section"]=="Lead" else {},
            "links_out": dedupe_list(links_out, key='url'),
            "citations": citations if sec["section"]=="Lead" else [],
            "images": [],     # Optional for now: fill this if you parse captions/files
            "is_stub": (q < 0),
            "quality_score": q
        }
        if doc["text"]:
            docs.append(doc)
    return docs

if __name__ == "__main__":
    out_path = pathlib.Path(OUT_DIR) / "clean.jsonl"
    count = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for fp in glob.glob(os.path.join(IN_DIR, "*.json")):
            docs = normalize_file(pathlib.Path(fp))
            for d in docs:
                out.write(json.dumps(d, ensure_ascii=False) + "\n")
                count += 1
    print(f"✅ Wrote {count} chunks to {out_path}")
