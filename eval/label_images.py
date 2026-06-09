#!/usr/bin/env python3
"""Interactive labeling tool for eval/images/ — builds eval/expected.json."""

import json
import platform
import subprocess
import sys
from pathlib import Path

IMAGES_DIR = Path(__file__).parent / "images"
OUTPUT_FILE = Path(__file__).parent / "expected.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def open_image(path: Path) -> None:
    if platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def load_existing() -> dict[str, dict]:
    """Return a dict keyed by 'images/<filename>' for fast lookup."""
    if not OUTPUT_FILE.exists():
        return {}
    with open(OUTPUT_FILE) as f:
        data = json.load(f)
    return {case["image"]: case for case in data.get("cases", [])}


def write_cases(cases: list[dict]) -> None:
    with open(OUTPUT_FILE, "w") as f:
        json.dump({"cases": cases}, f, indent=2)


def prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nInterrupted — progress saved.")
        sys.exit(0)


def main() -> None:
    images = sorted(
        p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        print(f"No images found in {IMAGES_DIR}")
        sys.exit(0)

    existing = load_existing()
    # Preserve existing order; append new entries at the end
    cases_by_key: dict[str, dict] = dict(existing)

    total = len(images)
    skipped = 0

    for i, img_path in enumerate(images, start=1):
        key = f"images/{img_path.name}"
        print(f"\nImage {i}/{total}: {img_path.name}")

        if key in cases_by_key:
            print("  Already labeled — skipping.")
            skipped += 1
            continue

        open_image(img_path)

        is_menu_raw = prompt("  Is this a menu? (y/n): ").lower()
        while is_menu_raw not in ("y", "n"):
            is_menu_raw = prompt("  Please enter y or n: ").lower()

        is_menu = is_menu_raw == "y"
        first_item: str | None = None

        if is_menu:
            first_item = prompt("  What is the first item on the menu? (type it exactly): ")

        cases_by_key[key] = {
            "image": key,
            "is_menu": is_menu,
            "first_item": first_item,
        }

        # Maintain insertion order when writing
        write_cases(list(cases_by_key.values()))

    # Summary
    all_cases = list(cases_by_key.values())
    menu_count = sum(1 for c in all_cases if c.get("is_menu"))
    not_menu_count = len(all_cases) - menu_count

    print(f"\n--- Summary ---")
    print(f"Total images : {total}")
    print(f"Menus        : {menu_count}")
    print(f"Not menus    : {not_menu_count}")
    if skipped:
        print(f"Skipped (already labeled): {skipped}")
    print(f"Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
