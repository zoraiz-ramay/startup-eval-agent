# Where every number comes from

A map of the evaluation pipeline: which source answers which field, where the language model is
involved, where it is deliberately kept out, and how the six dimensions become a pillar.

Every claim below cites `file:line` so you can check it rather than trust it. Line numbers move;
the function names do not.

---

## 1. The shape of a run

`core/pipeline.py::evaluate` is the whole thing. Six stages, one of which fans out:

```
INPUT ──> ENRICH ──┬─> VERIFY     ─┐
                   ├─> SUMMARIZE   │
                   ├─> FIT         ├──> SCORE ──> ROUTE
                   ├─> PROFILE     │
                   └─> TREND      ─┘
                   (concurrent, 5 threads)
```

The five middle stages are independent, so they run together in a `ThreadPoolExecutor`
(`pipeline.py:166-189`). Each is submitted through `contextvars.copy_context().run`
(`pipeline.py:171-172`) — a detail worth knowing, because pool threads start with an *empty*
context. Submitted plainly, they would lose the cache-bypass flag that `evaluate` sets
(`pipeline.py:90`) and a forced "Re-evaluate" would quietly replay week-old cached searches for
the profile and trend research, which is most of the run.

The return value (`pipeline.py:220-235`) is what gets stored and what the UI renders: `profile`,
`profile_sources`, `summary`, `facts`, `verification`, `fit`, `score`, `routing`, `trend`,
`deep_profile`.

---

## 2. Identity: which company is this?

Three attempts, in order, and the order is the point (`pipeline.py:110-155`):

| # | Attempt | Where | Notes |
|---|---|---|---|
| 1 | GlassDollar name search | `glassdollar_api.search_as_df` → `find_startup` | Fuzzy; needs ≥ 0.82 similarity (`data.py:82`) |
| 2 | GlassDollar by domain | `pipeline._by_domain` (`:63-79`) | Tried *before* the web |
| 3 | Live web reconstruction | `data.web_profile_row` (`:85`) | Sets `source = "web"` and forces `do_web = True` |

**Why domain beats name.** A domain is a stronger identity than a fuzzy name match: `phena.tech`
resolves to exactly one company, while `Phena` competes with FENA Holdings and Phenna Group
(`pipeline.py:122-125`). So a reviewer who pastes a URL gets the database record rather than a
scraped reconstruction of it.

If step 1 or 2 hits, the row is **hydrated** with the full company record
(`pipeline.py:141-154`): the paginated list endpoint returns lighter objects than
`/v1/companies/{id}`, so a second call fills in `referenced_customers`, `long_description` and the
rest. Existing non-empty values win over the detailed row.

If all three miss, the run returns `{"found": false}` (`pipeline.py:133-135`).

---

## 3. Does the LLM write the web searches?

**Partly — and the split is not obvious.** This is the question the codebase answers in three
different places, so all three are here.

| Stage | LLM writes queries? | Where |
|---|---|---|
| `enrich` | **No** | `enrich.py:65-78` |
| `profile` | **Yes, up to 2 extra** | `profile.py:167-177` |
| `trend` | **Yes**, stage 1 derives keywords | `trend.py:49-60` |
| `web_profile_row` | **No** | `data.py:92-98` |

### enrich — fixed templates, no model

Ten or eleven queries, built by string formatting from the company name, domain and country
(`enrich.py:65-78`):

```python
"funding_web":    f"{company} funding round amount raised investors"
"founders_web":   f"{company} founders team background"
"customers_web":  f"{company} customers clients case study"
...
```

Plus one `f"{company} {customer}"` query per claimed reference customer (`enrich.py:84`). The
whole set goes out as **one concurrent wave** under a single deadline (`enrich.py:88`), so
enrichment and customer verification finish together.

### profile — model-suggested, but capped and grounded

