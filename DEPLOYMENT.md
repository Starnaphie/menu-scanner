# Deployment

The app is deployed as a single Render web service. The FastAPI backend serves the frontend as static files, so no separate frontend deployment is needed.

Live URL: [menu-scanner-o1ab.onrender.com](https://menu-scanner-o1ab.onrender.com)

---

## Render setup

**1. Create a new Web Service**

Go to [render.com](https://render.com) → New → Web Service → connect your GitHub repo.

**2. Configure the service**

| Field | Value |
|---|---|
| Runtime | Python |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Instance type | Free |

Leave the root directory blank.

**3. Add environment variables**

In the Render dashboard under Environment, add:

| Key | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |

Do not add a `.env` file to the repo — Render injects env vars directly into the process.

**4. Deploy**

Click Create Web Service. The first deploy takes 2–3 minutes. Render auto-deploys on every push to the connected branch.

---

## Notes

**Cold starts:** The free tier spins down after 15 minutes of inactivity. First request after idle takes ~30 seconds. For demos, open the app beforehand to wake it up.

**Spend cap:** Set a monthly spending limit in your OpenAI dashboard to cap costs from unexpected traffic.

**HTTPS:** Render provides HTTPS automatically on `.onrender.com` domains. Camera and file access APIs require HTTPS — do not use the HTTP version.

**Accessing locally vs. production:** The frontend detects environment by hostname. Any non-Render hostname routes API calls to the local server on port 8000. Always access the local app via `http://localhost:8000`, not `http://127.0.0.1:8000`.

---

## Re-deploying

Render auto-deploys on push. To trigger a manual redeploy, go to your service dashboard → Manual Deploy → Deploy latest commit.

If the build succeeds but behavior is stale, clear `__pycache__` locally before pushing:

```bash
find . -type d -name __pycache__ | xargs rm -rf
```