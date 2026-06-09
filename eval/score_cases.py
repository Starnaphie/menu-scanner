import json

# STEP 1 — load
with open("eval/matched_cases.json") as f:
    data = json.load(f)

results = []

for case in data["cases"]:
    # STEP 2 — extract values
    image = case["expected"]["image"]
    is_menu = case["expected"]["is_menu"]
    first_item = case["expected"]["first_item"]
    items = case["predicted"]["items"]
    usage = case["predicted"]["usage"]
    predicted_menu = len(items) > 0

    # STEP 3 — determine outcome
    if is_menu == True and first_item:
        outcome = "TP" if predicted_menu else "FN"
        notes = ""
    elif is_menu == False:
        outcome = "TN" if not predicted_menu else "FP"
        notes = ""
    elif is_menu == True and not first_item:
        outcome = "TP" if len(items) <= 2 else "FP"
        notes = "illegible"

    # STEP 4 — score first item
    scoreable = is_menu == True and bool(first_item)
    if scoreable and len(items) > 0:
        first_item_match = first_item.lower() in items[0]["name"].lower()
    else:
        first_item_match = False

    # STEP 5 — build output dict
    result = {
        "image": image,
        "expected_is_menu": is_menu,
        "expected_first_item": first_item,
        "predicted_is_menu": predicted_menu,
        "predicted_first_name": items[0]["name"] if items else "",
        "outcome": outcome,
        "scoreable": scoreable,
        "first_item_match": first_item_match,
        "notes": notes,
        "usage": usage,
    }
    results.append(result)

    match_str = "✓" if first_item_match else "✗"
    print(f"{image} → {outcome} | first_item: {match_str} | notes: {notes}")

# STEP 6 — write eval/scored_cases.json
with open("eval/scored_cases.json", "w") as f:
    json.dump({"cases": results}, f, indent=2)

print(f"\nScored {len(results)} cases. Written to eval/scored_cases.json")
