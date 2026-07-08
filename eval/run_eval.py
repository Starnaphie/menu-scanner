import os
import json
import time
from pathlib import Path

import requests
from rapidfuzz import fuzz


GROUND_TRUTH_DIR = Path("eval/ground_truth")
CACHE_FILE = Path("eval/inference_cache.json")
METRICS_FILE = Path("eval/metrics.json")
API_BASE = "http://localhost:8000"

IMAGE_DIR = Path("eval/ground_truth_src")
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif"]


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with CACHE_FILE.open() as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with CACHE_FILE.open("w") as f:
        json.dump(cache, f, indent=2)


def run_extract(image_path: Path, cache: dict) -> dict:
    filename = image_path.name
    if filename in cache:
        print(f"cache hit: {filename}")
        return cache[filename]

    started = time.perf_counter()
    try:
        with image_path.open("rb") as f:
            response = requests.post(
                f"{API_BASE}/extract",
                files={"file": (filename, f)},
                data={"dietary_restrictions": "[]"},
                timeout=120,
            )
        response.raise_for_status()
    except requests.HTTPError as exc:
        print(f"error extracting {filename}: HTTP {response.status_code}: {response.text}")
        return None
    except Exception as exc:
        print(f"error extracting {filename}: {exc}")
        return None

    wall_latency_ms = (time.perf_counter() - started) * 1000
    result = response.json()
    result["wall_latency_ms"] = wall_latency_ms
    cache[filename] = result
    save_cache(cache)

    item_count = len(result.get("items", []))
    print(f"extracted: {filename} in {wall_latency_ms:.0f}ms, {item_count} items")
    return result


def score_extraction(ground_truth: list[dict], predicted: list[dict]) -> dict:
    matched_pairs = []
    used_predicted_indexes = set()

    for gt_item in ground_truth:
        gt_name = gt_item.get("name", "") or ""
        best_score = -1
        best_index = None

        for index, pred_item in enumerate(predicted):
            if index in used_predicted_indexes:
                continue

            pred_name = pred_item.get("name", "") or ""
            score = fuzz.token_sort_ratio(gt_name, pred_name)
            if score > best_score:
                best_score = score
                best_index = index

        if best_index is not None and best_score >= 80:
            used_predicted_indexes.add(best_index)
            matched_pairs.append((gt_item, predicted[best_index]))

    matched_count = len(matched_pairs)
    gt_count = len(ground_truth)
    pred_count = len(predicted)

    gt_with_description = [
        (gt_item, pred_item)
        for gt_item, pred_item in matched_pairs
        if gt_item.get("description") is not None
    ]
    description_matches = sum(
        1
        for _gt_item, pred_item in gt_with_description
        if pred_item.get("description") is not None
    )

    price_matches = sum(
        1
        for gt_item, pred_item in matched_pairs
        if str(gt_item.get("price", "") or "").strip()
        == str(pred_item.get("price", "") or "").strip()
    )

    return {
        "name_accuracy": matched_count / gt_count if gt_count else 0,
        "description_accuracy": (
            description_matches / len(gt_with_description)
            if gt_with_description
            else 0
        ),
        "price_accuracy": price_matches / matched_count if matched_count else 0,
        "matched_count": matched_count,
        "gt_count": gt_count,
        "pred_count": pred_count,
    }


def score_hallucination(ground_truth: list[dict], predicted: list[dict]) -> dict:
    hallucinated_names = []

    for pred_item in predicted:
        pred_name = pred_item.get("name", "") or ""
        has_match = any(
            fuzz.token_sort_ratio(pred_name, gt_item.get("name", "") or "") >= 80
            for gt_item in ground_truth
        )

        if not has_match:
            hallucinated_names.append(pred_name)

    total_predicted = len(predicted)
    hallucinated_count = len(hallucinated_names)

    return {
        "hallucination_rate": (
            hallucinated_count / total_predicted if total_predicted else 0.0
        ),
        "hallucinated_count": hallucinated_count,
        "total_predicted": total_predicted,
        "hallucinated_names": hallucinated_names,
    }


def score_dietary(ground_truth: list[dict], predicted: list[dict]) -> dict:
    true_positives_total = 0
    false_positives_total = 0
    false_negatives_total = 0
    evaluated_items_count = 0
    used_predicted_indexes = set()

    for gt_item in ground_truth:
        gt_tags = gt_item.get("dietary_tags") or []
        if not gt_tags:
            continue

        gt_name = gt_item.get("name", "") or ""
        best_score = -1
        best_index = None

        for index, pred_item in enumerate(predicted):
            if index in used_predicted_indexes:
                continue

            pred_name = pred_item.get("name", "") or ""
            score = fuzz.token_sort_ratio(gt_name, pred_name)
            if score > best_score:
                best_score = score
                best_index = index

        if best_index is None or best_score < 80:
            continue

        used_predicted_indexes.add(best_index)
        pred_item = predicted[best_index]
        evaluated_items_count += 1

        gt_tag_set = {str(tag).lower() for tag in gt_tags}
        pred_tag_set = {
            str(tag).lower()
            for tag in pred_item.get("user_dietary_flags") or []
        }

        true_positives_total += len(gt_tag_set & pred_tag_set)
        false_positives_total += len(pred_tag_set - gt_tag_set)
        false_negatives_total += len(gt_tag_set - pred_tag_set)

    precision_denominator = true_positives_total + false_positives_total
    recall_denominator = true_positives_total + false_negatives_total

    return {
        "precision": (
            true_positives_total / precision_denominator
            if precision_denominator > 0
            else None
        ),
        "recall": (
            true_positives_total / recall_denominator
            if recall_denominator > 0
            else None
        ),
        "true_positives_total": true_positives_total,
        "false_positives_total": false_positives_total,
        "false_negatives_total": false_negatives_total,
        "evaluated_items_count": evaluated_items_count,
    }


