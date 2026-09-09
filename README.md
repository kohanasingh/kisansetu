# KisanSetu 

**Har Kisan tak, Har Jawab.**

KisanSetu is a **Smart India Hackathon (SIH) 2025 winning project**. It turns the farmer and crop records an FPO (Farmer Producer Organization) already has sitting in files into AI-generated advisory for its farmers, and gives those farmers a voice-first assistant they can reach on their own real WhatsApp, in their own language.
- Live Demo -  `https://kisansetu-zplmpppmgq-el.a.run.app/`

## The problem

India's agricultural value chain is broken at the information layer, not the production layer. FPOs already hold years of records — yields, land sizes, crops, farmer phone numbers — that sit in filing cabinets nobody opens. Farmers, meanwhile, are often guessing: what to grow, where to sell it, what their soil actually suits, what MSP (Minimum Selling Price) they're entitled to, which government scheme they qualify for. Those schemes and subsidies go unclaimed not because they don't exist, but because the person eligible for one never hears about it. The data to fix this already exists on both sides — it just never gets connected.

## What KisanSetu does

Two sides of the same conversation:

- **FPO dashboard** (`/fpo`) — staff upload farmer/crop/yield records as Excel sheets or scanned paper registers, review what got parsed before anything is saved, and see AI-generated advisory (storage recommendations, crop planning, scheme matching) reasoned live from their own FPO's data. A built-in chatbot answers staff questions about their own roster, warehouses, and alerts.
- **Farmer assistant** — a voice-first WhatsApp bot. A farmer texts or sends a voice note in their own language and gets an answer grounded in their own record and their FPO's data (or the nearest FPO's, or general knowledge, in that order, with the assistant saying plainly which one applied). The integration is a real Meta WhatsApp Cloud API adapter, not a stub. Since testing against a live WhatsApp Business number isn't always possible, the site's `/demo` page mirrors the exact same conversation in a WhatsApp-styled UI, driven by the identical backend path — so anyone can try the real thing without a phone number.

## Live demo

- Landing page: `https://kisansetu-zplmpppmgq-el.a.run.app/`
- Live farmer-chat demo: `https://kisansetu-zplmpppmgq-el.a.run.app/demo`
- FPO dashboard: `https://kisansetu-zplmpppmgq-el.a.run.app/fpo`

Runs on Cloud Run's free tier with scale-to-zero — see [Deployment](#deployment) for what that means for the first request after a quiet period.

## Tech stack

