<!-- Versioned prompt: ingestion_scan_ocr. Loaded via
llm.load_prompt("ingestion_scan_ocr").

Powers the scanned-document branch of agents/ingestion.py. Instruct GPT-4o
Vision to read a photographed or scanned paper register and return
structured JSON matching the farmer / crop_record schema in
PROJECT_SPEC.md. Must flag low-confidence or unreadable fields rather than
inventing values — output is staged for human review, and a confident wrong
row is worse than a flagged blank one. -->
