# Phase 4: human review, audit, and prototype GIS

BhuDrishti AI assists with extraction and validation. A human officer makes the final verification decision. Quality scores and reference comparisons are decision aids; neither the AI output nor the synthetic map establishes legal ownership or official parcel boundaries.

## Workflow and data boundaries

```text
Uploaded PDF/image → OCR and extraction → three-layer validation → quality score
        → review queue → officer field decisions and issue resolutions
        → approve / reject / send back → attributed audit events
        → verified record → synthetic GIS parcel link
```

The Phase 3 document pipeline remains the source of OCR text, page images, extracted fields, and validation. Processing creates a review case for the configured human-review score band (default 60–84) **or** a critical validation issue at any score. Each case keeps an immutable `original_record` AI snapshot and a separate `reviewed_record`. A send-back followed by processing creates a new review attempt; it does not overwrite the earlier attempt. The review API selects the latest attempt for a record.

The queue derives priority from visible rules in `ReviewPriorityPolicy`: critical conflicts, missing required fields, possible duplicates, extraction confidence below 70%, a score below 70, and age of at least 18 hours. These defaults are adjustable in code. The response includes plain-language `priorityReasons`; there is no hidden priority model.

## Demo authentication and RBAC

`POST /api/v1/auth/demo/session` accepts `{ "userId": "officer" }` and issues an eight-hour, process-local HMAC-signed bearer session. The available local identities are `admin`, `officer`, `verifier`, and `auditor`. The response contains `accessToken`, `tokenType`, `expiresAt`, and server-derived user identity. Send `Authorization: Bearer <accessToken>` on protected requests; `GET /api/v1/auth/me` returns that identity. Changing an `X-Role` header or editing the token cannot grant a different role.

| Demo role | Server-enforced access |
| --- | --- |
| Admin | All document, review, record, audit, GIS, and demo setup actions. |
| Revenue officer | Upload/process, read documents, review/edit, assign or claim, approve/reject/send back, read records/audit/GIS, and prepare the synthetic demo. |
| Verifier | Read documents/records/reviews, start review, edit fields, resolve issues, and make a recommendation. Cannot make a final decision. |
| Auditor | Read documents/reviews/records/audit/GIS. Cannot upload, process, edit, or decide. |

The role switcher is **demo authentication**, enabled only when `BHUDRISHTI_ENVIRONMENT` is `development`, `demo`, `test`, or `testing`. It is deliberately easy to choose a demo identity and must not be presented as real identity verification. Production mode disables these sessions; integrate a trusted identity provider and persistent key management before deployment. The signed token secret changes when the API process restarts, so existing demo sessions need to be recreated.

## API contracts

All paths below are under `/api/v1`. JSON keys use camelCase. Protected routes require the bearer session.

