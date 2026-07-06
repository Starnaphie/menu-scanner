Document Scanner

## Demo Link
https://youtu.be/ta6yl-J72ww

---

## Overview

Menu Scanner is a single-page web application that extracts structured information from a photograph of a restaurant menu. Upload an image; the backend sends it to the OpenAI vision API and returns a list of menu items annotated with ingredients, allergen warnings, and dietary flags.

```
.
├── backend/
│   ├── main.py          # FastAPI app — POST /scan endpoint
│   └── extractor.py     # extract_menu() — pure extraction logic, no web framework
├── eval/
│   ├── expected.json    # Evaluation dataset (cases + expected assertions)
│   ├── images/          # Place test images here (see Evaluation section)
│   └── run_eval.py      # CLI eval harness
├── frontend/
│   └── index.html       # Single-page app (vanilla JS + fetch)
├── requirements.txt
└── run.sh               # Start the dev server
```

---

## Requirements

- Python 3.11+
- An OpenAI API key with access to `gpt-4o-mini`

---

## Setup

```bash
# 1. Create and activate the virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your OpenAI API key
export OPENAI_API_KEY=sk-...
```

---

## Running the server

```bash
./run.sh
```

This activates the venv, checks that `OPENAI_API_KEY` is set, and starts uvicorn at `http://localhost:8000` with `--reload` enabled for development.

Then open `frontend/index.html` directly in your browser (no separate static server needed).

---

## Environment variable

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Passed to the OpenAI client. The server will refuse to start if this is unset. |

The key is read at request time (lazy initialisation in `extractor.py`), so you can set it in your shell before running `./run.sh` or export it in a `.env` file that you source manually. No `.env` auto-loading is built in — keep secrets out of the repository.

---

## No-persistence guarantee

**Images are never written to disk.** The upload flow is:

1. The browser sends a `multipart/form-data` POST to `/scan`.
2. FastAPI reads the file bytes into memory with `await file.read()`.
3. The bytes are base64-encoded and embedded in the OpenAI API request payload.
4. The API response is parsed and returned as JSON.
5. The in-memory bytes are garbage-collected when the request ends.

There is no file system write, no temporary file, no object storage, and no database. Nothing about the uploaded image persists beyond the lifetime of the HTTP request.

---

## API

### `POST /scan`

Accepts a `multipart/form-data` body with a single `file` field containing an image.

**Accepted MIME types:** `image/jpeg`, `image/png`, `image/webp`, `image/gif`

**Success response `200`:**

```json
{
  "items": [
    {
      "name": "Nduja Crostini",
      "description": "Toasted sourdough with whipped ricotta and nduja",
      "common_ingredients": ["bread", "ricotta", "pork"],
      "obscure_ingredient_notes": [
        "nduja – a spreadable, spicy Calabrian pork salume"
      ],
      "allergy_warnings": ["gluten", "dairy"],
      "dietary_flags": ["spicy"]
    }
  ]
}
```

**Error responses:**

| Status | Meaning |
|---|---|
| `415` | Unsupported file type |
| `502` | OpenAI API error or the model returned malformed JSON |
| `500` | Unexpected server error |

### `GET /health`

Returns `{"status": "ok"}`. Useful for confirming the server is up before running evals.

---

## Evaluation

The eval harness (`eval/run_eval.py`) calls `extract_menu()` directly — **the FastAPI server does not need to be running**.

### Adding test images

Place images under `eval/images/` with the filenames referenced in `eval/expected.json`:

```
eval/images/
├── standard_cafe_menu.jpg
├── obscure_ingredients_menu.jpg
├── allergen_heavy_menu.jpg
├── street_scene.jpg
└── blurry_menu.jpg
```

Any case whose image file is missing is shown as `SKIP` and does not affect the exit code.

### Running evaluations

**Run the full dataset:**

```bash
python eval/run_eval.py --all
```

**Filter by case type:**

```bash
python eval/run_eval.py --type positive
python eval/run_eval.py --type negative
```

