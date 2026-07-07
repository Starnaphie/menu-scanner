# Menu Scanner

An AI-powered web app that analyzes menu photos and returns structured item data with ingredients, allergen notes, and dietary restriction flags.

Live: [menu-scanner-o1ab.onrender.com](https://menu-scanner-o1ab.onrender.com)

---

## What it does

Upload a photo of any restaurant menu. The app extracts every food item, identifies common and obscure ingredients, and flags items that conflict with your dietary restrictions — distinguishing animal-derived ingredients from plant-based alternatives.

**Key features:**
- Two-stage GPT-4o pipeline: faithful transcription followed by culinary analysis
- Dietary restriction enforcement with animal vs. plant-based distinction (e.g. cashew milk ≠ dairy)
- Pre-analysis verification step — edit or remove extracted items before analysis runs
- Per-item ingredient breakdown with expandable obscure ingredient notes
- Star reviews and scan history persisted per user
- Add items manually after a scan with AI refinement
- Guest mode (session-only) and full account support
- Works on any browser and device over HTTPS

---

## Architecture

```
frontend/index.html        Vanilla JS single-page app, served as static files
backend/main.py            FastAPI app — HTTP middleware, endpoints, CORS
backend/extractor.py       Two-stage GPT-4o pipeline
```

**Pipeline:**

Stage 1 — `/scan/stage1` (vision): GPT-4o reads the menu image and transcribes every food item verbatim, including any printed dietary labels.

Stage 2 — `/scan/stage2` (text): GPT-4o refines the transcription into structured objects with cleaned names, descriptions, common ingredients, obscure ingredient notes, and dietary flags. Processes items in batches of 10 to avoid token limit truncation.

`/refine-item`: Same Stage 2 logic, called for single items added manually post-scan.

---

## Tech stack

- **Backend:** Python, FastAPI, OpenAI GPT-4o
- **Frontend:** Vanilla JS, HTML/CSS (no framework)
- **Deployment:** Render (single service — backend serves frontend as static files)
- **Auth:** Client-side username/password with localStorage persistence

---

## Project structure

```
menu-scanner/
├── backend/
│   ├── main.py            FastAPI app and endpoints
│   └── extractor.py       GPT-4o pipeline (stage1, stage2, extract_menu)
├── frontend/
│   └── index.html         Full frontend (HTML + CSS + JS)
├── eval/                  LLM-as-judge eval suite
├── demo-docs/             Sample menu images
├── requirements.txt
├── run.sh
├── .env.example
├── SETUP.md
└── DEPLOYMENT.md
```