| Method and path | Purpose | Permission |
| --- | --- | --- |
| `GET /reviews` | Active latest-attempt queue; `filter=all\|high_priority\|low_confidence\|conflicts\|missing_fields\|assigned_to_me\|unassigned`, `search`, `sort=submitted_at\|quality_score\|priority`, `direction=asc\|desc`, `limit`, `offset`. Returns `{items,total}`. | Review read |
| `GET /reviews/{recordId}` | AI original, officer record, document ID, field evidence, validation, issue resolutions, priority, summary, and GIS state. | Review read |
| `POST /reviews/{recordId}/start` | Start review and append `REVIEW_STARTED`. | Review edit |
| `POST /reviews/{recordId}/fields/{fieldName}` | `{action:"accept"\|"edit"\|"reject", reviewedValue?, reason?}`. Edit requires a value; reject requires a reason. | Review edit |
| `POST /reviews/{recordId}/accept-clear-fields` | One explicit officer action to accept present fields with no field issue; appends a separate `FIELD_ACCEPTED` event for each. | Review edit |
| `POST /reviews/{recordId}/issues/{issueCode}/resolve` | `{fieldName?,resolution:"corrected"\|"confirmed"\|"not_applicable",reason}`. A correction must include a valid field edit. | Review edit |
| `POST /reviews/{recordId}/recommendation` | `{recommendation:"approve"\|"reject"\|"send_back",reason}` without final disposition. | Verifier or admin |
| `POST /reviews/{recordId}/assign` | `{officerId}`. Admin can assign an eligible demo officer; a revenue officer can claim self. | Review assign |
| `POST /reviews/{recordId}/decision` | `{decision:"approve"\|"reject"\|"send_back",reason?}`. Reject and send back require a reason. | Admin or revenue officer |
| `GET /audit/events` | Timeline events; optional `recordId`, `eventType`, `limit`, `offset`. | Audit read |
| `GET /records`, `GET /records/{recordId}` | Registry and detail with review, audit, and parcel context. | Record read |
| `GET /gis/parcels`, `GET /gis/parcels/{recordId}` | Synthetic parcels; filters for state, district, village, validation status, record status, and search. | GIS read |
| `GET /notifications` | Recent meaningful events derived from audit history. | Record read |
| `POST /demo/phase4/setup` | Development-only idempotent synthetic reference setup. | Admin or revenue officer |
| `GET /demo/phase4/sample` | Download a clearly labeled synthetic PDF in development. | Public demo sample |

`GET /reviews/{recordId}` returns a `summary` with `fieldsReviewed`, `fieldsTotal`, `warningsResolved`, `warningsTotal`, `criticalConflicts`, `canApprove`, and `blockingReasons`. The document viewer uses `GET /documents/{documentId}` and authenticated page-image fetches for source highlighting. Image blobs are held only while the viewer is open and their object URLs are revoked afterward.

### Approval and correction rules

An officer can approve only after every reviewable field has an explicit action, no field remains rejected, every validation issue has an explicit human resolution, and required values are present. The server returns HTTP 409 with blocking reasons if the gate is incomplete. `corrected` checks the officer edit and, for concrete reference mismatches such as survey number, checks the expected value. `confirmed` and `not_applicable` require a reason and preserve the underlying original warning as historical evidence. Editing a field again invalidates its current issue resolution, so a stale resolution cannot pass approval.

Field actions retain `originalValue`, `reviewedValue`, reviewer, timestamp, and reason. `FIELD_EDITED` audit metadata includes the previous and new values. The canonical record is updated with the reviewed value only on officer approval; `DocumentModel.extraction` and the case's original AI snapshot remain intact. Rejection and send-back create distinct final dispositions and audit events. A verifier's recommendation does not approve the record.

## Persistence and audit

Alembic revision `0003_phase4` adds `review_cases`, `audit_events`, and `parcel_index`. Revision `0004_review_attempts` makes the review case `record_id` index non-unique so a later processing attempt can keep its own immutable snapshot. Run `python -m alembic upgrade head` from `backend/` after updating an existing Phase 3 database.

`app.services.audit.append_event` stages events in the same SQLAlchemy transaction as the associated review or GIS change. Each event stores ID, record/document IDs, actor ID and role, type, timestamp, description, and metadata. Upload and processing stages emit events such as `DOCUMENT_UPLOADED`, `OCR_COMPLETED`, `VALIDATION_COMPLETED`, and `CONFLICT_DETECTED`; human actions emit `REVIEW_STARTED`, `FIELD_EDITED`/`FIELD_ACCEPTED`, `ISSUE_RESOLVED`, `RECORD_APPROVED`/`RECORD_REJECTED`/`RECORD_SENT_BACK`; indexing emits `GIS_INDEXED`. The application exposes no audit update/delete route, and ORM guards reject updates and deletes. A separate ORM guard prevents replacement of the original AI snapshot.

The audit UI uses `#/audit` and `#/audit/{recordId}`. Notifications are a filtered read of meaningful audit events, not an independent push-delivery system.

## Prototype GIS

