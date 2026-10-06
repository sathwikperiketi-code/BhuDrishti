# Phase 2 product experience

## Scope

The Phase 2 interface adds an operational shell, responsive navigation, Command Center, document evidence workspace, processing playback, extraction panel, and validation storyboard on the existing Phase 1 API. The backend, OpenAPI contracts, migrations, scoring policy, and tests were preserved.

The UI fetches `GET /api/v1/health`, `GET /api/v1/demo/cases`, and `GET /api/v1/demo/extractions/{case_id}`. Dashboard operational figures are illustrative. The document viewer renders a synthetic facsimile from fixture fields and uses the API's field provenance coordinates for linked highlights. Playback stages, validation checks, and quality scores are clearly labeled story examples; the API validation state stays pending. No source document is uploaded or OCR processed in this phase.

## Design system

`frontend/src/styles/tokens.css` defines color, typography, spacing, radius, border, shadow, status, and motion tokens. The shared `frontend/src/components/ui/` exports:

Button, IconButton, Badge, StatusBadge, Card, MetricCard, DataTable, Tabs, Tooltip, Dropdown, Modal, Drawer, ProgressBar, ConfidenceBar, Timeline, EmptyState, ErrorState, Skeleton, Toast, CommandBar, Breadcrumb, and PageHeader.

Motion uses the existing Framer Motion dependency with reduced-motion handling. Dashboard and workspace code are lazy-loaded by route.

## Responsive and accessible behavior

The desktop sidebar collapses and remembers its state. At narrow widths the shell switches to a drawer and a compact bottom navigation. The workspace stacks the evidence viewer and extraction or validation panel. The key layouts were visually inspected at 1440, 1280, 1024, 768, and 390 pixels.

Semantic landmarks, visible focus states, a route-safe skip link, keyboard navigation search, dialog focus traps and restoration, and reduced-motion support are included. Review links lead to a clearly marked planned page until the officer workflow exists.

## Verification

From `frontend/`: `npm run lint`, `npm run typecheck`, `npm run build`.

From `backend/`: `python -m pytest` (7 passing tests at Phase 2 handoff).

The running frontend was checked in a browser at the target widths, including dashboard, document, processing, validation, mobile navigation, search, case switching, and source/value conflict display. No page-level horizontal overflow or browser runtime errors remained after visual fixes.

## Changed files and dependencies

- Shell and routing: `frontend/index.html`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/components/Brand.tsx`, and all files in `frontend/src/app/`.
- Shared system: `frontend/src/styles/tokens.css`, `frontend/src/lib/motion.ts`, and all files in `frontend/src/components/ui/`.
- Features: all files in `frontend/src/features/dashboard/` and `frontend/src/features/workspace/`.
- Handoff: repository `README.md`, `frontend/README.md`, and this document.
- Backend code, migrations, contracts, tests, and package manifests were unchanged. No dependencies were added.

## Browser fixes made during Phase 2

- Removed a CSS class collision between the workspace container and synthetic document page, plus a second collision in the heading line.
- Improved operational label contrast and size on light workspace surfaces.
- Kept the selected synthetic case synchronized with same-route URL changes.
- Made the skip link preserve hash routing; search, logout, and mobile navigation dialogs now trap and restore keyboard focus.
- Clarified field review cues and processing stage status while preserving the API's pending validation state.