def _find_matching_image(stem: str) -> Path | None:
    for extension in IMAGE_EXTENSIONS:
        image_path = IMAGE_DIR / f"{stem}{extension}"
        if image_path.exists():
            return image_path
    return None


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def _average_optional(values: list[float | None]) -> float | None:
    present_values = [value for value in values if value is not None]
    return _average(present_values) if present_values else None


def _ground_truth_items(ground_truth: list[dict] | dict) -> list[dict]:
    if isinstance(ground_truth, dict):
        return ground_truth.get("items", [])
    return ground_truth


if __name__ == "__main__":
    cache = load_cache()
    pairs = []

    for ground_truth_path in sorted(GROUND_TRUTH_DIR.glob("*.json")):
        image_path = _find_matching_image(ground_truth_path.stem)
        if image_path is None:
            print(f"warning: image not found for {ground_truth_path.name}")
            continue

        with ground_truth_path.open() as f:
            ground_truth = json.load(f)

        prediction = run_extract(image_path, cache)
        if prediction is None:
            continue

        pairs.append((image_path.name, _ground_truth_items(ground_truth), prediction))

    print(f"collected {len(pairs)} ground_truth/prediction pairs")

    per_image = []
    ocr_failures = []

    for filename, ground_truth, prediction in pairs:
        predicted_items = prediction.get("items", [])
        extraction_scores = score_extraction(ground_truth, predicted_items)
        hallucination_scores = score_hallucination(ground_truth, predicted_items)
        dietary_scores = score_dietary(ground_truth, predicted_items)

        ocr_text_length = len(prediction.get("ocr_text", "") or "")
        if len(predicted_items) == 0 or ocr_text_length < 50:
            ocr_failures.append({
                "filename": filename,
                "ocr_text_length": ocr_text_length,
            })

        per_image.append({
            "filename": filename,
            "items_returned": len(predicted_items),
            "wall_latency_ms": prediction.get("wall_latency_ms", 0),
            "cost_usd": prediction.get("cost_usd", 0),
            "extraction": extraction_scores,
            "hallucination": hallucination_scores,
            "dietary": dietary_scores,
        })

    averages = {
        "avg_wall_latency_ms": _average([
            row["wall_latency_ms"] for row in per_image
        ]),
        "avg_cost_usd": _average([
            row["cost_usd"] for row in per_image
        ]),
        "avg_items_returned": _average([
            row["items_returned"] for row in per_image
        ]),
        "name_accuracy": _average([
            row["extraction"]["name_accuracy"] for row in per_image
        ]),
        "description_accuracy": _average([
            row["extraction"]["description_accuracy"] for row in per_image
        ]),
        "price_accuracy": _average([
            row["extraction"]["price_accuracy"] for row in per_image
        ]),
        "hallucination_rate": _average([
            row["hallucination"]["hallucination_rate"] for row in per_image
        ]),
        "dietary_precision": _average_optional([
            row["dietary"]["precision"] for row in per_image
        ]),
        "dietary_recall": _average_optional([
            row["dietary"]["recall"] for row in per_image
        ]),
    }

    print(
        "IMAGE                  | ITEMS | NAME_ACC | DESC_ACC | PRICE_ACC | "
        "HALLUC | LATENCY_MS | COST_USD"
    )
    for row in per_image:
        print(
            f"{row['filename'][:22]:<22} | "
            f"{row['items_returned']:>5} | "
            f"{row['extraction']['name_accuracy']:>8.2f} | "
            f"{row['extraction']['description_accuracy']:>8.2f} | "
            f"{row['extraction']['price_accuracy']:>9.2f} | "
            f"{row['hallucination']['hallucination_rate']:>6.2f} | "
            f"{row['wall_latency_ms']:>10.0f} | "
            f"{row['cost_usd']:>8.6f}"
        )

    print(
        f"{'AVERAGE':<22} | "
        f"{averages['avg_items_returned']:>5.1f} | "
        f"{averages['name_accuracy']:>8.2f} | "
        f"{averages['description_accuracy']:>8.2f} | "
        f"{averages['price_accuracy']:>9.2f} | "
        f"{averages['hallucination_rate']:>6.2f} | "
        f"{averages['avg_wall_latency_ms']:>10.0f} | "
        f"{averages['avg_cost_usd']:>8.6f}"
    )

    metrics = {
        "per_image": per_image,
        "averages": averages,
        "ocr_failures": ocr_failures,
        "eval_set_size": len(per_image),
    }
    with METRICS_FILE.open("w") as f:
        json.dump(metrics, f, indent=2)

    print("Results written to eval/metrics.json")
