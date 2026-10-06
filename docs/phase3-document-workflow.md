# Phase 3 document intelligence workflow

## End-to-end path

```text
PDF / JPG / JPEG / PNG / TIFF upload
  → signature and size checks; UUID storage; page preview
  → OpenCV preprocessing and metadata
  → per-page embedded PDF text or local Tesseract OCR
  → layout regions and deterministic field candidates
  → canonical land-record normalization with source evidence
  → field, record, and supplied-reference validation
  → 50/30/20 weighted score, warning penalties, configured route
  → persisted document, evidence, and review preparation
```

`POST /api/v1/documents/upload` returns the stored document and preview pages. `POST /api/v1/documents/{id}/process` starts the background task; `GET /api/v1/documents/{id}/processing-status` returns persisted stage states and errors. `GET /api/v1/documents/{id}` returns OCR regions, canonical extraction, field confidence/evidence, validation issues, score breakdown, warnings, and metadata. `GET /api/v1/documents` lists uploads; `GET /api/v1/documents/{id}/pages/{page}/image` serves a page preview.

The workflow records upload, preprocessing, OCR, field extraction, normalization, validation, quality score, and final routing as separate stages. The browser polls actual status, stops on completion/failure, and offers retry. If OCR is unavailable or recognizes no text, the document records an explicit failure instead of substituting synthetic output. The provider can be selected with `BHUDRISHTI_OCR_PROVIDER=auto|tesseract|pdf_text`.

## Evidence and checks

Each extracted field carries a value, extraction confidence, method, warning list, source page, and normalized bounding box when available. Clicking a field opens its page and highlights the source region. Confidence describes a heuristic extraction signal, not a calibrated probability or legal certainty. Searchable PDF text has no OCR confidence, so its field confidence is rule-derived. Some fields may have no source box when the source layout cannot be resolved.

Field validation checks required values, formats, ranges, area units, and low extraction confidence. Record validation checks completeness, logical consistency, and duplicate combinations. Cross-system validation compares supplied stored/reference records for parcel, village, area, ownership, and related-record conflicts. The default score is `0.50 × field + 0.30 × record + 0.20 × cross-system − warning penalties`. Defaults route scores below 60 to rejected, 60 to below 85 to human review, and 85 or above to approved. Weights and thresholds are environment settings. Even an approved route is an automated recommendation pending human verification.

Live cross-system checks use locally stored prototype records when they match parcel identifiers. They do not connect to an official government registry. If no comparison is available, the result reports that explicitly and routes toward human review.

## Synthetic presentation cases

`GET /api/v1/demo/analysis-cases` lists five deterministic, labeled cases. `GET /api/v1/demo/analyses/{case_id}` runs the same extraction and validation services on synthetic OCR regions and synthetic references. The cases are clean record, low confidence area, survey number conflict, missing owner, and duplicate record. Their values and scores are reproducible for a presentation. They are never presented as OCR results from an uploaded document. Seven earlier Phase 2 extraction fixtures remain available for visual storyboards.

## Upload limits and configuration

The server allowlists extensions and media signatures, rejects malformed/unsupported files, limits uploads to 20 MiB and 25 pages by default, and stores files under generated IDs instead of submitted paths. Source files are outside the web root. Useful settings include `BHUDRISHTI_DOCUMENT_STORAGE_DIR`, `BHUDRISHTI_UPLOAD_MAX_BYTES`, `BHUDRISHTI_UPLOAD_MAX_PAGES`, `BHUDRISHTI_RENDER_DPI`, `BHUDRISHTI_OCR_LANGUAGE`, `BHUDRISHTI_TESSERACT_CMD`, and the `BHUDRISHTI_PREPROCESS_*` options.

On the verified development machine, Tesseract has English and orientation data only. Install additional language packs and set `BHUDRISHTI_OCR_LANGUAGE` before processing regional scripts. Searchable PDFs use embedded text without claiming OCR recognition.

## Verification and limits

Run `python -m pytest` and `python -m alembic check` under `backend/`. Export OpenAPI with `python -m scripts.export_openapi`; then run `npm run generate:api`, `npm run lint`, `npm run typecheck`, and `npm run build` under `frontend/`. The UI should also be inspected at 1440, 1280, 1024, 768, and 390 pixels.

This is a local prototype. The background task runs in the API process rather than a durable external worker. No official reference data, model-based handwriting understanding, authentication, officer decision persistence, or complete review module is connected. GIS, analytics, advanced RBAC, and full audit workflows are intentionally outside Phase 3.
