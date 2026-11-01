# Deploying ResuMatch

| Part | Host | Cost |
| --- | --- | --- |
| Frontend (Next.js) | Vercel | Free |
| Backend (FastAPI + ML models, needs about 2 GB RAM) | Render, Docker, Standard plan | About $25/month, paid from credit |
| Database | Neon Postgres | Free |
| LLM | Google AI Studio (Gemini) | Free tier |

Run all commands in PowerShell from the `ResuMatch_PGAGI` folder.

## 1. Commit and push

```powershell
git add -A
git status
```

Check the list before continuing: `.env` must NOT appear; `chroma_db/` and `bm25_indexes/` should appear.

```powershell
git commit -m "Prepare for production deployment"
git push origin main
```

## 2. Deploy the backend

1. In Render, click **New → Blueprint** and connect `ResuMatch_PGAGI`. Render reads `render.yaml`.
2. When prompted, enter these values:

   | Name | Value |
   | --- | --- |
   | `GOOGLE_API_KEY` | Your Gemini key |
   | `DATABASE_URL` | The value from `backend/.env` with `-pooler` removed from the host |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` (replaced in step 4) |

3. Click **Apply**. The first build takes about 10 to 20 minutes.
4. Copy the service URL and open `https://YOUR-SERVICE.onrender.com/ready`.

   Expected result: `{"status":"ready"}`

The Standard plan (2 GB RAM) costs about $25 a month, so check your credit in Render's billing page. Smaller plans don't have enough memory.

## 3. Deploy the frontend

1. Go to https://vercel.com/new, sign in with GitHub and import `ResuMatch_PGAGI`.
2. Set **Root Directory** to `frontend`. Leave the framework as Next.js.
3. Add this environment variable, with no trailing slash:

   `NEXT_PUBLIC_API_URL` = `https://YOUR-SERVICE.onrender.com`

4. Click **Deploy** and copy the production URL, for example `https://resumatch-xyz.vercel.app`.

## 4. Connect the two

In the Render service **Environment** tab, set `ALLOWED_ORIGINS` to your Vercel URL, with no trailing slash:

`https://resumatch-xyz.vercel.app,http://localhost:3000`

Render redeploys by itself.

## 5. Test it

Open the Vercel URL and run one full interview: choose a role, upload a PDF resume, answer the questions and view the summary.

## Updating later

- **Frontend:** `git push`. Vercel redeploys automatically.
- **Backend:** `git push`. Render redeploys automatically.
- **Rebuilt indexes:** run `ingest.py` locally, commit, then push.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Browser shows "Failed to fetch" or a CORS error | `ALLOWED_ORIGINS` doesn't match the site exactly | Use the exact URL with `https://` and no trailing slash |
| Frontend calls `localhost:8000` | `NEXT_PUBLIC_API_URL` is missing | Add it in Vercel, then **Redeploy** (it's read at build time) |
| Service crashes with `unexpected keyword argument 'sslmode'` | Query string left on `DATABASE_URL` | Remove everything after `?` |
| Errors mentioning prepared statements | Neon pooled host | Use the direct host |
| `/ready` returns 503 "Indexes missing" | Indexes weren't uploaded | Check `backend/chroma_db/` and `backend/bm25_indexes/` are on GitHub |
| Questions look generic | Gemini quota reached, so the fallback is being used | Check the Render logs and your Gemini quota |

Backend logs are in the Render service under **Logs**.