`profile._queries` (`:142`) starts from eleven fixed queries, then, if a model is available, asks
for up to four more and **keeps at most two** (`profile.py:167-177`). The cap is not cosmetic: an
oversized wave triggers DuckDuckGo throttling, which returns *silently empty* results for the
program and advisor queries rather than an error (`profile.py:144-145`, `:175-176`).

Note what the prompt does *not* do: it suggests search queries, not facts. Whatever comes back
still has to survive the grounding gates in §6.

### Partial results are recorded, not hidden

`_ddg_many` takes a hard `overall_timeout` of 40s (`web.py:109-110`) and reports how much of the
wave came back (`enrich.py:88-91`). This matters because a throttled query is indistinguishable
downstream from "the web knows nothing" — without the count, a partial run looks identical to a
genuinely thin company, and two runs of the same startup silently disagree. When queries are
dropped, the engine string says so (`pipeline.py:216-218`).

---

## 4. Field-by-field provenance

`profile_cols` (`pipeline.py:199-202`) is the set of fields that reach the profile header.

| Field | First source | Backfill | Blank when |
|---|---|---|---|
| `company_name` | GlassDollar | — | never (falls back to the typed query, `pipeline.py:224`) |
| `website` / `domain` | GlassDollar | web row | no database record and no search hit |
| `hq` | GlassDollar | — | not in the database |
| `founded_year` | GlassDollar | **yes** — `deep_profile.founded_year` | neither database nor web established it |
| `funding` | GlassDollar | **yes** — `deep_profile.funding` | as above |
| `employees_count` | GlassDollar | **yes** — `deep_profile.employees` | as above |
| `linkedin_url`, `crunchbase_url` | GlassDollar | — | not in the database |
| `customers` / `Reference customers` | GlassDollar | — | not in the database |
| `Business model`, `Development stage` | xlsx pitch form only | — | the REST API does not expose them |
| Founders, advisors, programs, parent group | web research (`profile.py`) | — | nothing survived grounding |

### The backfill rule

`backfill_profile` (`pipeline.py:30-51`) fills **only blank fields** — wherever the database has a
value it stays authoritative — and records every filled field in `profile_sources` so the UI can
mark it web-sourced rather than passing it off as application data.

This exists because researched values previously lived only as evidence `Fact`s: visible in the
Evidence tab but never in the profile header, so the UI showed "—" for facts the run had actually
established (`pipeline.py:33-38`).

### The database wins over the researched value

`profile._seed_from_database` (`:566`) takes the three headline fields GlassDollar does answer
*before* the recall nets run, so `_recover_headline_facts` — a whole search wave plus an extraction
call — skips itself. Two consequences worth knowing:

- when the database and the research disagree, a researched `*_source` URL is **dropped**, because
  it evidences the value that lost;
- the database headcount never enters `employees_over_time`, whose gate requires an `http` source
  per datapoint.

---

## 5. Evidence: the `Fact` model

Every piece of evidence is a `Fact` (`core/provenance.py:33`) carrying `key`, `value`,
`source_url`, `method`, `confidence`, `verified`, `retrieved_at` and `source_type`.

`source_type` is derived from `method`, not set by hand (`provenance.py:13-25`):

| `method` | `source_type` | Meaning |
|---|---|---|
| `glassdollar_db` | `self_reported` | The xlsx — the startup's own application form |
| `glassdollar_api` | `private` | Curated third-party database, no linkable URL |
| `pitch_pdf` | `self_reported` | The startup's own deck |
| `ddg_search` | `public` | Found on the open web |
| `profile_research` | `public` | As above |
| `derived` | `inferred` | Computed, no direct source |

Two deliberate subtleties:

1. **A `public` claim with no URL is demoted to `inferred`** (`provenance.py:48-49`). If you cannot
   open it, it is not public evidence.
2. **The REST API is `private`, not `public` or `self_reported`** (`provenance.py:16-21`).
   Not `public`, because it has no URL and would be demoted by the rule above. Not
   `self_reported`, because GlassDollar corroborates across LinkedIn/Crunchbase/PitchBook rather
   than taking the pitch form at its word. The xlsx keeps `self_reported` — that one *is* the
   application form.

