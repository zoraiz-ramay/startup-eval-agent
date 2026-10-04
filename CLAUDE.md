# Siemens Startup Evaluation Agent

Evaluates startups for Siemens partnership decisions: enrich from web evidence → verify → score six
weighted dimensions → route to a pillar (Connect / Collaborate / Empower / Pass). A FastAPI backend
wraps a pure-Python engine; a React SPA is the product surface.

## The one rule everything else serves

**Every displayed fact must be traceable to a source, or it must not be displayed.**

This app informs partnership decisions, so an invented number is worse than a blank field. The
codebase enforces this in several places, and changes must not weaken them:

- `core/profile.py` — `_program_grounded` requires a program name and the company name to
  co-occur in a *single* result before a membership counts; `_ground_customers` requires a
  relationship phrase in a short window; `_clean_employee_series` drops any datapoint without an
  `http` source; `_clean_source_url` rejects a "source" that is not a URL.
- `core/data.py` — `web_profile_row` deliberately does **not** fill verifiable fields (funding,
  founded year, employees, HQ, customers) from model memory. It used to, and produced a funding
  round of "SAR 3.75 million" for makkook.ai that exists nowhere on the web.
- There are **two** sanctioned exceptions, both in `profile.py`, both last-resort passes that run
  only after GlassDollar and every web pass have come back empty, both stamping `*_origin="llm"`,
  carrying no source URL, and labelled **unverified** rather than web-sourced by the UI:
  - `_recall_hq_offline` — headquarters, added when Location became a headline tile.
  - `_recall_links_offline` — the LinkedIn and Crunchbase profile URLs, added because a company
    outside GlassDollar routinely showed both rows blank. A URL is riskier than a place name: it
    is a claim that a page *exists*, and a near-namesake's profile sends a reviewer to the wrong
    company. So a recalled URL is not stored as written — it must parse as a real profile path on
    the right host and its slug must pass the same `_identity_forms` gate `_extract_links` applies
    to a searched result, and the canonical URL is rebuilt from that slug.

  Do not widen this to a third field, and note what both have in common: they fill a field that is
  *identifying* (where the company is, where its public profile lives), never one that is
  *evaluative*. Nothing that feeds a score may come from model memory.
- `core/score.py` — a self-asserted program membership scores at a discount to an independently
  corroborated one; a source URL alone is not evidence.

If a field cannot be evidenced, leave it empty and let the UI show "—".

## Architecture

| Path | Role |
|---|---|
| `core/` | The engine. Pure Python, no web framework, no `api/` imports. |
| `core/programs.py` | Siemens' published programme criteria + the SFS gate. Data and pure predicates; no I/O. |
| `api/` | FastAPI wrapper + SQLite persistence (`api/store.py`, S3-backed). |
| `ui/` | React 18 + Vite SPA (the product surface). |
| `tests/` | pytest, backend + engine. |
| `data/` | `glassdollar_applications.xlsx` (429 rows), `runs.db`. |

`core/` must never import `api/` — the engine runs standalone from scripts and tests. The web
result cache is injected the other way round: `api/main.py` calls `core.web.install_cache(...)`.

Pipeline: `core/pipeline.py::evaluate` → `enrich` → (verify ‖ summarize ‖ fit ‖ profile ‖ trend,
concurrent) → `score` → `route`.

## Data sources: GlassDollar first, the web for the rest

`core/glassdollar_api.py` is the live REST client (`GLASSDOLLAR_API_KEY`, base
`https://actions-api.glassdollar.com`). It is the **first** source everywhere: `_evaluate`
resolves a name through it, then a domain via `get_company_by_domain`, and only then falls back
to `data.web_profile_row`; `/api/search` lists its hits ahead of the local xlsx.

What it can and cannot answer decides how much scraping is left:

- **It answers** name, website, domain, HQ, founded year, headcount, total funding,
  LinkedIn/Crunchbase URLs, referenced customers, descriptions, tags.
- **It does not answer** business model, development stage (Siemens pitch-form fields it does not
  expose), founders, advisors, programs, parent group, headcount history, trend, verification,
  Siemens-tool fit, scoring or routing. Those still need the web pipeline.

`profile._seed_from_database` takes the three headline fields it does answer *before* the recall
nets run, so `_recover_headline_facts` — a whole search wave plus an extraction call, and the most
fragile part of the chain — skips itself. The database also **wins over** the main wave's
extraction, not merely over a blank. Two rules hold there: a researched `*_source` URL is dropped
when the two disagree (it evidences the value that lost), and the headcount never enters
`employees_over_time`, whose `_clean_employee_series` gate requires an `http` source per datapoint.

A GlassDollar value has no URL, so it is `source_type: private` in `core/provenance.py` — not
`public` (which would be demoted to `inferred` for lacking a URL) and not `self_reported` (the API
corroborates across sources rather than repeating the pitch form). The xlsx keeps `glassdollar_db`
/ `self_reported`, because that one *is* the application form.

The xlsx stays: it carries the pitch-form answers and decks the API does not expose, and it is the
only source when no key is set. **The key only resolves inside the Siemens network**, so nothing
about the live API can be verified from a laptop or CI — `tests/test_glassdollar_first.py` drives
the client contract with a fake and says so at the top.

## Two gates decide a pillar, and they answer different questions