**Run a single case by ID** (1-based, matching order in `expected.json`):

```bash
python eval/run_eval.py --id 1   # standard café menu
python eval/run_eval.py --id 3   # allergen-heavy menu
python eval/run_eval.py --id 4   # street scene (negative)
```

**Run extract_menu on an arbitrary image** (no assertions, prints raw JSON):

```bash
python eval/run_eval.py --image path/to/any_menu.jpg
```

This is useful for inspecting raw model output during prompt development.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All non-skipped cases passed |
| `1` | One or more cases failed |

### Assertion fields

Each case in `expected.json` has an `expected` object. The harness checks:

| Field | Type | What is asserted |
|---|---|---|
| `must_contain_items` | `string[]` | Each name must appear as a case-insensitive substring in at least one returned item's `name` field |
| `must_flag_allergens` | `string[]` | Each allergen must appear as a case-insensitive substring in at least one item's `allergy_warnings` array |
| `dietary_flags_present` | `string[]` | Each flag must appear in at least one item's `dietary_flags` array |
| `must_not_hallucinate` | `bool` | When `true`, asserts no returned item has a blank or null `name` — catches obvious fabrication |
| `max_items` | `int\|null` | When set, asserts `len(items) <= max_items`; used on negative cases to verify the model doesn't invent content |

---

## Eval dataset design

### Why these cases?

The five cases in `eval/expected.json` were chosen to stress-test the three most important properties of `extract_menu()` independently, before combining them.

#### Positive case 1 — Standard café menu

**Purpose:** Baseline accuracy. A clearly printed, everyday menu with familiar items and standard formatting. This case answers the most basic question: can the model identify items, map them to the correct fields, and avoid inventing things that aren't there? If this fails, nothing else is worth testing.

**Key assertion:** `must_not_hallucinate` — every returned name must be traceable to the image. A model that hallucinates on a clean, readable menu cannot be trusted on harder inputs.

#### Positive case 2 — Obscure / regional ingredients

**Purpose:** Tests `obscure_ingredient_notes` specifically. Fine-dining and ethnic menus routinely use terms most users won't recognise — nduja, bottarga, koji, gochujang, guanciale. The notes field exists precisely to serve those users. A result that leaves it empty is a silent failure: technically valid JSON, but unhelpful.

**Key assertion:** `must_flag_allergens` includes `fish` (bottarga) and `gluten` — allergens that are only detectable if the model recognises the obscure ingredient, not just the obvious ones.

#### Positive case 3 — Allergen-dense menu

**Purpose:** Tests `allergy_warnings` completeness, which is the highest-stakes output field. This case front-loads items that touch all five major allergen groups (shellfish, nuts, gluten, dairy, eggs). Missing an allergen warning is a potentially harmful failure, so it warrants its own dedicated case rather than relying on incidental coverage from the other positives.

**Key assertion:** All five allergen groups must be detected across the result set.

#### Negative case 1 — Non-menu photograph

**Purpose:** Tests that the model does not hallucinate menu items when the input contains no menu. A street scene, portrait, or product photo should produce an empty list. Without this check, a model that always returns *something* would pass all positive cases while being fundamentally unreliable.

**Key assertion:** `max_items: 0` — no items should be returned.

#### Negative case 2 — Blurry / unreadable menu

**Purpose:** Tests graceful degradation on low-quality input. This case is distinct from the non-menu negative: the image *is* a menu, but the text is unreadable. The correct behaviour is to return little or nothing rather than guessing at plausible-sounding items. `max_items: 2` permits one or two genuinely visible words without failing, while still catching a model that fabricates an entire menu from blur.

**Key assertion:** `max_items: 2` combined with `must_not_hallucinate` — the model must not invent items it cannot actually read.

### What this coverage does not test

- **Multi-page menus** (the model receives a single image)
- **Handwritten menus** (a potential future positive case)
- **Non-English menus** (worth adding if the system will be used internationally)
- **Price extraction accuracy** (not currently a tracked output field)
- **Latency and cost** (the harness is correctness-only)
