# Deploying ResuMatch

| Part | Host | Cost |
| --- | --- | --- |
| Frontend (Next.js) | Vercel | Free |
| Backend (FastAPI + ML models, needs about 2 GB RAM) | Hugging Face Spaces, Gradio SDK | Free (16 GB RAM) |
| Database | Neon Postgres | Free |
| LLM | Google AI Studio (Gemini) | Free tier |

Run all commands in PowerShell from the `ResuMatch_PGAGI` folder.

## 1. Commit and push

```powershell
git add -A
git status
```

Check the list before continuing: `.env`, `chroma_db/` and `bm25_indexes/` must NOT appear.

```powershell
git commit -m "Prepare for production deployment"
git push origin main
```

## 2. Deploy the backend

1. Sign up at https://huggingface.co.
2. Create a Space at https://huggingface.co/new-space:
   - Name: `resumatch-api`
   - SDK: **Gradio**, template **Blank** (`backend/app.py` starts FastAPI; no Gradio UI is used)
   - Hardware: **CPU basic (free)**
   - Visibility: **Public** (the browser must reach it without a token)
3. Create a token with **Write** access at https://huggingface.co/settings/tokens.
4. In the Space, open **Settings → Variables and secrets** and add these as **Secrets**:

   | Name | Value |
   | --- | --- |
   | `GOOGLE_API_KEY` | Your Gemini key |
   | `DATABASE_URL` | Same value as in `backend/.env` |
   | `LLM_MODEL` | `gemini-2.5-flash` |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` (replaced in step 4) |

   `DATABASE_URL` must look like `postgresql+asyncpg://USER:PASSWORD@HOST/DBNAME`. Use Neon's direct host (no `-pooler` in the name) and remove anything after `?`, such as `?sslmode=require`.

5. Upload the backend. Replace `YOUR_USERNAME`:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -U huggingface_hub
   .\.venv\Scripts\hf.exe auth login
   .\.venv\Scripts\hf.exe upload YOUR_USERNAME/resumatch-api .\backend . --repo-type=space --exclude ".env" "*.log" "*.db" "knowledge_base/*" "__pycache__/*" "*/__pycache__/*" "test_*" "debug_headings.py" "Dockerfile" ".dockerignore"
   ```

   The excludes keep your secrets and the textbook PDFs out of the Space. Do not drop them.

6. Wait for the Space status to show **Running** (first build takes about 10 to 20 minutes). Then open:

   `https://YOUR_USERNAME-resumatch-api.hf.space/ready`

   Expected result: `{"status":"ready"}`

## 3. Deploy the frontend

1. Go to https://vercel.com/new, sign in with GitHub and import `ResuMatch_PGAGI`.
2. Set **Root Directory** to `frontend`. Leave the framework as Next.js.
3. Add this environment variable, with no trailing slash:

   `NEXT_PUBLIC_API_URL` = `https://YOUR_USERNAME-resumatch-api.hf.space`

4. Click **Deploy** and copy the production URL, for example `https://resumatch-xyz.vercel.app`.

## 4. Connect the two

In the Space secrets, set `ALLOWED_ORIGINS` to your Vercel URL, with no trailing slash:

`https://resumatch-xyz.vercel.app,http://localhost:3000`

The Space restarts by itself. If it doesn't, use **Settings → Factory rebuild**.

## 5. Test it

Open the Vercel URL and run one full interview: choose a role, upload a PDF resume, answer the questions and view the summary.

## Updating later

- **Frontend:** `git push`. Vercel redeploys automatically.
- **Backend:** run the `hf upload` command from step 2 again.
- **Rebuilt indexes:** run `ingest.py` locally, then run `hf upload`.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Browser shows "Failed to fetch" or a CORS error | `ALLOWED_ORIGINS` doesn't match the site exactly | Use the exact URL with `https://` and no trailing slash |
| Frontend calls `localhost:8000` | `NEXT_PUBLIC_API_URL` is missing | Add it in Vercel, then **Redeploy** (it's read at build time) |
| Space crashes with `unexpected keyword argument 'sslmode'` | Query string left on `DATABASE_URL` | Remove everything after `?` |
| Errors mentioning prepared statements | Neon pooled host | Use the direct host |
| `/ready` returns 503 "Indexes missing" | Indexes weren't uploaded | Check `chroma_db/` and `bm25_indexes/` exist in the Space's Files tab |
| Questions look generic | Gemini quota reached, so the fallback is being used | Check the Space logs and your Gemini quota |
| First load is slow | Free Space slept after about 48 hours idle | Wait a minute or so while it wakes |

Backend logs are in the Space under **Logs → Container**.