`core/score.py` produces the six dimensions and three route scorecards; those say how **strong** a
startup is. `core/programs.py` holds Siemens' **published** Connect / Collaborate / Empower
criteria and says whether the programme would actually take it. A pillar has to clear both, and
the criteria layer can only ever remove a route the scorecards admitted — which is what keeps the
browser what-if (`ui/src/scoring/routing.js`) a sound answer to the question it asks. **Do not
mirror the criteria client-side**: they read evidence, not weights, so no reviewer weighting can
move them.

Routing also reports `portfolio_stance` — complementary / integrates / adjacent / **competes** —
as an outcome in its own right. A startup that substitutes a Siemens product used to be visible
only as a 0.55 multiplier on `siemens_fit`, which usually pushed it under the alignment gate, so a
scout read "Pass" and never learned the reason was a product Siemens already sells. That is the
most strategically interesting thing an evaluation can find and it was being expressed as a
slightly lower number.

`assess_pillar` returns three states, and collapsing them to two throws away the useful half:

- `blocked` — wrong programme, and no further evidence changes that. A product classified a
  `substitute` of a Siemens tool cannot be listed beside it as a Marketplace partner offering.
- `unproven` — nothing disqualifies it, but a requirement is unevidenced. `next_steps` names each.
- `eligible` — every required criterion met. Outranks `unproven` in the primary-pillar sort
  regardless of scorecard, so the headline never prefers a higher-scoring guess.

Empower's unconditional append in `route.py` is still there and still the reason a scorecard-only
run can never be `Pass`; the criteria gate is what makes `Pass` reachable again.

Two things hang off the pillars beyond the criteria, and both are derived rather than researched —
no extra search, no extra completion, so they cost nothing per run:

- `core/empower.py` turns evidence the run already holds into what a scout can act on today: which
  Xcelerator bundle to offer, the investment signals (stage, investors, headcount growth, top-tier
  programme, corroborated customers, market momentum) each carrying the source URL of the fact
  behind it, and templated approach angles. The angles are **templated, not generated** — a model
  asked for outreach ideas writes fluent suggestions naming a product the company does not make.
- `core/departments.py` ships an **empty** `DEPARTMENTS` registry. Collaborate is a venture-client
  programme, so the real question is which department would buy, and only Siemens can supply that.
  `assess_departments` reports `configured: False` and the UI says "not yet configured" — never an
  empty list of departments, which would read as every department having declined. Same rule as
  `employees_history_status` and the SFS `unassessed` state. Filling it in is data, not code.

**SFS is a lender, not a grant.** `assess_sfs` requires evidenced financeability — an asset the
startup sells or needs, contracted/recurring revenue, a project with an offtake, or Series A+
backing — and then names the product line (vendor finance / equipment & technology finance /
project finance / corporate lending). The rule that matters: **a startup's customers being
capital-intensive is not a reason to recommend SFS.** The old one-line judgement inside the
profile extraction prompt confused the two and returned true for all 18 stored runs, including two
pure software companies. Its fourth state, `unassessed`, is load-bearing — a run whose commercial
posture was never extracted knows nothing either way, and reporting that as "not relevant" is the
same mistake `employees_history_status` exists to prevent.

Everything in `core/profile.py` **transcribes** evidence; nothing there judges. Judgements live in
`core/programs.py`, over the `commercial` sub-profile (deployment, APIs, certifications, pricing,
hardware, revenue shape, funding stage, investors) that the profile stage evidences.

## Calibrate anything a model scores, and watch for dimensions going flat

Three scored quantities had independently collapsed to constants, and a green test suite could not
see any of them, because each individual score was arithmetically correct — only the distribution
across runs shows it. `scripts/dimension_variance.py` (advisory in `scripts/gates.sh`) is the
check; read its output rather than skipping past it.

Asked for a 0–100 confidence with no anchors, a model uses the top of the scale and nothing else:
the fit prompt returned 85–100 for all 54 matches it ever made, and trend momentum returned 90–92
for every niche. Both prompts now tie each band to an observable consequence and require the
answer to cite what it counted. **A model-produced number without a rubric is not a measurement.**

## Traction is a points rubric, not a judgement

`core/traction.py` scores the product owner's table — Funding 30 · Customers 30 · Revenue 30 ·
Employees 10, bands in `config.TRACTION_RUBRIC` — deterministically, from facts the run already
holds. It costs nothing per run, is recomputed for every stored run as it is read
(`with_traction`, called from `api/store.py` and `api/workspace.py`), and replaces the model's
holistic `dimensions.traction`; the model's number stays beside it as `traction_llm`, because the
gap between the two across the corpus is the calibration signal.

- **An unevidenced division is dropped, never scored zero**, and the rest are normalised over what
  remains. Confidence is the share of the 100 points that were evidenced (employees only → 10%),
  so a score normalised from one small division reads as thin rather than strong. A *sourced*
  "pre-revenue" is the opposite case: a real 0 that stays in the denominator.
- **The model supplies words, never numbers.** The one extraction call it rides
  (`_extract_commercial_posture`) returns a revenue *quote*, which must appear verbatim in the
  evidence, and Python parses the figure out of it (`text.parse_money`). A model asked for a
  revenue number rounds, converts and occasionally invents one.
- **Labelling a grounded customer "big name" is identifying, not evaluative** — the same kind of
  fact as a programme's prestige tier (`_grade_programs`). Whether a company is a customer at all
  stays with `_ground_customers`; the model may only label names already in that list, never add
  one, and `config.NOTABLE_COMPANIES` is the offline baseline it can upgrade but not overrule.
  This is not a third model-memory exception, and must not be widened into one.

