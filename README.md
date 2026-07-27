# Siemens Startup Evaluation Agent

A web app that takes a startup from the GlassDollar export, enriches it with outside
evidence, scores it on a weighted model, and routes it to a **Siemens for Startups**
pillar: **Empower · Collaborate · Connect · Pass**.

Implements the deck pipeline: **INPUT → ENRICH → VERIFY → STRUCTURE → SCORE → REVIEW**,
with provenance on every fact (`value · source_url · method · confidence · retrieved_at`).

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py          # opens in your browser
```

Type a startup name (try **RIIICO**), or pick one from the dropdown, then **Evaluate**.

## LLM vs. free fallback

- **With a Siemens LLM API key** (recommended): full AI reasoning for the offering
  summary, Siemens-portfolio fit, and routing rationale. Get a key with the `llm` scope
  from [my.siemens.com](https://my.siemens.com/).
  ```powershell
  $env:SIEMENS_API_KEY = "SIAK-..."
  ```
- **Without a key**: the app runs a **free offline fallback** (keyword engine) so you can
  use it immediately. Add the key any time to upgrade the reasoning — no code change.

Only the LLM is a paid service. All web enrichment is **DuckDuckGo (free)**; no paid
Crunchbase/LinkedIn APIs — those URLs are surfaced from the GlassDollar row.

## Connecting your data

| What | How |
|------|-----|
| GlassDollar | Defaults to `glassdollar_applications.xlsx` at the project root (produced by the GlassDollar pipeline). Override with `GLASSDOLLAR_XLSX` or the sidebar. Columns are matched by name. |
| Siemens tools | `siemens_tools.csv` (108 tools) ships with the app; edit it to tune the portfolio. |
| Pitch decks | Each row's `pdf_local_path` is resolved against the `pdfs/` folder at the project root (override with `PDF_DIR`). If `has_pdf` is false or the file is missing, the deck step is skipped. |

## Scoring (from the deck)

`FinalScore = RawScore × DataConfidence`, `DataConfidence = 0.5 + 0.5 × data_completeness`.

| Dimension | Weight |
|-----------|--------|
| Traction | 28% |
| Siemens Fit | 27% |
| Product | 15% |
| Market | 12% |
| Founder | 10% |
| Ecosystem | 8% |

- **Anti-gaming:** `effective_traction = verified + 0.5 × unverified` — claims alone can't win.
- **Confidence cap:** sparse/unverifiable profiles top out near **75**.
- **Siemens Fit** scores closeness to a deployable Siemens tool (interim: the 108-tool
  catalogue; swap in a BU pain-point catalogue later without touching the schema).

## Files

```
app.py               Streamlit UI (the REVIEW screen)
core.py              pipeline: load · enrich · verify · score · route + LLM client
siemens_tools.csv    Siemens software portfolio (108 tools)
glassdollar_applications.xlsx   GlassDollar export at the project root (default data source)
requirements.txt / .env.example
```

## Notes / next steps

- **SharePoint online (not synced):** add Microsoft Graph auth to pull decks directly
  (kept out for now to avoid storing credentials).
- **BU pain-point catalogue:** the Siemens-Fit dimension is built to swap from the software
  catalogue to a focus-area/pain-point catalogue when available.
- **Batch mode:** `core.evaluate()` is importable for scoring a whole sheet headless.