---

## 6. The grounding gates

The product's one rule is that every displayed fact must be traceable to a source. These are the
places that enforce it, and they all look over-strict on purpose.

| Gate | Where | Refuses |
|---|---|---|
| `_program_grounded` | `profile.py:208` | A program membership unless the program name and the company name co-occur in a **single** search result |
| `_ground_customers` | `profile.py:451` | A customer unless a relationship phrase appears in a short window near the name |
| `_clean_employee_series` | `profile.py:847` | Any headcount datapoint without an `http` source |
| `_clean_source_url` | `profile.py:115` | A "source" that is not a URL |
| `web_profile_row` | `data.py:85` | Filling funding, founded year, employees, HQ or customers from model memory |

That last one has a history: it used to fill those fields from what the model remembered, and
produced a funding round of "SAR 3.75 million" for makkook.ai that exists nowhere on the web. The
only remaining model-memory path is `_knowledge_profile_row` (`data.py:216`, reached at `:106`), reached solely
when DuckDuckGo returns *nothing at all*, and its output is marked unverified.

If a field cannot be evidenced it stays empty and the UI shows "—".

---

## 7. Scoring

`core/score.py::score_startup` produces six dimensions on 0-100, then combines them.

### The weights

`WEIGHTS` (`config.py:19-26`), summing to 1.00:

| Dimension | Weight |
|---|---|
| traction | 0.28 |
| siemens_fit | 0.27 |
| product | 0.15 |
| market | 0.12 |
| founder | 0.10 |
| ecosystem | 0.08 |

### From dimensions to the stored score

```python
raw          = Σ dims[k] × WEIGHTS[k]                       # score.py:121
completeness = (# of 8 key fields present) / 8              # score.py:125
confidence   = 0.5 + 0.5 × completeness                     # score.py:126
final        = raw × confidence                             # score.py:127
if completeness < 0.5: final = min(final, THIN_PROFILE_CAP) # score.py:128-129
```

So a sparse profile cannot score well no matter how good its dimensions look: confidence multiplies
everything, and below half-complete the result is capped at 75 (`config.py:27`). The eight key
fields are `company_name`, `hq`, `founded_year`, `employees_count`, `funding`, `customers`,
`linkedin_url`, `Your pitch` (`score.py:123-124`).

### Anti-gaming on traction

Reference customers are weighted by verification status, not counted
(`score.py:31`): `verified` 1.0, `partial` 0.5, `unverified` 0.25, **`contradicted` 0.0**.

### Programs are discounted when self-asserted

An evidenced membership earns its full prestige tier (`tier1` 16 pts, `tier2` 11, `tier3` 6,
capped at 36). A membership evidenced *only* by the company's own site earns half, under its own
lower cap of 18 (`config.py:39-46`, applied at `score.py:113-115`).

Neither treating them as equal nor discarding them is right: a startup can put any logo on its
`/partners` page, but NVIDIA Inception and Microsoft for Startups publish no searchable member
directory, so a genuine membership there is frequently impossible to corroborate.

### Missing evidence is not a red flag

Kept strictly separate (`score.py:141` and `:144`): `missing_evidence` is absence of data,
`red_flags` is negative evidence. "We don't know" must never read as "it's bad".

### Route scorecards

The same dimensions, re-weighted three times (`score.py:11-20`, computed at `:134-137`), because
what makes a good Connect candidate (deployable traction) is not what makes a good Empower
candidate (technical promise Siemens tools can accelerate):

| | traction | siemens_fit | product | market | founder | ecosystem |
|---|---|---|---|---|---|---|
| **Connect** | 0.35 | 0.30 | 0.15 | 0.10 | 0.05 | 0.05 |
| **Collaborate** | 0.15 | 0.35 | 0.20 | 0.10 | 0.15 | 0.05 |
| **Empower** | 0.05 | 0.20 | 0.25 | 0.10 | 0.25 | 0.15 |

