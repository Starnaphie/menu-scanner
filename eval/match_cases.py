import json

# STEP 1 — load expected.json
with open("eval/expected.json") as f:
    expected = json.load(f)
expected_cases = expected["cases"]

# STEP 2 — load inference_cache.json
with open("eval/inference_cache.json") as f:
    cache = json.load(f)
cache_lookup = {c["image"]: c for c in cache["cases"]}

# STEP 3 — join on "image" field
matched = []
for case in expected_cases:
    key = case["image"]
    if key not in cache_lookup:
        print(f"WARNING: no cache entry for {key}, skipping")
        continue
    matched.append({
        "expected": case,
        "predicted": cache_lookup[key]
    })

# STEP 4 — write eval/matched_cases.json
with open("eval/matched_cases.json", "w") as f:
    json.dump({"cases": matched}, f, indent=2)
print(f"Matched {len(matched)} cases. Written to eval/matched_cases.json")
