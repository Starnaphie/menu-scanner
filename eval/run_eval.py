import json
import sys

# STEP 1 — load both files
scored = json.load(open("eval/scored_cases.json"))["cases"]
metrics = json.load(open("eval/metrics.json"))

# STEP 2 — print per-image results table
print(f"{'IMAGE':<35} {'OUTCOME':<8} {'FIRST_ITEM_MATCH':<17} {'NOTES'}")
print("-" * 75)
for c in scored:
    match_str = "✓" if c["first_item_match"] else ("—" if not c["scoreable"] else "✗")
    print(f"{c['image']:<35} {c['outcome']:<8} {match_str:<17} {c['notes']}")

# STEP 3 — print confusion matrix
cm = metrics["confusion_matrix"]
print("\nCONFUSION MATRIX")
print(f"{'':20} {'Predicted YES':>14} {'Predicted NO':>13}")
print(f"{'Actual YES (menu)':20} {'TP='+str(cm['TP']):>14} {'FN='+str(cm['FN']):>13}")
print(f"{'Actual NO (not menu)':20} {'FP='+str(cm['FP']):>14} {'TN='+str(cm['TN']):>13}")

# STEP 4 — print classification metrics
print("\nMETRICS")
print(f"  Accuracy:            {metrics['accuracy']}")
print(f"  Precision:           {metrics['precision']}")
print(f"  Recall:              {metrics['recall']}")
print(f"  F1 Score:            {metrics['f1']}")
print(f"  First Item Accuracy: {metrics['first_item_accuracy']} "
      f"({metrics['first_item_correct']}/{metrics['first_item_total']})")

# STEP 5 — print cost summary
print("\nCOST")
print(f"  Total input tokens:  {metrics['total_input_tokens']}")
print(f"  Total output tokens: {metrics['total_output_tokens']}")
print(f"  Estimated cost:      ${metrics['estimated_cost_usd']:.6f}")

# STEP 6 — exit with code 1 if f1 < 0.8
sys.exit(0 if metrics["f1"] >= 0.8 else 1)