- **The division panels look up more on request, and none of it scores.** `core/traction_lookup.py`
  (`POST /api/runs/{id}/lookup/funding|headcount`) fetches funding rounds with investor profiles, and
  sourced headcounts — the reviewer's Tracxn first, the model's own web search second, never its
  memory. The model only transcribes the gathered prose; a value is kept only if that prose states
  it, and a web row only if it cites a source the search used. The result is stored and served to
  the next reader (see "What a run produces is stored" below); it is never written into the run's
  `result_json`, so it cannot move a score.

## Siemens Fit is three pillar assessments, scored per department

`core/pillar_match.py` (model half) and `core/pillars.py` (pure half) score Empower against
`siemens_tools.csv`, Collaborate against the selected department's needs, and Connect against
`data/siemens_xcelerator_data.xlsx` — three criteria each, 0–3, against the product owner's
anchors. Siemens Fit is `round(100 × best assessed pillar total / 9)`; the route is decided from
the pillar bands by `recommend`, and no model can override it (`decision_research` runs only for
department-less engine calls).

- **The model proposes; `validate_match` decides.** Integer scores 0–3, citations that exist,
  catalog ids that were shortlisted, a positive score only with both, and the third criterion
  (actionability / ecosystem value) capped at 1 unless the pillar's statement names a matched entry
  and carries a next step. Thematic similarity alone cannot earn a route.
- **An Empower tool must exist before it is recommended.** `siemens_tools.csv` has carried names
  that are not Siemens products. `core/tool_check.py` runs one small web search per cited tool;
  `not_found` re-runs the match without it (`pillar_match._with_real_tools`, two rounds), and
  `unchecked` — no search available, or an unreadable answer — keeps the tool, because a failed
  search is not evidence of absence. Checks are cached only when conclusive, stored in
  `tool_checks`, and the `not_found` ones are the admin page's "could not be verified" list:
  fixing that list is a catalog edit, not code.
- **Tool shortlists are semantic + word search** (`core/tool_search.py`), for both the fit stage
  (80) and Empower (20). Word overlap alone showed Wandelbots a shortlist without Tecnomatix or
  Process Simulate but with a cybersecurity certification that shared the word "industrial". The
  catalog is embedded once into `data/tool_index/` (`scripts/build_tool_index.py`, ~30s; rerun
  after any change to `siemens_tools.csv`), the startup once per run, and the two rankings are
  fused by reciprocal rank over the top 20 of each (`FUSE_DEPTH`, measured by
  `scripts/compare_tool_retrieval.py`). The index is used only when catalog checksum, model and
  size all match; otherwise — or when the provider cannot embed — it is words alone and the pillar
  says so (`retrieval.method == "words"`). Gemini's `gemini-embedding-001` is verified; the Siemens
  gateway embeds only if `EMBEDDING_MODEL` names a model it serves, and the index must then be
  rebuilt with that model.
- **Empower ranks up to 5 tools** (`recommended_tools`), held to the criteria's bar by
  `pillars._recommended_tools` (shortlisted, relation, reason, a real citation) and existence-checked;
  one that cannot be found is dropped without a re-match. They never move the score. Fit also lists
  up to 5, but everything that decides from `fit.matches` reads the first one or three.
- **Connect asks whether the offering is already in the ecosystem** (rubric v2+). Its criteria are
  Ecosystem gap · Industry & topic fit · Ecosystem value. The gap is **derived, never scored by the
  model**: the Xcelerator sellers are embedded into `data/xcelerator_index/`
  (`scripts/build_tool_index.py --catalog xcelerator`, ~10s; rerun after any change to the
  workbook), the 10 nearest the startup's offering are fused with word overlap, the model labels
  each `equivalent | overlapping | distinct` in the Connect call it already makes, and
  `pillars.gap_level` counts only equivalents with **no cited differentiator** — a raw count
  punished a startup for working in a busy area even when it was evidently different. A skipped
  seller counts as overlapping, never as absent. Bands are `config.CONNECT_GAP_*`; tune them from
  `connect.ecosystem_gap` in `scripts/dimension_variance.py`, not by argument. A saturated offering
  (gap 0) tops out at 6/9 and can never be Strong. **Absence is a gap only where the ecosystem
  is**: with Industry & topic fit below 2 the gap is capped at 1 — an offering nobody sells because
  it is unrelated is distant, not new, and scoring that 3/3 lifted weak startups to Review.
- **Connect's Ecosystem value is derived too, on two paths** (rubric v3; the model now scores only
  Industry & topic fit, which at 2+ must cite both an industry and a topic). Its three signals:
  an ecosystem **audience** (sellers the model names as would use / integrate / resell / partner,
  each with a reason and a citation, never one it labelled equivalent — drawn from the nearest
  sellers or from `audience_candidates`, sellers in the startup's industries and topics), a clear
  **fit**, and a good **market** signal — a `market:` record `pillar_match.market_records` builds in
  Python from the trend stage's cited figures (`config.CONNECT_GOOD_MARKET`), so "good" is never
  the model's call. With an audience: 1, +1 for fit or market, +1 for both. Without one — open
  space — fit and market alone: 0, 1 or 2 (`pillars.value_level`). So an open-space startup that
  fits and has a strong market can still be Strong (3+3+2); one that does neither cannot.
  `pillars.connect_case` turns the same rows into the verdict the opportunity map's third step
  shows — "Connecting makes sense" / "Worth exploring" / "does not make sense", from the band —
  with each point for or against and its source: templated, never generated. The equivalent
  sellers are competitors: `catalogGroups` keeps them out of the "Ecosystem audience" node.
- **Collaborate ranks a department's needs by meaning** (`data/needs_index/`, all ~50 needs of the
  requirements workbook, `scripts/build_tool_index.py --catalog needs`; rerun after any change to
  it). Ranked once per evaluation in `prepare_pillars`, filtered per department. Not fused with
  words as tools are: needs have no product name to quote, and on Radical Dot words put "Defect
  Detection" above "Advanced Recycling". The top three are kept as `closest_needs`, which the map
  lists first when nothing matched; they never move the score.
