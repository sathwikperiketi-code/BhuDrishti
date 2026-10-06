# BhuDrishti AI architecture

The operational path uses uploaded bytes and persisted database state. React displays backend responses; it does not create extraction values, scores, approval states, or processing progress.

```text
Named user → password login → revocable server session
    ↓
PDF or image upload → validated bytes → UUID storage + document row
    ↓
Page rendering → OpenCV preprocessing
    ↓
PyMuPDF embedded text when usable; otherwise Tesseract on rendered pages
    ↓
Persisted page text, regions, provider, language, and stage transitions
    ↓
Inline-label and aligned-table extraction → normalized record + field evidence
    ↓
Field / record / officer-approved local-reference validation → configured quality score
    ↓
Persisted review case → attributed officer edits and issue resolutions
    ↓
Authorized approval transaction → final record + audit
    ↓
Officer-imported, source-referenced GeoJSON boundary → validated WGS84 geometry + GIS audit
```

## Service boundaries

- `app/api/routes/` handles HTTP contracts and permission checks. `app/services/auth/` authenticates persisted users, signs revocable sessions, and checks server-side roles.
- `app/services/documents/storage.py` validates file type, signatures, MIME, size, page count, image dimensions, and safe storage paths. It stores original bytes and rendered pages under a generated UUID.
- `app/services/documents/preprocess.py` creates actual normalized page images. `ocr.py` chooses usable PyMuPDF text first or invokes local Tesseract. It reports installed versus requested languages and fails visibly when a scan cannot be recognized.
- `app/services/documents/pipeline.py` persists stage status, OCR/text output, extraction, validation, score, routing, errors, records, review cases, and audit events. Current execution uses an API background task, so a durable external queue would be needed for production operations.
- `app/services/intelligence/` recognizes labeled lines and geometrically aligned table cells, normalizes fields, and attaches page/source text/value-cell coordinates. Tesseract provides a measured recognition signal. Embedded PDF text has no OCR probability; its confidence is `null` and is shown as unavailable.
- `app/services/intelligence/validation.py` applies field, record, and local-reference checks. Only records with an attributed officer approval, or explicitly trusted imported references, may participate in operational comparisons. The configured score combines field, record, and reference contributions at 50%/30%/20%; unavailable references create an explicit issue. A high score remains a recommendation, not an approval.
- `app/services/review/service.py` creates an officer case for every processed record and retains an immutable original extraction snapshot alongside reviewed values. Edits and issue resolutions identify the actor and reason. Approval checks the current reviewed record, writes canonical values, and appends audit in one database transaction.
- `app/services/gis.py` keeps parcel metadata even when no boundary is available. An officer can import a GeoJSON Polygon for an approved record with a required source reference; the service checks geometry and stores its provenance before drawing it. Legacy virtual-grid polygons are withdrawn from operational GIS. An imported boundary is not an independently verified cadastral boundary.

## Persistence and history

SQLAlchemy models and Alembic migrations store users, sessions, documents, source/page metadata, OCR regions, extracted fields and evidence, records, reviews, audit events, parcels, and notification reads. OCR and extraction details are persisted as structured JSON on the document and record rows; relational keys link documents, records, reviews, parcels, and audit entries. SQLite is the local default and PostgreSQL can be configured.

Historical Phase 5 presentation rows and columns remain in the schema for audit retention. Each document has a persisted operational or sample dataset scope and a classification reason. Migration `0011` classifies existing demo rows and documents with explicit synthetic evidence without deleting sources, records, or audit events. New uploads may declare the sample scope, and source-authored synthetic notices promote a document to that scope after OCR. Operational lists, counts, search, review actions, and GIS exclude sample rows server-side; sample evidence is available through explicit scoped read requests and the read-only `#/demo` view. Neither sample nor unapproved records can become operational comparison references.

## API and client

The API is versioned at `/api/v1`; OpenAPI is exported by `python -m scripts.export_openapi`, and frontend types are generated with `npm run generate:api`. The React app uses hash routes for Dashboard, Documents, Processing, Validation, Review, Records, GIS, Analytics, Audit, Settings, and the separate Sample dataset. It polls operational document status and renders only the stages returned by the backend. The document viewer uses normalized field evidence boxes to navigate the actual rendered page.

Named accounts use a local password provider and revocable bearer sessions. An administrator is bootstrapped after migrations via `python -m scripts.bootstrap_admin --email ... --name ...`; there are no built-in accounts. Admins can provision further accounts in Settings. The four roles and protected endpoints are enforced on the server. External identity, official record/cadastral connectors, durable jobs, and stronger audit storage remain integration work.

For the reported two-column PDF, the old parser treated `Owner Name` as a value and missed `Survey / Khasra No.` and `Land Area`. The current parser pairs labels with right-hand value cells using their persisted PDF geometry. The source contains no State, so State remains missing and blocks approval until an officer corroborates it. See the root README for local setup and verification commands. Older phase-specific documents describe historical iterations and may mention retired demo endpoints.
