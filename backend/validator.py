import re


PRICE_PATTERN = re.compile(r"^\$?\d+(?:\.\d{2})?$")


def validate_items(items: list[dict]) -> list[dict]:
    for item in items:
        warnings = []

        if not isinstance(item.get("name"), str) or not item["name"].strip():
            warnings.append("missing_name")

        if not isinstance(item.get("category"), str) or not item["category"].strip():
            warnings.append("missing_category")

        price = item.get("price")
        if price is not None and (
            not isinstance(price, str) or not PRICE_PATTERN.match(price.strip())
        ):
            warnings.append("invalid_price_format")

        item["validation_warnings"] = warnings

    return items