- **Unassessed is not a no-match.** No grounded concept, no catalog, no model or output that fails
  validation → `unassessed`. Only assessed pillars feed Siemens Fit, and Pass needs all three.
- **A Collaborate at 0/9 is not a route.** When every department scores 0, `build_all` sets
  `recommended: null` with `basis: "no_collaborate_match"` (distinct from
  `no_collaborate_assessment`), and `pillars.siemens_fit` leaves a 0/9 Collaborate out, so the fit
  comes from Empower or Connect — or stays pending, never 0, if neither was assessed. It still
  counts as assessed for Pass. Both are re-derived on read, so stored runs follow the rule.
- **A run is one startup assessed for every department.** Nobody picks a department before
  searching — that asked the reviewer to guess what the evaluation exists to find. Research,
  Empower and Connect are department-independent and run once; Collaborate is matched against each
  department's needs in parallel (`pillar_match.for_department`), and `assessment.build_all` heads
  the run with the department whose needs it answers best (`departments.recommended`; null, never
  a default, when no Collaborate could be assessed or every department scored 0/9). The run's own `department` / `assessment` are
  the recommended one's, so single-department readers keep working; `departments.ranked` holds every
  department's full assessment, hydrated on read, and the Scoring tab switches between them with
  `?dept=` and no call. Stored under `runs.department_id = '*'`, with `assessment_key` covering the
  rubric, the shared catalogs and EVERY department's needs — one department's needs changing makes
  the run stale. Fresh research from an older run is re-assessed (`pipeline.assess_departments`)
  and always saved as a new run. One-department runs and runs with no department are history,
  readable and never rewritten.
- **Collaborate reads Siemens' stated needs** from `data/Startup_Evaluator_Departmental_Requirements.xlsx`
  (`core/department_needs.py`): one catalog entry per capability, with its category, description and
  keywords; the 15 sharing most concepts with the startup go to the model when a department states
  more. Such a department is `source: workbook`, not demo. Without the file, departments fall back
  to five example keywords and Collaborate is **provisional** — scored, included, labelled so. An
  admin's `PUT /api/departments/{id}` overrides either. Any change to the needs changes the checksum.

`core/assessment.py` computes `total = 0.30 traction + 0.35 Siemens Fit + 0.20 (Team & Ecosystem
points × 5) + 0.15 market` on every read (`hydrate`); any missing component leaves it pending, never
0. The model's holistic `final_score` and `siemens_fit` are kept as `llm_final_score` /
`llm_siemens_fit` and shown only as diagnostics.

**Market** (`core/market.py`, 15%) is three criteria 0–5: size and growth are banded in Python from
the figure the trend stage cited (`trend.landscape.market_size`, EUR bands; CAGR bands), and only
without a cited figure may the model judge them — capped at 2. Strategic relevance is the model's,
and 4+ must name a Siemens Xcelerator industry or topic. `market_score = points ÷ 15 × 100` replaces
the model's holistic market number in the total (kept as `llm_market`); a department run from
before the rubric keeps the model's number and says so (`market_method`).

## The market landscape rides in the trend stage's own wave

`core/trend.py` stage 1 has always asked the model for competitor and funding queries, and stage 3
threw everything except the prose away. `_market_landscape` now extracts named competitors, funded
peers, market size and active investors from the same results.

Its five queries go into the **same** `_ddg_many` call as the trend queries, because `_ddg_many`
caps concurrency at 10 — so ten queries are one round trip and the landscape adds no search time.
The extraction runs concurrently with the momentum call, both under `copy_context()`.

Both calls read the **same** evidence, and that is deliberate: they used to read different slices,
which produced a page contradicting itself — "no CAGR figures are cited" as the stated basis for a
momentum score, directly above a cited CAGR of 31.7%.

Grounding is the same bar as everywhere else, and both halves matter: every entry needs a real
`http` source, **and** its name has to appear in the evidence text. A model asked for competitors
in a niche will list the ones it remembers rather than the ones in the results, and a fabricated
competitor beside a link is indistinguishable from a real one. The startup is also filtered out of
its own landscape in code — Celonis came back at the top of its own process-mining competitor list,
because in results about a company's own niche that company genuinely is the most prominent name.

`landscape` absent and `landscape` present-but-empty are different statements, and the UI renders
them differently: "not researched on this run" versus "the search named no competitor".

## A profile appears before its verdict

`pipeline.evaluate` takes `on_partial(section, data)` alongside `on_step`, and
`POST /api/evaluate/stream` delivers those over SSE. The returned result is unchanged and still
complete — `tests/test_evaluate_stream.py` pins that a streamed run is byte-identical to a plain
one, which is the property that matters. Two code paths producing two answers for one company
would be far worse than a slow page.

