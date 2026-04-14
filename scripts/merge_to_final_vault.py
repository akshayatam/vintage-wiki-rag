#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

BATCH_ROOT = Path("vault_batches")
FINAL_VAULT = Path("themk_final_vault")
FINAL_IMAGES = FINAL_VAULT / "images"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_article(src: Path, dest_dir: Path) -> None:
    """
    Copy a markdown article into the final vault without overwriting.
    If same filename + same content already exists, skip.
    If same filename + different content exists, append _1, _2, etc.
    """
    dest = dest_dir / src.name

    if not dest.exists():
        shutil.copy2(src, dest)
        print(f"Copied article: {src.name}")
        return

    # Same filename exists: compare content
    if sha256(src) == sha256(dest):
        print(f"Skipped identical article: {src.name}")
        return

    stem = src.stem
    suffix = src.suffix
    counter = 1

    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            shutil.copy2(src, candidate)
            print(f"Copied article with rename: {src.name} -> {candidate.name}")
            return
        if sha256(src) == sha256(candidate):
            print(f"Skipped identical article (duplicate renamed version): {src.name}")
            return
        counter += 1


def copy_image(src: Path, dest_dir: Path) -> None:
    """
    Copy an image into final images folder without overwriting.
    If same filename + same content already exists, skip.
    If same filename + different content exists, append _1, _2, etc.
    """
    dest = dest_dir / src.name

    if not dest.exists():
        shutil.copy2(src, dest)
        print(f"Copied image: {src.name}")
        return

    if sha256(src) == sha256(dest):
        print(f"Skipped identical image: {src.name}")
        return

    stem = src.stem
    suffix = src.suffix
    counter = 1

    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            shutil.copy2(src, candidate)
            print(f"Copied image with rename: {src.name} -> {candidate.name}")
            return
        if sha256(src) == sha256(candidate):
            print(f"Skipped identical image (duplicate renamed version): {src.name}")
            return
        counter += 1


def main() -> None:
    FINAL_VAULT.mkdir(exist_ok=True)
    FINAL_IMAGES.mkdir(exist_ok=True)

    batch_dirs = sorted(p for p in BATCH_ROOT.glob("themk_batch_*") if p.is_dir())

    if not batch_dirs:
        print("No batch vaults found.")
        return

    for batch_dir in batch_dirs:
        print(f"\nMerging from {batch_dir}")

        # Top-level markdown files only, excluding _indexes folder
        for md_file in sorted(batch_dir.glob("*.md")):
            copy_article(md_file, FINAL_VAULT)

        # Merge images
        image_dir = batch_dir / "images"
        if image_dir.exists():
            for img_file in sorted(image_dir.rglob("*")):
                if img_file.is_file():
                    copy_image(img_file, FINAL_IMAGES)

    print(f"\nDone. Final merged vault is at: {FINAL_VAULT}")


if __name__ == "__main__":
    main()