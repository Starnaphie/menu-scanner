# Menu Scanner

An AI-powered web app that analyzes restaurant menu photos and returns structured item data with ingredients, allergen notes, dietary restriction flags, and semantic search.

**Live:** [menu-scanner-o1ab.onrender.com](https://menu-scanner-o1ab.onrender.com)

---

## Architecture

```mermaid
flowchart TD
    A[Menu Image] --> B[Google Vision API\ndocument_text_detection]
    B --> C[Raw OCR Text]
    C --> D[GPT-4o\nStructured JSON Parsing\n+ Dietary Flag Injection]
    D --> E[Schema Validator\nfield checks + warnings]
    E --> F[/extract response\nitems + scan_id + cost + latency]
    F --> G[OpenAI Embeddings\ntext-embedding-3-small]
    G --> H[FAISS IndexFlatL2\nper-scan in-memory index]
    H --> I[/search response\nranked items + L2 scores]
```

**Pipeline stages:**

Stage 1 — `_stage1_ocr`: Google Vision API `document_text_detection` extracts raw text from the menu image. Returns a plain text string.

Stage 2 — `_stage2_refine`: GPT-4o parses OCR text into structured JSON. Each item gets `name`, `description`, `category`, `price`, `common_ingredients`, `obscure_ingredient_notes`, and `user_dietary_flags`. Dietary restriction logic distinguishes animal-derived ingredients from plant-based alternatives. Processes in batches of 10 to stay within token limits.

Validation — `validate_items`: Checks each item for missing name, missing category, and malformed price. Appends a `validation_warnings` list to each item.

Embeddings — `build_index`: Embeds each item's `name + description` using `text-embedding-3-small` and stores in a per-scan FAISS `IndexFlatL2` index held in memory.

Search — `search_index`: Embeds a query string and returns the top-k nearest items by L2 distance.

---

## Eval Results

Evaluated on 9 hand-labeled restaurant menus across cuisines and formats (Italian, Japanese, American brunch, Mediterranean). Ground truth labeled for: item name, description, price, and dietary tags. Category excluded from metrics due to menu-specific terminology variance — menus use arbitrary section names (e.g. "First Dish", "Small Plates") that don't map cleanly to canonical categories.

| Image | Items | Name Acc | Desc Acc | Price Acc | Halluc Rate | Latency (ms) | Cost (USD) |
|---|---|---|---|---|---|---|---|
| A Taste of Italia | 9 | 1.00 | 1.00 | 1.00 | 0.00 | 16,089 | $0.000594 |
| Benihana | 28 | 0.69 | 0.92 | 0.75 | 0.14 | 25,011 | $0.001472 |
| Brunch at Boujie | 26 | 1.00 | 0.96 | 1.00 | 0.00 | 29,546 | $0.001880 |
| Cesarina | 14 | 1.00 | 1.00 | 1.00 | 0.00 | 26,323 | $0.001336 |
| Italy in Town | 26 | 0.96 | 1.00 | 1.00 | 0.00 | 26,922 | $0.001692 |
| Juniper & Ivy | 34 | 0.92 | 1.00 | 0.67 | 0.03 | 63,745 | $0.002324 |
| Morning Glory | 8 | 1.00 | 1.00 | 0.88 | 0.00 | 11,093 | $0.000687 |
| Piccolo | 14 | 1.00 | 1.00 | 0.93 | 0.00 | 18,886 | $0.000971 |
| The Pink Door | 29 | 0.97 | 1.00 | 0.97 | 0.00 | 24,837 | $0.001900 |
| **AVERAGE** | **20.9** | **0.95** | **0.99** | **0.91** | **0.02** | **26,939** | **$0.001428** |

**Key findings:**

- **Name extraction accuracy: 95%** — the one outlier is Benihana (0.69), driven by its dense multi-column teppanyaki format where OCR conflates column boundaries. All other menus hit 0.92+.
- **Description accuracy: 99%** — near-perfect across all menus. GPT-4o is highly reliable at preserving description text once OCR produces clean input.
- **Price accuracy: 91%** — main failure mode is Juniper & Ivy (0.67), a multi-page menu with inconsistent price formatting (some prices on separate lines, some inline). A post-processing normalization pass would close this gap.
- **Hallucination rate: 2%** — Benihana accounts for almost all hallucinations (0.14), again due to column parsing errors causing item merges. All other menus are at 0.00–0.03.
- **Average latency: 27s** — dominated by the GPT-4o call (~20s). Juniper & Ivy peaks at 64s due to menu length (34 items across multiple pages). Parallelizing OCR and embedding stages would reduce this significantly.
- **Average cost: $0.0014/image** — well within practical range for a production API.

**Eval set:** 9 images, all fully labeled. Small set — metrics should be interpreted as directional, not definitive.

---

## API

### `POST /extract`

Accepts a menu image. Returns structured items, semantic search ID, latency breakdown, and cost.

**Request:** `multipart/form-data`
- `file` — image file (JPEG, PNG, WEBP, GIF)
- `dietary_restrictions` — JSON string array, e.g. `'["dairy", "gluten"]'`

**Response:**
```json
{
  "scan_id": "6c6a30d4-...",
  "items": [
    {
      "name": "Carbonara Rigatoni",
      "description": "Prosciutto ham, oil, egg yolk, grated parmigiana, cracked pepper.",
      "category": "pasta",
      "price": "$18",
      "common_ingredients": ["prosciutto", "egg yolk", "parmesan", "pepper"],
      "obscure_ingredient_notes": [],
      "user_dietary_flags": ["dairy"],
      "validation_warnings": []
    }
  ],
  "ocr_text": "...",
  "latency_breakdown": { "stage1_ocr_ms": 2100, "stage2_llm_ms": 19400, "total_ms": 21500 },
  "cost_usd": 0.001428
}
```

### `POST /search`

Semantic search over a previously extracted menu using FAISS.

**Request:** `application/json`
```json
{ "scan_id": "6c6a30d4-...", "query": "something creamy with pasta", "k": 5 }
```

**Response:**
```json
{
  "results": [{ "name": "Carbonara Rigatoni", "score": 0.8989, "...": "..." }],
  "query": "something creamy with pasta",
  "scan_id": "6c6a30d4-..."
}
```

---

## Tech Stack

- **Backend:** Python, FastAPI, Google Vision API, GPT-4o, OpenAI `text-embedding-3-small`, FAISS
- **Frontend:** Vanilla JS, HTML/CSS
- **Deployment:** Render (single service — backend serves frontend as static files)

---

## Setup

See [SETUP.md](SETUP.md) for local development instructions and [DEPLOYMENT.md](DEPLOYMENT.md) for Render deployment.