The five concurrent branches are collected with `as_completed`, not in a written order: they differ
by tens of seconds, and a summary that finished in three seconds used to sit unread until the
slowest branch returned.

**The header profile is emitted twice, and that is the whole feature.** Measured on a real run, the
deep-profile branch returned at 112s of 118s — a page waiting for it waits for the entire
evaluation. So `_header_profile(row, {}, source)` goes out as soon as enrichment finishes and the
researched version replaces it later. This is only safe because `backfill_profile` fills BLANK
fields and never overwrites: the later version adds values, it never changes one on screen.

Anything a streaming run has not produced yet must say so rather than render its empty state. A
pillar pill with no pillar reads as a verdict of nothing; a Fit Score of 0 reads as a bad company.
Both are the `employees_history_status` mistake one level up.

`EventSource` is not usable here — it is GET-only and this must be a POST carrying the session
cookie and CSRF header — so the client is `fetch` plus a stream reader, falling back to
`api.evaluate` on any stream failure.

## Measuring a scoring change instead of arguing about it

`py -3 -m benchmarks.routing_eval` replays the **current** engine over every stored run and scores
the result against human labels in `benchmarks/labels.json`. `benchmarks/replay.py` rebuilds the
inputs from `result_json` and re-runs `score_startup` / `route` — no network, no model, no cost —
so a change to the decision layer is measurable across the whole history in a second.

What is deliberately *not* replayed: enrichment, extraction, fit and trend. Those are the model's
reading of the web at the time, and re-running them would move the inputs under the experiment.

**The labels are the gap, and only a reviewer can close it.** `--seed` adds an unlabelled row per
company; the report leads with coverage and refuses to compute anything until a `pillar` is filled
in, because a precision of 1.00 over three labels is not a result. Once ~30 are labelled, swap the
advisory line in `scripts/gates.sh` for `--min-f1 <floor>` and make a routing regression fail.

## A refresh adds evidence; it never quietly drops it

Every run is a fresh sample of the web, and the newest used to replace everything shown — Radical
Dot's investors went 8 → 3 → 0 → 2 → 6 across refreshes. `core/carry_forward.py` folds every stored
run of the company (`store.prior_runs_for`, oldest first) into the fresh one as each branch lands,
**before** anything is scored or emitted:

- Lists (people, programmes, investors, competitors, headcount points) are a union. An item only an
  earlier run found keeps its own `source_url` and gains `last_confirmed_at`; the UI shows "last
  confirmed {date}" (`ConfirmedTag.jsx`). Carried items must still name an http source — older runs
  made under weaker gates must not resurrect what today's gates would drop.
- Single values: a blank or unsourced fresh value never replaces a sourced prior; between two
  sourced values the newer wins and the loser goes to `deep_profile.history`. GlassDollar facts count
  as sourced (their `source_url` is "GlassDollar", not a URL). A web value beats an `*_origin="llm"` recall.
- Values that carry their own source are carried the same way: `customer_segment_grade` (it scores
  traction's Customers division when no customer is named — missing it flipped Radical Dot's
  Customers between evidenced and unknown across refreshes), `commercial.revenue`, certifications.
- Named reference customers have no URL of their own; one is carried only when an earlier run's
  verification claim sourced it and did not contradict it, with that source in
  `deep_profile.customer_evidence` (traction reads it) and its label in `customer_classes`.
- Market size / CAGR older than 18 months is dropped, fresh or carried; a year-only `as_of` is read
  as 31 December.
- The Team & Ecosystem panel lists every entity of a cited kind on record, cited ones first and
  marked. Showing only the model's citations made carried investors look lost: it cited a
  different two of fifteen each run.
- Identity first: priors are used only when their own domain matches (a directory page recorded as
  the website does not count as the company's domain), or, without one, the full normalised name.

It transcribes and never judges, like `core/profile.py`. Model outputs are recomputed over the
merged evidence. Stored runs are never rewritten.

## Evidence age is about the evidence, not the run

`Fact.retrieved_at` records when a search actually ran. For a result replayed from `web_cache` that
is the *original* search's timestamp, not this run's — `install_cache`'s optional `entry_getter`
is what carries it through, and `_ddg_many`'s `stats["cached_at"]` is what maps it back per query.
A re-evaluation can be reasoning over week-old results and now says so.

`freshness_days` is a live property and is **not serialised**. It used to be, as a stored constant
zero: every Fact is built during the run that gathers it, so its age is always 0 at write time, and
it then sat frozen in `result_json` while the run aged. Nothing read it, which is the only reason
nobody noticed. Age belongs to whoever is reading, against their own clock — the Evidence tab
computes it from `retrieved_at`.

One more of the same family, and the most expensive: `siemens_fit` blended
`0.3 × challenge_match` whenever the approved-challenge library was non-empty. With one unrelated
approved challenge recorded, that taxed every startup ~30% of its tool fit and accounted for
**all eight** `Pass` verdicts in the corpus. A demand-side match is now a bonus that can only
raise fit. `tests/test_siemens_fit_scoring.py` pins it.

## The assistant: the evaluation first, Tracxn second, the model's own web search third

`POST /api/ask` → `core/chat.py::chat_assistant`. With a run in focus, `run_brief` turns what the
evaluation already researched into ≤ ~700 tokens of numbered facts (`R1…`), each with its source —
profile, scores, pillars, market, competitors, claim checks, then founders/investors/programmes —
and one **non-thinking** call answers from them, citing `[R#]` (renumbered to `[1]…`, the same
scheme as a web answer, so the dock links both alike). Measured on Radical Dot's four suggestion
chips, two were answered there with no search at all. Python, not the prompt, decides what falls
through: an answer citing no fact, or one that says `Not covered:`, goes to search, and a
`SEARCH: <query>` reply hands the search a sharper query (always naming the company — without
it "top risks" came back as generic industry risks). The search then gets only the headline
facts, not the whole brief, and a capped thinking budget (`CHAT_SEARCH_THINKING`, 512): a
grounded Gemini answer spent up to ~3,900 thinking tokens otherwise. History is the last four
turns, assistant turns cut to 400 chars. Answers follow one shape (`_CHAT_STYLES`): a sentence
that answers, cited bullets, a table only for comparisons, a `Not covered:` line — rendered by
`ui/src/components/AnswerText.jsx`, never as HTML. A grounded answer the model writes twice is
cut to its first copy (`llm._drop_repeat`).

With the reviewer's Tracxn account connected,
`TracxnClient.research` plans up to three calls over the MCP server's **read-only** tools (schemas
discovered, arguments validated against them, anything named for a write refused) and the answer
is written from that data only. Without a connection — or when Tracxn fails or has nothing — the
model searches the web itself (`LLMClient.web_answer`: Google Search grounding on Gemini, the
Responses API `web_search` tool on the gateway) and cites what it used. **No DuckDuckGo here**:
`tests/test_assistant.py` fails if the path touches it. A provider that cannot search answers from
memory labelled *unverified* — never under a web label. The gateway's `web_search` support cannot
be checked from outside the Siemens network; if it is missing, answers degrade to that label.

