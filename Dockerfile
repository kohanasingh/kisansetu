# KisanSetu — single container: API + orchestrator + agents + the three
# static web pages. Deploy: Cloud Run — see deploy/cloud_run.md for the
# flag-by-flag reasoning (note that --max-instances 1 is load-bearing
# here, since all state is in-process with no external DB).

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY web/ web/

# Cloud Run injects PORT (defaults to 8080); uvicorn must bind to it.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
