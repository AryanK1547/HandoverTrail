# Changes from the Round 3 Plan

## Delivered in code and covered locally

- **Conflict and evidence-gap detection:** deterministic claim-slot comparison,
  normalization, possible-conflict labeling, gap rules, side-by-side evidence,
  and audited resolution. The synthetic fixture adds three comparisons and
  missing-evidence cases.
- **Gap-to-question exit interview:** local templates, reviewer draft
  management, assigned Departing role, timestamped interview source, and
  pending claims routed through review.
- **Provider-safe, accountable handover:** one provider gateway, public-only
  provider payloads, pattern masking, append-only claim edit history,
  immutable public-evidence release snapshots, and version acknowledgements.
- Runtime dependencies are pinned. The local synthetic-only pytest suite
  passes 36 tests; no provider requests are made by the tests.

## Local workspace and review-journey hardening

- Uploads now use a separate project/workspace token instead of the demo
  project. The token restores that workspace after navigation or refresh;
  starting a second workspace creates a separate empty project. Cached demo
  claims are not present in upload workspaces. `.md` files are parsed as
  line-based text alongside `.txt` and `.csv` files.
- Extraction is idempotent for repeated source content, records the latest
  run status and method for the UI, and applies an 80,000-character provider
  input limit with an explicit local-fallback reason.
- Review has searchable, filterable, paginated claim cards, persistent
  extraction status, and a visible evidence-check state. Role-aware navigation
  leads Incoming to the release rather than the candidate queue. The simulated
  role survives refresh through a URL parameter.
- Three Playwright journeys exercise the local reviewer queue, release and
  acknowledgement, and separate upload workspaces. Playwright controls a real
  Chromium browser; test data is temporary and provider calls are disabled.
- Verification on this branch: pytest **40 passed**, Playwright **3 passed**,
  Python compilation passed, and `git diff --check` passed.
- These hardening changes are local to `r3/ux-hardening` and are not deployed.
  The deployed findings below still describe commit `839953b`.

## Deviations and remaining work

- Optional LLM rewording for interview questions was not added; templates are
  local and deterministic.
- There is no authenticated identity, private user account, or durable hosted
  database. Workspace URLs are access-by-link, and the demo role selector is
  not an authorization boundary.
- The deployed Upload Sources page still exposes upload, demo-load, and parse
  controls to Incoming; the local branch gates them. The live UI also reports
  conflicting upload-size limits (2 MB in page text versus 200 MB in the
  widget).
- No approved claims or release were present in the observed Cloud state.
  Incoming therefore saw an empty handover. Phase D did not manually approve
  claims or create a release in the shared database. Opening Review Claims
  automatically refreshed derived conflict/gap records; exact row changes
  were not measured.
- Live Gemini/OpenRouter extraction, upload validation, empty-cloud bootstrap,
  restart behavior, cross-session effects, and complete interview/release
  journeys remain unverified on Cloud. The provider names/models documented are
  configured values, not verified results from this live QA run.
- **Schedule evidence:** the Round 3 plan says the window opened at 23:59 IST
  on 13 Nov 2026. The reachable Round 3 implementation commits and their
  merges into `main` are timestamped earlier on 13 Nov (01:43–16:23 IST).
  Phase D was also run at about 16:47–16:55 IST that day, before the stated
  opening and the plan's Monday QA block. History was not rewritten. If the
  event enforces its published dates, the work and this QA evidence may be
  ineligible; confirm with the organizer before submission.