## What a run produces is stored, and served before it is searched again

`result_json` stays the record of a run; `api/store.py` also writes what it holds row by row, and
what is fetched *after* a run (on request) goes in too — Tracxn or web alike, the product owner
confirmed storing Tracxn data is permitted.

- `save_run` → `_replace_children`: people, programmes, customers, evidence facts, tool matches,
  the evaluation's own investors (`provider='research'`), every scored criterion
  (`assessment_criteria`: pillars, Team & Ecosystem, market — per-run history) and the Empower
  `tool_checks`. `backfill_assessment_records` fills these once for runs saved before the tables
  existed; it skips any run that already has criteria rows, so a restart never doubles history.
- `save_enrichment(company, kind, payload)` → `enrichments` (raw history, every fetch) plus the
  normalised table for its kind: `funding_rounds` + `investors`, `headcounts`, `market_signals`.
  The lookup and business-flow endpoints read `latest_enrichment` first and search only on
  `refresh`; the UI says "Saved {date}" on a stored copy. `business_flow` is per run (it is written
  from that run's research); the rest are per company.
- **A partial result is not stored.** A signals search with a failed domain, or a lookup that fell
  through to the model's memory, is shown but not saved — otherwise the gap would be served as the
  answer until someone thought to refresh.

## Telemetry (SigNoz / OpenTelemetry)

`api/telemetry.py` exports traces, metrics and logs over OTLP, and is **off unless
`OTEL_EXPORTER_OTLP_ENDPOINT` is set** (`tests/conftest.py` blanks it, so pytest never exports).
`core/` uses only `opentelemetry-api` — spans are no-ops without the SDK — so the engine still runs
standalone. Each pipeline branch runs inside its own span (`pipeline._submit`), and every DuckDuckGo
search gets a `web.search` span, because ddgs' own HTTP client is invisible to instrumentation.

Kept out of telemetry on purpose: the `/api/auth/callback` URL (it carries the Entra code), Redis
(its keys are session ids), and prompt/completion text. Adding a root log handler silences Python's
last-resort stderr output, which is why `attach_log_handler` adds a WARNING console handler first.

Local SigNoz runs self-hosted through Foundry inside WSL2 Ubuntu; UI on :8080, OTLP on :4318.

## Authentication

Sign-in is Microsoft Entra ID, as a **backend-for-frontend**: `api/auth.py` is the confidential
client, does the code exchange, and keeps every token server-side. The browser gets an opaque
session id in an httpOnly cookie and never sees a token — which is what lets `ui/src/api.js` keep
its "no tokens in the browser bundle" stance. Sessions live in Redis (db 1), not in a signed cookie
(that would put the payload in the browser) and not in SQLite (`api/store.py` uploads the whole DB
file to S3 after every write).

Entra is behind a Conditional Access policy requiring a compliant device on a trusted location, so
**no CI runner can ever complete a real sign-in.** `AUTH_MODE=stub` replaces only the round trip to
Entra; cookies, CSRF, the session store and the guard are all production code. It is sealed twice —
`APP_ENV=production` (baked into the `Dockerfile`) and a gunicorn check — and the process exits
rather than starting with auth stubbed. Do not add a third mode, and do not add a "not configured,
so allow" branch anywhere: fail-closed is the point.

The guard lives in `SecurityMiddleware.dispatch()`, so **a new `/api` route is protected by
default** and has to be named in `PUBLIC_PATHS` to opt out. Identity reaches a route via
`Depends(current_user)`, and admin-only routes via its sibling `Depends(require_admin)`.

`overrides.reviewer` used to be free text a client chose. It is now the authenticated principal,
alongside `reviewer_oid/upn/tid/source`. Those are **NULL on pre-SSO rows and are never backfilled**
— promoting unverified history to verified is the one thing an audit trail must not do.

## Per-reviewer workspaces, one shared evaluation

The split that everything in `api/store.py` below `web_cache` exists for: **an evaluation is
shared, the record of who asked for it is private.**

- `searches` — one row per `/api/evaluate`, keyed on the Entra `oid`, with `served_from`
  (`cache` | `fresh`). This is both the reviewer's list (`GET /api/my/searches`, what Explore,
  Home and Tracking read) and the admin activity log.
