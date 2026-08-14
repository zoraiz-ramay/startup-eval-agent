#!/usr/bin/env node
/**
 * Deterministic Siemens iX / accessibility conformance checks for ui/src.
 *
 * This is a script rather than a reviewer agent on purpose. The previous multi-agent system had a
 * `ui_review` agent with `tools: []` that scored "ix_compliance" by reading JSX and returning a
 * number — an opinion that could not be reproduced, argued with, or regressed against. Everything
 * here is mechanically checkable, so an agent cannot talk its way past it and a human can see
 * exactly why something failed.
 *
 * Rules are intentionally narrow: each one has caught a real defect in this repo, and anything
 * that cannot be checked without judgement belongs in a human review instead.
 *
 *   node scripts/ix_lint.mjs [--json]
 */
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const UI_SRC = join(ROOT, "ui", "src");
const TOKENS = join(UI_SRC, "tokens.css");

const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(jsx?|css)$/.test(name)) files.push(p);
  }
})(UI_SRC);

const findings = [];
const add = (file, line, rule, message) =>
  findings.push({ file: relative(ROOT, file).split(sep).join("/"), line, rule, message });

/** Declared design tokens — the allowed vocabulary for colour. */
const tokenNames = new Set(
  (readFileSync(TOKENS, "utf8").match(/^\s*(--[\w-]+)\s*:/gm) || [])
    .map((m) => m.trim().replace(/\s*:$/, "")),
);

