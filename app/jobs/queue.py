"""In-process fire-and-forget async job queue — asyncio.create_task with
error logging, no external broker.

Used for background ingestion parsing, advisory generation, and anything
that must continue after a request returns. Note this is why Cloud Run needs
--no-cpu-throttling (see deploy/cloud_run.md).
"""