Processed records receive candidate parcels in `parcel_index`; an officer-approved record becomes `verified` and is linked to the reviewed survey and owner values in the same transaction as the approval. The GIS API returns `synthetic:true` and a disclaimer. Leaflet renders deterministic polygons in a virtual `CRS.Simple` grid. They are **not coordinates, survey boundaries, or official cadastral data**. The record detail route `#/records/{recordId}` links back to `#/gis?record={recordId}` after indexing. The GIS command center is at `#/gis`.

## Repeatable survey conflict walkthrough

The repository includes [`samples/survey-conflict.synthetic.pdf`](../samples/survey-conflict.synthetic.pdf). It visibly says it is synthetic. The source reads `Record No.: HIST-2026-041` and `Survey No.: 142/3A`; the development setup endpoint seeds a synthetic comparison record with the same record number and survey `142/3B`. Both uploads and the reference are demonstration data, not official records.

1. Start API and frontend as described in the [README](../README.md). Choose the **Revenue Officer** demo role.
2. Open `#/documents` and select **Load demo source**. The UI calls `POST /demo/phase4/setup`, downloads the sample, and uploads it through the real document intake. The setup call is idempotent.
3. Select **Process document**. The embedded PDF text goes through the normal extraction, validation, scoring, persistence, and audit path. Inspect `survey_number_mismatch` with expected value `142/3B`; the route is `human_review`.
4. Open the review queue at `#/review`, then open the record and select **Start review**. Inspect the source highlight for `surveyNumber`.
5. Select **Accept clear fields** as an explicit bulk review action. Edit `surveyNumber` to `142/3B` with a reason. Resolve `survey_number_mismatch` as `corrected`, also with a reason. Processed uploads are excluded from reference comparisons, so repeating the demo retains this single intended mismatch.
6. Confirm the summary shows `canApprove`, then approve. Follow the transition to `#/records/{recordId}`, `#/gis?record={recordId}`, and `#/audit/{recordId}`. The audit timeline records the correction, approval, and GIS link. A second upload of the same sample remains a review case with a survey conflict.

For a send-back demonstration, select **Send back** with a reason in the decision panel. The completed case then offers **Reprocess document**; processing creates a new review attempt while preserving the earlier AI snapshot and audit history.

For an API-driven run, create a session first and send its bearer token to setup, upload, process, review, and decision endpoints. The setup response provides `sampleUrl`, `referenceRecordId`, and `alreadyExisted`.

## Run and verify

Use Python 3.11+, Node.js 22.12+, and npm 10+. Install Tesseract for scanned PDFs and images; searchable PDFs can use embedded text. From `backend/`:

```powershell
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m pytest
python -m alembic check
python -m uvicorn app.main:app --reload --port 8000
```

From `frontend/`:

```powershell
npm ci
npm run generate:api
npm run lint
npm run typecheck
npm run build
npm run dev
```

The frontend runs at `http://127.0.0.1:5173`; FastAPI OpenAPI documentation is at `http://127.0.0.1:8000/docs`.

## Known limits

- Demo users can choose any displayed role. The process-local token is not a production identity or persistent session system.
- Source page images require a bearer session. Production deployments still need a trusted identity provider, transport security, and a considered media caching policy before handling private records.
- Review priority thresholds are code-configurable defaults, not an admin-managed policy UI. Assignment and notifications are local workflow features, without external delivery or workload balancing.
- The API-process background task is suitable for a prototype; a durable worker and retries are needed for production throughput.
- Audit immutability is enforced through application routes and ORM guards, not cryptographic sealing or database-level write-once storage. Database administrators retain direct modification ability.
- Older review attempts remain in the database after reprocessing, but there is no dedicated API to browse each historical snapshot by attempt ID.
- The synthetic reference is not a government data integration. GIS polygons are virtual geometry and cannot support parcel location, area measurement, or legal boundary claims.
- OCR language quality depends on installed Tesseract language data; this prototype does not include regional-language models by default.
