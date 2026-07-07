# Local Setup

## Prerequisites

- Python 3.11+
- An OpenAI API key with GPT-4o access

## Steps

**1. Clone the repo and create a virtual environment**

```bash
git clone <repo-url>
cd menu-scanner
python -m venv venv
source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Set up your environment variables**

```bash
cp .env.example .env
```

Open `.env` and add your key:

```
OPENAI_API_KEY=sk-...
```

The app uses `python-dotenv` to load this automatically on startup. Never commit `.env` — it is already in `.gitignore`.

**4. Start the server**

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
```

**5. Open the app**

Go to `http://localhost:8000` in your browser. Use `localhost` not `127.0.0.1` — the frontend routes API calls based on hostname.

---

## Notes

- The `--reload` flag watches for file changes and restarts automatically
- All logs from the pipeline (stage1, stage2, batch processing) print to the terminal at INFO level
- The eval suite lives in `eval/` and can be run independently — see the scripts there for usage
- Set a spending limit in your OpenAI dashboard to cap local testing costs