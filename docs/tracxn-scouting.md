# Solve a Problem and Tracxn

The `/workspace` page is now **Solve a Problem**. `/explore` remains the company database so existing saved-view links continue to work.

## Connect an account

1. Install `requirements.txt`. The adapter uses `requests` and `jsonschema`.
2. Set `TRACXN_REDIRECT_URI` to the public app origin followed by `/api/integrations/tracxn/callback`. For local Vite development use `http://localhost:5173/api/integrations/tracxn/callback`. Restart the API after changing environment settings.
3. Open **Explore a startup → Connect Tracxn**, sign in, and approve read access. Each reviewer connects their own account. A normal Tracxn subscription needs MCP access enabled.

The local `.env` has the localhost callback configured. Production must supply its own HTTPS callback. The browser and API must use the same origin (Vite proxies `/api` locally).

Tracxn's official endpoint is `https://platform.tracxn.com/mcp`. Its public OAuth metadata, checked on 2026-09-08, advertises dynamic client registration, PKCE S256, the `read` scope, issuer validation, and authorization-code grants. It does not advertise refresh grants; expired tokens require reconnecting. Disconnect removes this app's saved token. It does not revoke consent on Tracxn's side.

Tokens and OAuth transactions live in the existing Redis session store, keyed by the authenticated reviewer. No token enters SQLite, exports, URLs returned to the UI, or browser storage. `SESSION_BACKEND=memory` is only for local/test use. Tracxn-derived model/search responses bypass the shared research cache; complete scouting responses are cached for ten minutes per reviewer and connection identity.

## Search behavior

- Try the connected user's Tracxn company search first. MCP tools and their input schemas are discovered at runtime; schema validation happens before calling a compatible search tool. Simple query schemas need no tool-selection LLM call.
- If disconnected, unavailable, or without company results, use GlassDollar. Its API is name-based, so capability searches may have no matches.
- Include relevant internal applications, preserving application priority. Final display order is applications, Tracxn, GlassDollar, then web, with relevance ordering inside each group. Duplicate names only receive missing fields from lower-priority sources.
- Fill missing descriptions from attributable web snippets. If fewer than five relevant candidates remain, run a smaller web discovery wave. `do_web=false` disables both web steps.
- Rank evidence against the problem. A valid empty LLM ranking remains empty. Unknown facts stay unknown; unsupported MCP response shapes fall back to GlassDollar/web.

The integration covers **startup evaluation and problem scouting**. A new evaluation uses an exact Tracxn company name/domain match before GlassDollar and web research. Tracxn fields seed the profile; unsupported or missing fields still use the established evidence pipeline. Ambiguous identities fall back. Licensed evaluations are stored per reviewer in Redis for 30 days, using private run IDs, and never enter the shared company database. Cached public evaluations remain shared. Existing saved evaluations show a refresh prompt when they predate the new rubric.

## Performance

GlassDollar keyword searches run concurrently (three workers) with an eight-second request timeout and one attempt per search, following a single token check. Web discovery is skipped when the ranked provider results are sufficient. Keyword derivation and web extraction request no reasoning; `SCOUTING_LLM_MODEL` can select a cheaper/faster model supported by the configured gateway without changing full evaluation's model. Repeat successful requests reuse the per-user ten-minute cache. Provider-failure fallbacks are not cached.

These are avoided-work and concurrency improvements; no live provider latency claim has been measured. A model outage or web-provider retries can still make an uncached search slow.

## Verification and remaining live check

`tests/test_tracxn_scouting.py` exercises fallback order, disabled web, rejected rankings, schema discovery, OAuth state/PKCE/issuer handling, account isolation, and shared-cache isolation. Component and browser tests cover the brief, examples, source labels, result links, errors, and responsive layout. Browser tests use fixtures, not paid APIs.

The public OAuth metadata was verified live. Authenticated Tracxn tool responses and account-specific access have not been verified: an MCP-enabled Tracxn user must complete sign-in and run a real query. JSON company records and JSON text content are supported; prose-only or incompatible vendor schemas fall back safely and may need an adapter update after that live check.

Sources: [Tracxn custom clients](https://help.tracxn.com/en/articles/15131843-connect-any-other-mcp-compatible-client), [Tracxn MCP FAQ](https://help.tracxn.com/en/articles/15131961-faqs-tracxn-mcp).
