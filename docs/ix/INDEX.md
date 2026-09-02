# iX Reference Index (pinned versions)

Pinned: `@siemens/ix` 5.1.1, `@siemens/ix-react` 5.1.1, `@siemens/ix-icons` 3.5.0.

**Do not trust the public iX docs site for version-specific facts** — it tracks the latest
release, not 5.1.1. These four files are extracted directly from the installed package files in
`ui/node_modules/@siemens/` and are the source of truth for this migration.

- `tokens.md` — all 240 `--theme-*` custom properties from `ix/dist/siemens-ix/theme/classic-{light,dark}.css`, grouped by kind, plus a mapping table against `ui/src/tokens.css`.
  Grep: `grep -i "theme-color-primary" docs/ix/tokens.md`
- `components.md` — all 104 `@siemens/ix-react` components with their web-component tag and declared props, grouped by function.
  Grep a component: `grep -n "^### \`IxButton\`" -A 20 docs/ix/components.md`
  Grep for a prop across all components: `grep -n "\`variant\`" docs/ix/components.md`
- `icons.md` — all 1479 `@siemens/ix-icons` glyph names (the `name=` value for `<ix-icon>`/`<IxIcon>`) with their JS export identifier.
  Grep: `grep -i "search" docs/ix/icons.md`
- `INDEX.md` — this file. Read it whole; the other three are meant to be grepped, not read in full (they total ~19k tokens).

Treat `components.d.ts` and the theme CSS files in `node_modules` as the ground truth if any
extraction here looks wrong or incomplete — these docs are a convenience layer over them, not a
replacement.
