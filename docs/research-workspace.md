# Startup research workspace

## Evaluation and persistence

The homepage accepts one to ten names or websites, separated by newlines, commas, or semicolons. Duplicate names are collapsed. Two evaluations run concurrently per API process, and the remainder queue. Each company has its own status and can succeed or fail independently.

`POST /api/jobs` accepts `kind`, `names` or `problem`, `refresh`, and an idempotency `request_id`. `GET /api/jobs/{id}` is scoped to the authenticated reviewer. Background workers publish partial and completed results to Redis, so changing navigation or reloading the tab does not cancel research. The browser stores opaque job references and query labels in per-reviewer session storage; complete results stay on the server. Problem searches use the same lifecycle.

Job snapshots last 24 hours. Tracxn evaluation reports are private to their reviewer and last 30 days in Redis. Ordinary evaluations retain the existing database history. Production must use the existing Redis session backend; the in-memory backend is development-only. Running jobs do not survive an API-process restart. Jobs without updates for 30 minutes are marked interrupted and require an explicit retry. This avoids silently repeating paid provider calls.

Tracxn OAuth can now start from either research page and returns to that page. Each new evaluation attempts an exact Tracxn name/domain match when connected, then falls back to GlassDollar and the web. Authenticated vendor response shapes still require a real MCP-enabled account for live validation. Public provider metadata was verified during implementation.

## Siemens fit rubric v1

This is a proposed internal screening rubric, not an official Siemens acceptance model. Its purpose is to make the points reviewable and identify what remains unknown.

| Criterion | Maximum points |
| --- | ---: |
| Relevant Siemens use case | 30 |
| Adds to the Siemens portfolio | 25 |
| Integration feasibility | 20 |
| Demonstrated customer value | 15 |
| Readiness to deliver | 10 |

An evidence-assisted LLM assigns levels 0–4 and returns a short rationale, an exact quote, a known evidence ID, and the next check. Python validates citations and computes `weight × level / 4`. Unsupported citations earn no points. Unverified evidence is capped at level 3 for strategic relevance/complementarity and level 2 for the other criteria. Substitute-only portfolio matches earn zero complementarity points. If model assessment is unavailable, conservative portfolio-based rules give only limited provisional points and show their lack of citations.

The rubric score feeds the existing `siemens_fit` dimension, and consequently the canonical score and route scorecards. Published programme requirements still gate eligibility. Empower, Collaborate, and Connect have distinct keyboard-accessible tabs showing their existing criteria, score gates, reasons, and next steps. Browser what-if weighting is removed. Old stored evaluations are not silently rewritten: use Refresh Data to apply this rubric.

Rubric version and evidence coverage are returned with every new assessment. Calibration against human-labelled startup decisions is still needed before treating these numbers as investment or programme-admission predictions.

## Department interests

`department_profiles` and `department_shortlists` are database-backed. Initial DI, SI, and Mobility interests are explicitly labelled demo placeholders. They do not alter official programme criteria or pretend to represent approved business-unit priorities.

Reviewers can add companies to shared unit shortlists and remove their own additions. Company evaluation data is resolved using the viewing reviewer's accessible private report or a public report; licensed results are never shared through the board. Companies with no evaluation are unassessed. Old reports require refresh for the new fit component.

The separate interest score is `60% explicit interest-term coverage + 40% Siemens fit`. Both components, matched terms, and missing terms are shown. It does not change the canonical company score. The matching is explicit text matching, not a claim of semantic proof.

Administrators can replace a demo profile through `PUT /api/departments/{id}` with `label` and `interests`; doing so clears its demo flag. Real membership restrictions and approved department criteria should be added when the real organisational data arrives. Currently these are shared internal shortlists, not permission-restricted departmental silos.

## Navigation

The primary menu contains Explore a startup, Solve a Problem, Companies, Saved views, Department interests, Tracking, and Ask AI. Settings is reached through the account control. Duplicate secondary saved-view links and the duplicate profile Assistant button have been removed.

Programme references: [Siemens for Startups](https://www.siemens.com/en-us/company/innovation/startups/) and [Collaborate](https://www.siemens.com/en-us/company/innovation/startups/collaborate/). The weighted rubric and demo department interests are application design choices, not claims from those pages.

## Local startup

Run `bash scripts/run_api.sh` and `npm --prefix ui run dev`. The API reloads code changes and uses local development sessions when Redis is unavailable. Memory sessions and jobs are lost when the API restarts; production continues to use Redis through `start.sh`. If searches report a missing search service, restart the API so `/api/jobs` is registered. Tracxn login is optional for both evaluation and problem searches.