const RAW_COLOUR = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/;
const NAMED_COLOUR = /(?:^|[\s:;"'{])(?:red|blue|green|black|white|orange|purple|gray|grey)(?:[\s;"'}]|$)/i;
// Interactive elements whose entire content is an icon/symbol have no accessible name.
const ICON_ONLY = /<button\b(?![^>]*aria-label)(?![^>]*aria-labelledby)[^>]*>\s*\{?\s*["'`]?[^\w\s<{"'`][^<]{0,3}["'`]?\s*\}?\s*<\/button>/;

for (const file of files) {
  const src = readFileSync(file, "utf8");
  const isTokens = file === TOKENS;
  const isTest = /\.test\.jsx?$/.test(file);
  // Split on \r?\n, not "\n". A trailing \r defeats the comment stripping below: "." does not
  // match \r and "$" without /m only matches end-of-string, so //-comments survive on a CRLF
  // file and their prose gets linted as code. That is invisible until git's autocrlf rewrites a
  // checkout, at which point identical source starts and stops failing depending on how the
  // working tree was produced.
  const lines = src.split(/\r?\n/);

  lines.forEach((raw, i) => {
    const line = i + 1;
    const code = raw.replace(/\/\*.*?\*\//g, "").replace(/\/\/.*$/, "");
    if (!code.trim()) return;

    // 1. Colour literals belong in tokens.css and nowhere else — that file is the single seam
    //    where the palette is swapped for the iX theme.
    if (!isTokens && !isTest && (RAW_COLOUR.test(code) || NAMED_COLOUR.test(code))) {
      add(file, line, "ix/no-raw-colour",
        "Raw colour outside tokens.css — use a var(--token) so the iX theme controls it");
    }

    // 2. A var() must resolve to a token that actually exists, or it silently renders nothing.
    //    Siemens iX supplies its own variables (--theme-*, --ix-*) from siemens-ix.css; those are
    //    declared outside this repo, so they are trusted rather than resolved here. Referencing
    //    them is the whole point of the token migration.
    for (const m of code.matchAll(/var\(\s*(--[\w-]+)/g)) {
      const external = m[1].startsWith("--theme-") || m[1].startsWith("--ix-");
      if (!tokenNames.has(m[1]) && !external) {
        add(file, line, "ix/unknown-token", `var(${m[1]}) is not declared in tokens.css`);
      }
    }

    // 3. Icon-only controls need an accessible name.
    if (!isTest && ICON_ONLY.test(code)) {
      add(file, line, "a11y/icon-button-name",
        "Icon-only <button> without aria-label — unusable with a screen reader");
    }

    // 4. Any element carrying an onClick must be genuinely interactive.
    if (!isTest && /onClick=/.test(code) && /<(div|span)\b/.test(code)
        && !/role=/.test(code) && !/aria-hidden/.test(code)) {
      add(file, line, "a11y/clickable-non-interactive",
        "onClick on a <div>/<span> with no role — not keyboard reachable");
    }

    // 5. The hand-rolled error box is how the app shipped an inaccessible error state for
    //    months while a passing test asserted otherwise. ErrorBox is the only sanctioned surface.
    if (!isTest && /className="error-box"/.test(code) && !/ErrorBox\.jsx/.test(file)) {
      add(file, line, "ix/use-errorbox",
        "Hand-rolled error box — use <ErrorBox> so role=\"alert\" is guaranteed");
    }
  });
}

/**
 * Ratchet, not a cliff.
 *
 * The codebase starts with dozens of pre-existing violations. Failing on all of them makes the
 * gate permanently red, and a permanently red gate is one everybody learns to ignore — the same
 * way three failing tests sat in this repo for months. So the baseline records what exists today
 * and the gate fails only on NEW findings. The recorded set is the UI agents' backlog, and the
 * number may only go down: `--baseline` refuses to record a larger set.
 */
const BASELINE = join(ROOT, "contract", "ix-lint-baseline.json");
const key = (f) => `${f.file}|${f.rule}|${f.message}`;   // line numbers move; identity does not

const report = () => {
  const byRule = {};
  for (const f of findings) (byRule[f.rule] ??= []).push(f);
  for (const [rule, items] of Object.entries(byRule)) {
    console.error(`\n${rule}  (${items.length})`);
    for (const f of items.slice(0, 12)) console.error(`  ${f.file}:${f.line}  ${f.message}`);
    if (items.length > 12) console.error(`  … and ${items.length - 12} more`);
  }
};

const readBaseline = () => {
  try {
    return new Set(JSON.parse(readFileSync(BASELINE, "utf8")).findings.map(key));
  } catch {
    return null;
  }
};

if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ findings, count: findings.length }, null, 2));
  process.exit(0);
}

if (process.argv.includes("--baseline")) {
  const existing = readBaseline();
  if (existing && findings.length > existing.size) {
    console.error(`refusing to grow the baseline: ${existing.size} -> ${findings.length}.`);
    console.error("Fix the new findings instead; the baseline only ratchets down.");
    process.exit(1);
  }
  const out = { _note: "Pre-existing iX/a11y debt. The gate fails on anything NOT in here. "
                     + "Only ever shrinks — regenerate after fixing findings.",
                generated_from: "scripts/ix_lint.mjs", count: findings.length, findings };
  writeFileSync(BASELINE, JSON.stringify(out, null, 2) + "\n");
  console.log(`ix_lint: baseline written with ${findings.length} known finding(s)`);
  process.exit(0);
}

const baseline = readBaseline();
if (baseline === null) {
  if (findings.length) report();
  console.error(`\nix_lint: no baseline at contract/ix-lint-baseline.json — `
              + `run: node scripts/ix_lint.mjs --baseline`);
  process.exit(findings.length ? 1 : 0);
}

const fresh = findings.filter((f) => !baseline.has(key(f)));
const fixed = baseline.size - (findings.length - fresh.length);

if (fresh.length) {
  const byRule = {};
  for (const f of fresh) (byRule[f.rule] ??= []).push(f);
  for (const [rule, items] of Object.entries(byRule)) {
    console.error(`\nNEW  ${rule}  (${items.length})`);
    for (const f of items) console.error(`  ${f.file}:${f.line}  ${f.message}`);
  }
  console.error(`\nix_lint: ${fresh.length} NEW finding(s). `
              + `Fix them, or if intentional re-baseline deliberately.`);
  process.exit(1);
}

console.log(`ix_lint: no new findings `
          + `(${findings.length} known, ${fixed > 0 ? `${fixed} fixed since baseline` : "none fixed yet"})`);
process.exit(0);