- `company_aliases` — every string a company can be reached by: the typed query, the resolved
  name, the domain. Without it the cache-first lookup in `/api/evaluate` misses its own writes,
  because it searches on what was typed while `save_run` files the run under what the pipeline
  resolved. `save_run(result, aliases=[...])` records them; `latest_run_for_alias` reads them and
  falls back to the exact-name match for pre-alias rows.
- `sessions` — one row per sign-in, written from `create_session`. Redis holds only *live*
  sessions, so it can say who is online but never how many sessions there have been.
- `saved_views` — grid views keyed on the `oid`; they used to be `localStorage` and so belonged
  to a browser rather than a person.

Lists are strictly private: no parameter widens `/api/my/searches` to another principal. The
team-wide view is `/api/runs` and `/api/admin/*`, behind `require_admin`, which reads `ADMIN_UPNS`
(comma-separated). **Unset means nobody is an admin, never everybody** — same fail-closed rule as
the rest of `api/auth.py`.

## Running it

```bash
AUTH_MODE=stub SESSION_BACKEND=memory ADMIN_UPNS=e2e.reviewer@siemens.com \
  py -3 -m uvicorn api.main:app --port 8000    # backend (single process — see below)
cd ui && npm run dev                           # frontend on :5173
py -3 -m pytest tests/ -q                      # backend tests
bash scripts/gates.sh                          # ALL gates (run before finishing any change)
```

`ADMIN_UPNS` is what makes `/admin` reachable in dev — `e2e.reviewer@siemens.com` is the stub
principal's UPN. Leave it unset to exercise the forbidden path.

The e2e suite needs the backend in stub mode, and in **one** process: `SESSION_BACKEND=memory`
splits across gunicorn workers, so a request landing on the other worker looks signed out.

The backend serves the API only — `/` returns 404 by design. The UI is `:5173` in dev.

`.env` at the repo root holds `GEMINI_API_KEY` and, in the Siemens environment,
`GLASSDOLLAR_API_KEY` (both gitignored). Without either the engine degrades — keyword-only
extraction, xlsx + web instead of the live database — rather than failing.

## Frontend map

Routes (`ui/src/App.jsx`): `/` Home, a bare search landing that evaluates whatever you type ·
`/workspace` the scouting workspace, labelled **Explore** in the rail (the file is still
`pages/Home.jsx`) · `/explore` the companies grid, labelled **Databases** (route deliberately
unchanged so saved-view links keep resolving) · `/startup/:id` Profile · `/saved` · `/alerts` ·
`/ask` · `/settings` · `/admin` (rail entry hidden unless `/api/auth/me` reports `is_admin`; the
page itself explains a 403 rather than 404ing, so a shared link is diagnosable). API client:
`ui/src/api.js`. Shared state: `ui/src/state.jsx`.

The Profile is **one scrolling page with a section rail**, not a tab set: Profile → Scoring & Fit →
Market & Risk → Evidence, each anchored and scroll-spied (`SECTIONS` / `useScrollSpy` in
`Profile.jsx`). A rail entry is rendered only when its anchor exists (`present`), so no destination
scrolls nowhere.

Icons are Siemens iX, via `ui/src/components/Icon.jsx`. It inlines the SVG and repaints it in
`currentColor` because the shipped glyphs carry `fill='none'` and expect the host to paint them —
an `<img>` or a CSS mask renders them blank. Do not reintroduce Unicode or emoji glyphs in chrome.

The six weight sliders (`ui/src/components/WeightSliders.jsx`) and the single
`se.whatIfWeights.v1` behind them are shared by the profile what-if and Explore's portfolio
re-weighting on purpose: "my weighting" is something a reviewer has, not a per-screen setting.

`ui/src/tokens.css` is the **single source of truth for design tokens** — chrome (product shell),
canvas (data surface), text, semantic, pillar ramp, type scale. Components reference tokens, never
raw colours. `docs/ui-inventory.json` is generated from source by `scripts/ui_inventory.py`; read
it instead of recalling the component list from memory.

## Design contract: Siemens iX owns styling and information architecture

Siemens iX (`@siemens/ix`) is now authoritative for both styling **and** information architecture.
The Tracxn-modelled shell — icon rail, top command bar, collapsible secondary side-nav, dense data
canvas — is being retired in favour of iX's own shell and layout primitives. Where an old Tracxn
rule had a purpose, here is what replaces it, not just what's deleted:

- **App shell.** The fixed icon rail + top bar + conditional side-nav stack (`App.jsx`) is replaced
  by iX's own shell composition (`IxApplication` as the single root, holding the application header,
  application menu and content components as children rather than hand-rolled fixed-position
  siblings — see `docs/ix/guidance.md`). The exact shell composition is a Phase 3 decision; this
  entry records the authority, not the final component list.
- **Command bar.** The Ctrl/Cmd-K global search-and-slash-command palette has no iX equivalent and
  needs a fresh IA decision in Phase 3 rather than a re-skin.
