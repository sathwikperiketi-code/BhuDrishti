# Phase 5 demo and operations API

This is a local, synthetic presentation workflow. It does not connect to a government registry, certify ownership, or use official parcel geometry. Ordinary uploads still use their actual bytes, PDF text/OCR provider, extraction evidence, and validation rules.

## Presenter flow

1. Sign in with the labeled demo officer or admin session.
2. Open `/demo` and select **Survey conflict** (recommended).
3. Start the scenario. The server creates a visibly synthetic PDF, stores it through the normal upload intake, and runs the real document pipeline. The UI may pace its presentation timeline; it does not pause server processing.
4. Open the document evidence and validation. The source says `142/3A`; a synthetic comparison record says `142/3B`. The configured score is calculated from actual validation results and may differ from an illustrative pitch number.
5. Review fields, correct the survey number to `142/3B`, resolve the mismatch, and approve as the officer.
6. Inspect the preserved AI value, officer correction, audit event, verified record, and synthetic GIS parcel.
7. Use **Reset Demo**. The previous run is archived from operational lists, search, analytics, and notifications. Source, review, record, parcel, and append-only audit history remain addressable by ID. A new run receives new IDs and the same PDF content, issue codes, and score.

The five scenario IDs are `clean-record`, `low-confidence-area`, `survey-conflict`, `missing-field`, and `duplicate-record`. The low-confidence signal is explicitly illustrative and applies only to a server-created synthetic run. Uploading the same PDF through the ordinary document endpoint uses the ordinary confidence policy, with no illustrative override, and cannot activate synthetic reference records.

## API

All paths below are under `/api/v1`. Read endpoints require a signed demo session; start/reset require `demo:setup` (admin or revenue officer). Demo Mode is disabled outside development/demo/test environments.

| Endpoint | Purpose |
| --- | --- |
| `GET /demo/phase5/scenarios` | Five descriptions, expected validation routing, sample URLs, and synthetic disclaimer. |
| `GET /demo/phase5/scenarios/{id}/sample` | Download a visibly synthetic sample PDF (development/demo only). |
| `POST /demo/phase5/scenarios/{id}/start` | Create a run and asynchronously process its source PDF. Returns `runId`, `documentId`, and a sample URL. |
| `GET /demo/phase5/runs/{runId}` | Poll status, stage, validation, score breakdown, review status, and archived flag. |
| `POST /demo/phase5/reset` | Archive active presenter runs without deleting evidence. |
| `GET /analytics/summary` | Metrics, 14-day processing volume, status distributions, and recent activity from visible persisted prototype data. |
| `GET /search?q=...` | Capped categorized record, document, and survey results across ID, owner, survey, khata, village, and district. |
| `POST /notifications/{eventId}/read` | Store an idempotent per-user read receipt without modifying the audit event. |

Analytics rates are percentages or `null` with no denominator. Approval rate uses latest approved cases divided by latest approved plus rejected cases. Review rate uses completed documents routed to human review. Conflict rate counts each completed document once when validation has an error, mismatch, or conflict. The response includes these definitions and labels the source `prototype_persisted_data`.

## Storage and integrity

Migration `0005_phase5` adds `documents.demo_scenario`, `demo_runs`, and `notification_reads`. A server-owned demo marker distinguishes a synthetic run from an ordinary upload. Demo reference rows are scoped to their scenario and cannot influence ordinary uploads. Reset sets `demo_runs.archived_at`; it does not delete documents, review attempts, verified values, parcel rows, or audit events. Default operational lists omit archived runs; direct ID links and audit queries retain history.

This remains a local prototype: demo sessions use a process-local signing key, background processing is in-process, GIS polygons are synthetic, and audit append-only rules are enforced at the application ORM level rather than by a write-once database or cryptographic log.