---

## 8. Routing

`core/route.py::route` (`:11`) is eligibility-based — a startup can qualify for more than one
pillar. `pillar` is the primary, `secondary` lists the rest.

```python
if aligned and dimensions["siemens_fit"] >= 50.0:      # route.py:25
    if r_connect >= 70 and traction >= 60:  eligible.append("Connect")       # :26-27
    if r_collab  >= 55 and traction >= 35:  eligible.append("Collaborate")   # :28-29
    eligible.append("Empower")                                               # :30
eligible.sort(key=lambda r: cards.get(r, final), reverse=True)               # :32
pillar = eligible[0] if eligible else "Pass"                                 # :33
```

Three properties fall out of this, and they are not obvious:

1. **The alignment gate at line 25 is the only thing that produces `Pass`.** It reads
   `fit.aligned` and the *raw* `dimensions.siemens_fit` against `FIT_ALIGN_THRESHOLD`
   (50.0, `config.py:28`).
2. **`Empower` is appended unconditionally** (`:30`) — no score gate, no traction gate. So once
   the alignment gate passes, `eligible` is never empty and the result can never be `Pass`.
3. **The primary is the highest-scoring eligible route, not a fixed order** (`:32`), so the
   headline pillar always matches what the scorecards say.

`reasons` and `risks` are model prose (`route.py:_route_reasons`) and are not recomputable from the
stored numbers.

---

## 9. Caching

| Layer | Where | Note |
|---|---|---|
| Web results | `web.install_cache` (`web.py:25`), backed by the `web_cache` table | Injected by `api/main.py` — `core/` never imports `api/` |
| Failed fetches | `web.py:356` | Only **successful** fetches are cached, so a timeout or transient 5xx cannot pin an empty result |
| Whole evaluations | `store.latest_run_for_alias` | Keyed through `company_aliases` |
| Cache bypass | `evaluate(use_web_cache=False)` (`pipeline.py:82-94`) | What "Re-evaluate" uses |

`company_aliases` exists because the cache-first lookup searches on what the reviewer *typed* while
`save_run` files the run under what the pipeline *resolved* — without it, `phena` never finds the
run stored as `Phena Technologies` and the whole external pipeline runs again.

---

## 10. What happens without keys

Neither key is required; the engine degrades rather than failing.

| Missing | Effect |
|---|---|
| `GEMINI_API_KEY` | `llm.available` is False. Query generation falls back to the fixed templates, extraction to keyword matching (`profile._offline_extract`, `:333`), program tiers to `KNOWN_PROGRAM_TIERS` (`config.py:48`). Engine string reads `offline-fallback` (`pipeline.py:212`). |
| `GLASSDOLLAR_API_KEY` | No live database. Resolution falls to the local xlsx and then the web. |

**The GlassDollar key only resolves inside the Siemens network**, so nothing about the live API can
be verified from a laptop or from CI — `tests/test_glassdollar_first.py` drives the client contract
with a fake and says so at the top.

---

## 11. Reading a stored run

Given a row from `/api/runs/{id}`, the provenance of any figure is answerable:

1. **Is it in `profile`?** Then it came from GlassDollar — unless the same key appears in
   `profile_sources`, which means it was blank in the database and backfilled from the web. That
   entry carries the origin and, where one exists, the URL.
2. **Is it a dimension or the score?** Recompute it: §7 is the whole formula, and `score.raw_score`,
   `score.data_completeness` and `score.data_confidence` are all stored.
3. **Is it a founder, advisor, program or customer?** It is in `deep_profile`, and it only got
   there by surviving §6. Programs additionally carry `confidence: self_asserted | corroborated`,
   which is what decides whether they score at full or half weight.
4. **Is it the pillar?** §8, from `score.route_scorecards` and `fit.aligned`. The `reasons` prose
   is not derivable — it is generated text.
5. **Where did the underlying evidence come from?** `facts[]`, each with `method`, `source_url`,
   `confidence` and `retrieved_at`.
