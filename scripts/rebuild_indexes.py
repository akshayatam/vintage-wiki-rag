#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict

import yaml

VAULT_DIR = Path("themk_final_vault")
INDEX_DIR = VAULT_DIR / "_indexes"

INVALID_FILENAME_CHARS = re.compile(r'[\\/*?:"<>|]')


def clean_filename(name: str) -> str:
    name = name.strip().replace("/", "_").replace("\\", "_")
    return INVALID_FILENAME_CHARS.sub("_", name)


def display_title(title: str) -> str:
    return title.replace("_", " ")


def extract_frontmatter(md_text: str):
    if not md_text.startswith("---\n"):
        return None
    parts = md_text.split("---\n", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def normalize_tags(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def main() -> None:
    INDEX_DIR.mkdir(exist_ok=True)

    tag_to_pages: dict[str, list[str]] = defaultdict(list)

    for md_file in sorted(VAULT_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        frontmatter = extract_frontmatter(text)
        if not frontmatter:
            continue

        try:
            meta = yaml.safe_load(frontmatter) or {}
        except Exception as e:
            print(f"Skipping {md_file.name}: invalid YAML ({e})")
            continue

        tags = normalize_tags(meta.get("tags"))
        page_title = md_file.stem

        for tag in tags:
            tag_to_pages[tag].append(page_title)

    # rebuild indexes from scratch
    for old_index in INDEX_DIR.glob("*.md"):
        old_index.unlink()

    for tag, pages in sorted(tag_to_pages.items()):
        safe_tag = clean_filename(f"_{tag}") + ".md"
        out_file = INDEX_DIR / safe_tag

        display_tag = display_title(tag)
        unique_pages = sorted(set(pages), key=str.lower)

        yaml_header = {
            "title": f"Index: {display_tag}",
            "tags": [tag],
        }

        lines = [
            "---",
            yaml.safe_dump(yaml_header, sort_keys=False).strip(),
            "---",
            "",
            f"# {display_tag.title()} Index",
        ]

        for page in unique_pages:
            lines.append(f"- [[{page}]]")

        out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Built index: {out_file.name}")

    print(f"\nDone. Rebuilt indexes in: {INDEX_DIR}")


if __name__ == "__main__":
    main()