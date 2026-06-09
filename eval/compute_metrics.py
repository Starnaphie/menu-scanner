import json

# STEP 1 — load
with open("eval/scored_cases.json") as f:
    data = json.load(f)
cases = data["cases"]

# STEP 2 — count confusion matrix values
TP = sum(1 for c in cases if c["outcome"] == "TP")
FP = sum(1 for c in cases if c["outcome"] == "FP")
TN = sum(1 for c in cases if c["outcome"] == "TN")
FN = sum(1 for c in cases if c["outcome"] == "FN")

# STEP 3 — compute classification metrics
accuracy = (TP + TN) / (TP + FP + TN + FN) if (TP + FP + TN + FN) > 0 else 0.0
precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

# STEP 4 — compute first item accuracy
scoreable_cases = [c for c in cases if c["scoreable"]]
first_item_correct = sum(1 for c in scoreable_cases if c["first_item_match"])
first_item_accuracy = first_item_correct / len(scoreable_cases) if scoreable_cases else 0.0

# STEP 5 — compute cost
INPUT_COST_PER_1K = 0.000150
OUTPUT_COST_PER_1K = 0.000600
total_input = sum(c["usage"]["input_tokens"] for c in cases)
total_output = sum(c["usage"]["output_tokens"] for c in cases)
cost = (total_input / 1000 * INPUT_COST_PER_1K) + (total_output / 1000 * OUTPUT_COST_PER_1K)

# STEP 6 — write eval/metrics.json
metrics = {
    "confusion_matrix": {"TP": TP, "FP": FP, "TN": TN, "FN": FN},
    "accuracy": round(accuracy, 4),
    "precision": round(precision, 4),
    "recall": round(recall, 4),
    "f1": round(f1, 4),
    "first_item_accuracy": round(first_item_accuracy, 4),
    "first_item_correct": first_item_correct,
    "first_item_total": len(scoreable_cases),
    "total_input_tokens": total_input,
    "total_output_tokens": total_output,
    "estimated_cost_usd": round(cost, 6),
}

with open("eval/metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)

print("Metrics written to eval/metrics.json")