- **Backend:** FastAPI + Uvicorn (Python), single in-process app — no external database (see [Known limitations](#known-limitations--out-of-scope)).
- **Language models:** OpenAI GPT-4o for intent classification, grounded Q&A, and Vision (document/photo reasoning); Whisper (`whisper-1`) for speech-to-text; `gpt-4o-mini-tts` for spoken replies. Google Gemini (`gemini-flash-lite-latest`) is used narrowly — as the primary reasoning model for the FPO advisory agent (falling back to GPT-4o if Gemini is unavailable) and for a secondary translation quality-pass — everything else stays on OpenAI.
- **Weather:** Open-Meteo — free, no API key, real forecasts (not mocked), evaluated against fixed thresholds for heavy rain / storm / drought risk.
- **Ingestion:** pandas + openpyxl for Excel/CSV parsing; GPT-4o Vision directly for scanned paper registers (no separate OCR engine).
- **Frontend:** static HTML/JS with the Tailwind CDN, no build step, no framework.
- **Deployment:** Docker, single container, Google Cloud Run.

## Architecture

Three pages, one backend, two ways in for a farmer:

```
   Farmer, real WhatsApp        Anyone, browser (/demo)
          |                              |
          v                              v
transports/whatsapp_cloud.py   transports/web_console.py
          |                              |
          +---------------+--------------+
                          |
                          v
          orchestrator/farmer_router.py
                          |
          orchestrator/identity.py  (4-path resolution:
                          |          phone -> named FPO -> nearest FPO -> general knowledge)
                          v
   +----------------------+----------------------+
   v                      v                       v
agents/advisory.py   agents/climate.py    agents/farmer_query.py
(storage/crop/         (weather alerts)    (grounded Q&A + photos)
 schemes)
   |                      |                       |
   +----------------------+-----------------------+
                          |
                          v
                    db/store.py
                    /          \
        db/dummy_data.py     staged uploads, once an FPO
     (seeded FPOs/farmers/    approves them via
      warehouses only)        agents/ingestion.py

   FPO staff, browser (/fpo)
          |
          v
   orchestrator/fpo_router.py --> agents/advisory.py, agents/ingestion.py
```

**The farmer side has two transports sharing one orchestrator path.** `transports/whatsapp_cloud.py` is a genuine Meta WhatsApp Cloud API integration — webhook receiver and sender, not a stub. `transports/web_console.py` drives the *identical* `orchestrator/farmer_router.py` logic, styled to look like a WhatsApp conversation, so the `/demo` page is a real live agent, not a scripted replay — a judge typing or speaking into it gets a genuinely generated answer.

**The agents**, each one job:
- `orchestrator/identity.py` — resolves who a farmer is in four steps: registered phone number → named their FPO → nearest FPO to a mentioned village → general knowledge only, if none of those land.
- `agents/farmer_query.py` — grounded free-form Q&A (including a photo or soil-report scan) from a facts dict built from the resolved farmer/FPO, never from invented data.
- `agents/advisory.py` — storage recommendations (real lookup over seeded warehouse data), crop planning, and government-scheme matching.
- `agents/ingestion.py` — Excel/CSV parsing and GPT-4o Vision reading of scanned registers, always staged for FPO review before anything reaches the farmer roster.
- `agents/climate.py` + `jobs/scheduler.py` — periodic and on-demand Open-Meteo checks that raise real weather alerts.

**Why there's no RAG or vector database.** No FPO has actually onboarded into this system yet, so there's no real farmer data to index — building a retrieval pipeline against data that doesn't exist would be solving a problem this prototype doesn't have. Instead, every agent call fetches structured facts through `db/store.py` and injects them into the prompt directly as JSON. This is a deliberate scope decision for the current data size, not a missing feature: `db/store.py` is the seam designed to swap in real ingestion and a real retrieval layer once actual FPO data exists, without touching any calling code.

## Setup — running it locally

```bash
git clone <this-repo-url>
cd kisansetu
cp .env.example .env
```

Fill in `.env`:
- `OPENAI_API_KEY` — required. Get one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
- `GOOGLE_API_KEY` — optional. Without it, the advisory agent always falls back to GPT-4o and translation is skipped (fail-open) — nothing breaks. Get one at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
- `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN` — only needed to receive messages from a real Meta WhatsApp Business number. Leave blank to use the `/demo` mimic instead.

Install and run:

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/` (landing), `/demo` (live farmer chat), or `/fpo` (staff dashboard).

## Deployment

Two Cloud Run configurations are documented in [`deploy/cloud_run.md`](deploy/cloud_run.md) — both are real and both work:

- **`--min-instances 1`** — always-on, no cold start, but a standing monthly compute cost even while idle.
- **`--min-instances 0`** — scale-to-zero, **currently in use**. Runs on Cloud Run's free tier — the first request after a period of inactivity takes a few seconds to wake the service, and in-memory session/demo state resets when that happens.

The always-on config remains available as a documented future-scaling path if steady traffic ever justifies it; it isn't in use right now.

## Further scope, not implemented yet

These are deliberate scope decisions for a prototype, not oversights:

- **No RAG / vector database.** See [Architecture](#architecture) above — the documented upgrade path is to swap `db/store.py`'s in-memory lookups for real ingestion plus retrieval once real FPO data exists.
- **Seeded, not real, FPO data.** `db/dummy_data.py` stands in for actual onboarded FPOs (a handful of FPOs, farmers, and warehouses with realistic Indian regions/names) — no real farmer or FPO has used this system yet.
- **MSP figures and government scheme details come from the model's own knowledge**, not a live government data source — the app never fabricates a table of these, and the model is instructed to flag them as indicative and confirm-before-acting, but they can be outdated.
- **No login or authentication anywhere** — the FPO dashboard is reachable directly by anyone with the URL, by design, for this stage.
- **The real WhatsApp transport is implemented, not stub code, but hasn't been verified against a live Meta Business number.** Every request it makes matches Meta's documented API shape and was tested as far as possible without real credentials; the `/demo` page is the way to exercise the identical logic today.


## License

MIT — see [`LICENSE`](LICENSE).
