# Startup research workspace

## Evaluation and persistence

The homepage accepts one to ten names or websites, separated by newlines, commas, or semicolons. Duplicate names are collapsed. Two evaluations run concurrently per API process, and the remainder queue. Each company has its own status and can succeed or fail independently.

`POST /api/jobs` accepts `kind`, `names` or `problem`, `refresh`, and an idempotency `request_id`. `GET /api/jobs/{id}` is scoped to the authenticated reviewer. Background workers publish partial and completed results to Redis, so changing navigation or reloading the tab does not cancel research. The browser stores opaque job references and query labels in per-reviewer session storage; complete results stay on the server. Problem searches use the same lifecycle.

Job snapshots last 24 hours. Tracxn evaluation reports are private to their reviewer and last 30 days in Redis. Ordinary evaluations retain the existing database history. Production must use the existing Redis session backend; the in-memory backend is development-only. Running jobs do not survive an API-process restart. Jobs without updates for 30 minutes are marked interrupted and require an explicit retry. This avoids silently repeating paid provider calls.

Tracxn OAuth can now start from either research page and returns to that page. Each new evaluation attempts an exact Tracxn name/domain match when connected, then falls back to GlassDollar and the web. Authenticated vendor response shapes still require a real MCP-enabled account for live validation. Public provider metadata was verified during implementation.

## LLM scoring and department fit

New evaluations use `core/judgment.py` (`llm-judgment-v1`). The model judges all six dimensions and the overall score directly from collected research; no point bonuses, weights, confidence multiplier, or rule-based score fallback is applied. Numeric ranges, complete dimension coverage and evidence IDs are validated. Quotations are hydrated from the original research rather than copied by the model. Department interests are explicitly available as a separate mock evidence source. Invalid or unavailable assessments are explicitly unassessed, not zero-rated. The previous scoring implementation remains only for historical replay/tests; the evaluation pipeline no longer invokes it.

Scoring & Fit keeps Decision first, then an iX department selector and an explicit Assess department fit button with Digital Industries, Smart Industries and Siemens Mobility. Mock interests come from the backend department table. The selected profile drives three explanations: relevant use case, Siemens portfolio relevance and demonstrated customer value. Integration feasibility and delivery readiness are removed.

`POST /api/runs/{id}/assessment/{department}` assesses existing research without scraping again. Access to private runs is checked against the current reviewer. Successful judgments are cached for 24 hours by reviewer, research snapshot, prompt version and department configuration. Overlapping requests for the same research share a lock so duplicate page mounts do not duplicate model calls. Prompts omit repeated inherited URLs and use concise, non-thinking structured generation to avoid assessment timeouts. Changing department never starts an LLM call. The user must press Assess department fit. Each department receives a separate holistic LLM fit score with a summary and three explanations. Successful overall scores and department assessments are persisted to the saved evaluation. The first replaced score is retained as original_score; decisions remain unchanged. Database, profile and canonical company endpoints read these same saved values. Private Tracxn results remain scoped to their owner. Database separates Overall score, Siemens fit and Department fit, with a department selector; an assessment against outdated interests is not shown as current. Saved views and CSV exports retain the department context. A new research run requires fresh department assessment.

Empower, Connect and Collaborate use Siemens iX tabs and contain only “Under development”. Portfolio fit and SFS remain. The challenge match, flags/gaps and reviewer override controls are removed. The retired override endpoint returns HTTP 410; existing audit history is retained.

## Department interests

`department_profiles` and `department_shortlists` are database-backed. Initial DI, SI, and Mobility interests are explicitly labelled demo placeholders. They do not alter official programme criteria or pretend to represent approved business-unit priorities.

The standalone Department interests page and its navigation entry have been removed. Department profiles remain backend data for Scoring & Fit and Database. Administrators can configure the profiles through `PUT /api/departments/{id}`.

## Local startup

Run `bash scripts/run_api.sh` and `npm --prefix ui run dev`. The API reloads code changes and uses local development sessions when Redis is unavailable. Memory sessions and jobs are lost when the API restarts; production continues to use Redis through `start.sh`. If searches report a missing search service, restart the API so `/api/jobs` is registered. Tracxn login is optional for both evaluation and problem searches.
