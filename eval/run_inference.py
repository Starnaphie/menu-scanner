import json
import os
import sys

# Load .env file if OPENAI_API_KEY is not already set
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.extractor import extract_menu

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
EXPECTED_PATH = os.path.join(EVAL_DIR, "expected.json")
CACHE_PATH = os.path.join(EVAL_DIR, "inference_cache.json")

# Load expected cases
with open(EXPECTED_PATH) as f:
    expected = json.load(f)

# Load or init cache
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH) as f:
        cache = json.load(f)
else:
    cache = {"cases": []}

cached_images = {c["image"] for c in cache["cases"]}

# Filter to only uncached cases
to_run = [c for c in expected["cases"] if c["image"] not in cached_images]
total = len(expected["cases"])
skipped = total - len(to_run)

for i, case in enumerate(to_run, start=1):
    image_rel = case["image"]
    path = os.path.join(EVAL_DIR, image_rel)
    filename = os.path.basename(image_rel)
    print(f"Running {i}/{len(to_run)}: {filename}")

    with open(path, "rb") as f:
        image_bytes = f.read()

    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")

    items, usage, _cost_usd = extract_menu(image_bytes, mime)

    cache["cases"].append({
        "image": image_rel,
        "items": items,
        "usage": usage,
    })

    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

print(f"Done. {len(to_run)} images processed, {skipped} skipped (cached).")