- **Dense data tables.** iX ships no `IxTable`/`IxBasicTable` (verify any component name against
  `docs/ix/components.md` before it enters a design) — Explore's sticky-column, customisable,
  URL-state-persisted grid needs an explicit Phase 3 decision on what iX primitive(s) it's rebuilt
  from.
- **Pillar colour ramp.** The hand-derived four-way Connect/Collaborate/Empower/Pass ramp has no
  anchor in iX's palette; Phase 3 decides whether it stays a hand-derived app-level overlay or is
  redrawn onto an iX-supported scale.
- **Dark chrome over a light canvas.** iX has no "dark chrome, light workspace" construct. This
  seam either gets an iX-sanctioned equivalent or an explicit, documented exception in Phase 3 —
  it does not survive by default just because it existed before.

Rules that are mechanically enforced by `scripts/ix_lint.mjs`, not left to judgement: no raw
hex/rgb outside `tokens.css`; interactive elements need accessible names; every data view needs
visible loading, empty and error states.

## Frontend source-file rules

- Target <= 300 lines per hand-written source file; 400 is the hard ceiling.
- Split by coherent responsibility, never by line count. Do not manufacture wrapper components to
  get under the limit — a 40-line component that only forwards props is worse than a long file.
- `styles.css` and `tokens.css` are exempt: they are the app's single stylesheet and its token
  source, and slicing them per-component would invent an architecture nothing else follows.
- Prefer existing components, utilities and tokens. Do not add a dependency for something a
  browser API does cleanly (the Overview's scroll-spy is ~140 lines of IntersectionObserver).
- Keep configuration in one place. `ui/src/pages/profile/sections.js` is the only list of the
  Overview's sections; the rail, the scroll-spy and the tests all read it.
- Clean up observers, subscriptions and listeners. Every one of them has a disconnect test.
- Run `bash scripts/gates.sh` before finishing. Do not reformat unrelated code.

## The profile reads top to bottom, and that is load-bearing

Every view under `ui/src/pages/profile/` is a single column of `<section>`s, with the rail beside
it (`ProfileSectionNav` + `useScrollSpy` + `ProfileLayout`), modelled on Tracxn's profile
navigation.

They used to be two-column `grid2`s. **Do not put them back.** A table of contents needs a reading
order, and in two columns "Team & ecosystem" sits beside "Executive summary" at the same scroll
position — there is no single current section to mark and the indicator flickers between the pair.

**The rail is the page's only navigation.** A pipeline ribbon (`Input › Enrich › … › Route`) and a
tab bar used to stack above it. The ribbon rendered all seven steps as done on every finished run,
so it reported nothing a reader could act on while costing ~70px of sticky chrome; two navigation
systems for one page was the other half of the problem. The Ask tab went with them — the ✦
Assistant button opens the same conversation in the dock, from any view.

Consequences worth knowing before changing any of it:

- `ui/src/pages/profile/sections.js` is the **only** list of views and sections. A view's `id` is
  also its `?tab=` value, deliberately unchanged from the old tab labels so permalinks a reviewer
  already shared still resolve.
- Exactly one rail group is open, and the open group **is** the rendered view. Rail state and
  `?tab=` are the same fact; do not add a second source of truth.
- A group header is a disclosure (`aria-expanded` + `aria-controls`), not a tab — a tablist's
  children must be tabs, and these own a list. Sections are real anchors.
- The rail must never be `display: none`. It was hidden below 1000px back when the tab bar carried
  navigation there; now that would leave a phone with no way to reach Scoring & Fit at all. Below
  1000px it becomes a full-width block above the content — same markup, same state.
- `Section` takes its accessible name from the registry. Six unnamed `<section>`s in a row are read
  out as "region, region, region".

Three numbers have to stay in step, and there is one source for each:

- `--profile-sticky-h` is *measured at runtime* by `useStickyOffset`, because `.profile-head` is
  itself sticky and its height depends on how long the company's summary is. On a real profile it
  is ~408px, which is why the scroll-spy's activation band is a fraction of the space *below* the
  chrome and not of the viewport: a percentage of the viewport produced a negative root rect and
  the observer silently stopped firing.
- `.profile-section { scroll-margin-top }` puts a clicked section a few pixels below that line;
  `CROSS_TOLERANCE_PX` in `useScrollSpy.js` must cover that gap, or a section scrolled to by a
  click counts as not yet reached and the marker snaps back to its neighbour.
- The active rule is "the last section whose top has crossed the line" — the same in both scroll
  directions. Not "first intersecting entry" (IntersectionObserver's entry order is unspecified)
  and not "most visible" (that tracks panel height, so a two-chip panel can never win).

## Testing

Three layers, and they are not interchangeable:

- `tests/` — pytest for engine and API behaviour.
- `ui/src/**/*.test.jsx` — Vitest + Testing Library. Render the component and assert **behaviour**.
- `ui/e2e/` — Playwright journeys + visual regression at four breakpoints.

**Never assert on source text.** Tests of the form `assert "sticky-header" in open(file).read()`
were generated by a previous agent system; they verify nothing, are satisfied by pasting a string,
and all of them rotted into permanent failures. They have been replaced. Do not reintroduce the
pattern.

Visual baselines in `ui/e2e/__screenshots__/` are the record of "the layout still works". Agents
can update them.
## Conventions

- Comments explain **why**, especially where the code looks odd on purpose (the grounding gates
  above are all non-obvious and all deliberate). Do not add narration of what the next line does.
- Prefer editing existing modules over adding new ones; the engine is deliberately small.
- One concern per commit.
