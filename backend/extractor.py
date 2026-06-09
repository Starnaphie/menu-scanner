import base64
import json
import os
import re

from openai import OpenAI

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client

_STAGE1_SYSTEM_PROMPT = """
You are a menu transcription tool. Your only job is to read what is visibly printed on the menu image and copy it out faithfully.

Return ONLY a valid JSON array (no markdown, no code fences). Each element must be an object with exactly these keys:

- name (string): the item's name exactly as printed
- raw_description (string | null): the item's description exactly as printed, or null if absent
- raw_flags (array of strings): any dietary or allergen labels explicitly printed on the menu for this item (e.g. "(V)", "GF", "vegan", "contains nuts") — copy them verbatim; use [] if none are printed

Rules:
- Read the menu strictly column by column, left to right. Complete every item in the leftmost column before moving to the next column. Do not mix items across columns.
- Include only lines for food on the menu: dishers, sides, specials, etc. Do not include section headers, prices, modifiers like "choose your protein", drinks, etc.
- Include every non-drink category: starters, dishes, sides, specials, etc.
- Do not invent, infer, or reason about ingredients, allergens, or dietary suitability — only report what is visibly printed on the menu.
- Output only the JSON array, nothing else.
""".strip()

def _stage1_extract(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> tuple[list[dict], dict]:
    """
    Base64-encode *image_bytes*, send to GPT-4o-mini vision, and return a tuple of
    (items, usage) where items is a list of raw menu-item dicts and usage contains
    input_tokens and output_tokens.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _STAGE1_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": "auto"},
                    },
                    {
                        "type": "text",
                        "text": "Extract all menu items from this image and return the JSON array.",
                    },
                ],
            },
        ],
        max_tokens=2048,
        temperature=0,
    )

    raw = response.choices[0].message.content or ""
    raw = raw.strip()

    # Strip accidental markdown code fences (```json … ```)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        items: list[dict] = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        items = []
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
    return items, usage


_STAGE2_SYSTEM_PROMPT = """
You are a culinary analyst. You will receive a raw JSON array of menu items extracted from a menu image. Your job is to refine this list. Follow these rules strictly:

For each remaining item, produce an object with these keys:
- name (string): cleaned item name
- description (string | null): cleaned description, or null if no description is present
- common_ingredients (array of strings): well-known ingredients a typical person would recognise
- obscure_ingredient_notes (array of strings): each obscure term from the description repeated as a standalone string in the format 'term – explanation', for easy display
- user_dietary_flags (array of strings): only populated when the user has dietary restrictions (see below). If no user restrictions are provided, always use [].

Output ONLY a valid JSON array, no markdown, no explanation.
""".strip()


def _stage2_refine(
    raw_items: list[dict],
    restrictions: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """
    Send *raw_items* (Stage 1 output) to GPT-4o-mini as a text-only call and return a
    tuple of (items, usage) where items is the refined list of menu-item dicts.
    """
    system_prompt = _STAGE2_SYSTEM_PROMPT
    if restrictions:
        joined = ", ".join(restrictions)
        system_prompt += (
            f"\n\nThe user has these dietary restrictions: {joined}. "
            "For each restriction, carefully read the item name and description and determine "
            "if the item contains or may contain ingredients relevant to that restriction. "
            "Only add a restriction to user_dietary_flags if the item CONTAINS or MAY CONTAIN "
            "that restricted ingredient — never add restrictions the item is safe from. "
            "Do not add flags for restrictions that have no relevance to this item."
        )

    # 1. STRIP raw_flags before sending to LLM
    items_for_llm = [
        {k: v for k, v in item.items() if k != "raw_flags"}
        for item in raw_items
    ]

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Refine this extracted menu data: {json.dumps(items_for_llm)}",
            },
        ],
        max_tokens=4096,
        temperature=0,
    )

    # 2. PARSE the LLM response
    raw = response.choices[0].message.content or ""
    raw = raw.strip()

    # Strip accidental markdown code fences (```json … ```)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        refined_items: list[dict] = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        refined_items = []

    # 2.5. NORMALIZE refined_items before copying raw_flags
    for item in refined_items:
        # Coerce description to None if not a non-empty string
        if not isinstance(item.get("description"), str) or not item["description"].strip():
            item["description"] = None

        # Coerce list fields to [] if not lists
        for field in ["common_ingredients", "obscure_ingredient_notes", "user_dietary_flags"]:
            if not isinstance(item.get(field), list):
                item[field] = []

    # 3. COPY raw_flags after parsing
    for raw_item, refined_item in zip(raw_items, refined_items):
        refined_item["visible_dietary_flags"] = raw_item.get("raw_flags", [])

    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
    return refined_items, usage


_STAGE3_SYSTEM_PROMPT = """
You are a dietary restriction analyst. You will receive a single menu item (name and description) and a list of the user's dietary restrictions.

Each restriction is something the user CANNOT eat or AVOIDS. "beef" means no beef, "dairy" means no dairy, "gluten" means no gluten, and so on — treat every restriction as a prohibition, not a preference.

For each of the user's restrictions, read the item name and description and determine whether the item is likely to contain, may contain, or is safe from that restricted ingredient or category. Return a JSON array where each element has:
- restriction (string): the user's restriction being evaluated
- verdict (string): one of "contains", "may contain", or "safe" — "contains" if the item clearly has it, "may contain" if it is uncertain or a common hidden ingredient, "safe" if the item clearly does not have it
- explanation (string): a concise 1-2 sentence explanation based only on the item name and description

Include every one of the user's restrictions in the output, even if safe. Do not reference visible_dietary_flags. Do not invent ingredients not implied by the name or description.
Output ONLY a valid JSON array, no markdown, no explanation.
""".strip()


def _stage3_explain_flags(
    item: dict,
    restrictions: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """
    For a single refined menu item, return confidence and explanation for each
    dietary flag relevant to the user's restrictions.
    """
    restriction_note = ""
    if restrictions:
        joined = ", ".join(restrictions)
        restriction_note = f"\n\nThe user's dietary restrictions are: {joined}."

    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _STAGE3_SYSTEM_PROMPT + restriction_note},
            {
                "role": "user",
                "content": f"Evaluate this menu item against the user's restrictions: {json.dumps(item)}",
            },
        ],
        max_tokens=1024,
        temperature=0,
    )

    raw = response.choices[0].message.content or ""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        explanations: list[dict] = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        explanations = []
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
    return explanations, usage


def extract_menu(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    restrictions: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """
    Orchestrate Stage 1 (faithful extraction) and Stage 2 (culinary refinement),
    returning (refined_items, combined_usage).
    """
    raw_items, usage1 = _stage1_extract(image_bytes, mime_type)
    print(raw_items)
    refined_items, usage2 = _stage2_refine(raw_items, restrictions)
    print(refined_items)
    combined_usage = {
        "input_tokens": usage1["input_tokens"] + usage2["input_tokens"],
        "output_tokens": usage1["output_tokens"] + usage2["output_tokens"],
    }
    return refined_items, combined_usage
