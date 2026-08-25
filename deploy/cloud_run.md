# Deploying KisanSetu to Google Cloud Run

One container, one URL, single instance.

## One-time setup

```bash
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
```

## Deploy (from repo root)

```bash
gcloud run deploy kisansetu \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 1 \
  --no-cpu-throttling \
  --memory 1Gi \
  --set-env-vars OPENAI_API_KEY=...,GOOGLE_API_KEY=...
```

`GOOGLE_API_KEY` (Gemini translation) is optional —
`services/translate.py` is fail-open. No DB env vars: the prototype's
data layer is in-memory, seeded from `db/dummy_data.py` at startup.

To exercise the real WhatsApp transport, also set `WHATSAPP_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, and `WHATSAPP_VERIFY_TOKEN`. Omit them for
a web-demo-only deployment.

## Why these flags

| Flag | Reason |
|---|---|
| `--no-cpu-throttling` | Two independent reasons: (1) the demo console's send/poll pattern returns fast and processes the agent chain in a background task the frontend then polls. (2) `jobs/scheduler.py`'s climate-watch tick runs between requests with no request driving it — default throttling would freeze it. |
| `--min-instances 1` | No cold starts mid-demo; keeps the job queue and scheduler loop alive. |
| `--max-instances 1` | **Architecturally required**: there is no external DB. The in-memory dataset, per-session console outboxes, and ingestion-review state all live in one process. A second instance wouldn't see the same data. Don't relax this without first adding a real shared DB. |

## After deploy

1. Landing page at `https://<cloud-run-url>/`
2. Live demo at `/demo` — no setup needed, lists sample inputs to try.
3. FPO dashboard at `/fpo` — no login.
4. For real WhatsApp: set the Meta webhook to
   `https://<cloud-run-url>/webhook/whatsapp`, verify token =
   `WHATSAPP_VERIFY_TOKEN`.
