# iX usage guidance (distilled from ix.siemens.io)

> **Version caveat:** the live docs site is pinned to release 5.0.0, one minor version behind our
> installed `@siemens/ix-react` 5.1.1, and it has no version switcher. For any rule below that
> touches something that could plausibly have changed in 5.1.0/5.1.1 (component props, new
> variants, behavior), `docs/ix/components.md` — extracted directly from node_modules — wins over
> anything stated here. This file is advisory, not authoritative, for version-sensitive facts.

## Colors
- Use background color tokens only on non-interactive backgrounds/screen areas; all are solid except color-0 (transparent). (https://ix.siemens.io/docs/styles/colors)
- Use `primary` (brand color) for primary buttons or selected elements. (https://ix.siemens.io/docs/styles/colors)
- Use semi-transparent color variants on interactive elements (cards, etc.) so they work across background colors. (https://ix.siemens.io/docs/styles/colors)
- Use "ghost" colors for elements with invisible backgrounds that need visible hover/active/selected states. (https://ix.siemens.io/docs/styles/colors)
- Reserve "ghost-alt" variants for alternating table grid rows. (https://ix.siemens.io/docs/styles/colors)
- Use "solid" color variants only on specific backgrounds or with borders (outline buttons, input fields). (https://ix.siemens.io/docs/styles/colors)
- Do not use status colors (alarm/critical/warning/success/info/neutral) for text — they lack required contrast; use them for icons/indicators/backgrounds, and pair with matching "contrast" colors for any text/icon placed on the colored background. (https://ix.siemens.io/docs/styles/colors)
- Use `color-contrast-text`/`color-contrast-bdr` when the background is unpredictable. (https://ix.siemens.io/docs/styles/colors)
- Use `color-std-text` as the default for all text/icons; `color-soft-text` for secondary text, subtitles, labels, hints, placeholders; `color-weak-text` only for disabled text; `color-alarm-text` for error/alarm text. (https://ix.siemens.io/docs/styles/colors)
- Use `color-hard-bdr` for solid non-transparent borders, `color-std-bdr` for input components, `color-soft-bdr` for cards/separators, `color-weak-bdr`/`color-x-weak-bdr` for subtle screen-area separation. (https://ix.siemens.io/docs/styles/colors)
- For charts, use the designated infrastructure colors for axes/ticks/gridlines/tooltips and the recommended data-series color sequence; use the 40%-opacity variants when comparing current vs. past or actual vs. benchmark. (https://ix.siemens.io/docs/styles/colors)

## Typography
- Use headings (H1-H6) sequentially and only to indicate real information hierarchy, not for visual sizing. (https://ix.siemens.io/docs/styles/typography/guide)
- Reserve H1 for the primary page title; don't have more than one per page. (https://ix.siemens.io/docs/styles/typography/guide)
- Use body-text styles for multi-line paragraphs, not for single-line labels. (https://ix.siemens.io/docs/styles/typography/guide)
- Use label styles for single-line text inside components. (https://ix.siemens.io/docs/styles/typography/guide)
- Use display type only for large single-line values such as KPI numbers on cards. (https://ix.siemens.io/docs/styles/typography/guide)
- Use code type only for code snippets/keywords/editor content, not for general text emphasis. (https://ix.siemens.io/docs/styles/typography/guide)

## Elevation
- Use the base layer (color-1) for the main page background and large sections. (https://ix.siemens.io/docs/styles/elevation)
- Use first-level containers (color-2 / component-1) for cards, side panels, and content blocks that need separation from the base. (https://ix.siemens.io/docs/styles/elevation)
- For containers nested inside containers, separate with borders or semi-transparent color-component-2 rather than another background layer. (https://ix.siemens.io/docs/styles/elevation)
- Reserve shadows (shadow-4) for elements that float above the main UI and demand immediate attention: dropdowns, tooltips, modals, toasts. (https://ix.siemens.io/docs/styles/elevation)
- Do not apply shadows to navigation elements or cards that are part of the primary layout flow — use background layering + borders instead. (https://ix.siemens.io/docs/styles/elevation)
- Do not use color-3 through color-8 for primary layering; they're reserved for specific components. (https://ix.siemens.io/docs/styles/elevation)

## Shadows
- Access shadow tokens via CSS custom properties, e.g. `var(--theme-shadow-1)`, rather than hardcoding shadow values. (https://ix.siemens.io/docs/styles/shadows)
- The public shadows page does not itself document which shadow level to use where beyond this — defer to the elevation page's floating-element rule above. (https://ix.siemens.io/docs/styles/shadows)

## Icons
- Choose icons that are easily recognizable, contextually appropriate, and not open to misinterpretation. (https://ix.siemens.io/docs/icons/icon-usage)
- Use `app-menu` for the application menu, `apps` for an application switcher, `context-menu` for item-specific actions (e.g. in event lists), `more-menu` for overflow options in toolbars; `drag-gripper` is for drag-and-drop reordering, not a menu affordance. (https://ix.siemens.io/docs/icons/icon-usage)
- Use status icons (alarm, critical, warning, success, info) only for their intended severity meaning, matched to the corresponding status color, in that hierarchy order. (https://ix.siemens.io/docs/icons/icon-usage)
- Be consistent within one context: either every item in a list/menu gets an icon, or none do. (https://ix.siemens.io/docs/icons/icon-usage)
- Pair every standalone (icon-only) control with a tooltip and an accessible description so screen readers can announce it. (https://ix.siemens.io/docs/icons/icon-usage)
- Expect navigation to collapse to a menu icon, the app switcher to move into an expandable menu, and header actions to move into a `more-menu` dropdown at small breakpoints. (https://ix.siemens.io/docs/icons/icon-usage)

## Accessibility
- Meet minimum contrast: 4.5:1 for body text, 3:1 for large text, 3:1 for icons against background, 3:1 for adjoining component colors, 3:1 for data-visualization elements against background. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Never rely on color alone — any information conveyed by color must also be available as text. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Make every feature operable by keyboard; tab order must follow reading order (left-to-right, top-to-bottom). (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Disabled elements must not be in the tab order and must not show tooltips. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Follow ARIA keyboard-interaction patterns for any custom (non-native) interactive component. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Keep interactive touch targets at least 24x24px, and support keyboard, mouse, touch, and voice input on the same control. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Provide cancel/undo for pointer-driven actions, and provide error descriptions via feedback text rather than color/icon alone. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Use correct ARIA (`aria-label`, `aria-labelledby`, `aria-describedby`) and semantic HTML (`h1`-`h6`, `header`/`main`/`footer` regions); make status messages programmatically discoverable. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Provide text alternatives for non-text content, descriptive page titles/link text, and a skip link past repeated blocks. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Ensure the UI stays readable and functional at 200% zoom; don't autoplay content; keep dismissible message bars visible until the user closes them. (https://ix.siemens.io/docs/guidelines/accessibility/overview)
- Group related form inputs and declare the page language in HTML; don't bake text into images; don't impose time limits without an adjustment option; don't validate input before the user leaves the field. (https://ix.siemens.io/docs/guidelines/accessibility/overview)

## Application shell
- Use `ix-application` as the single top-level wrapper for the whole app; it is a layout/config hub, not a visual-styling component. (https://ix.siemens.io/docs/components/application/guide)
- Let it drive the adaptive layout across its three breakpoints (lg >=62em, md >=48em, sm >=36em) rather than hand-rolling breakpoint logic; use `forceBreakpoint` only when a specific breakpoint must be forced. (https://ix.siemens.io/docs/components/application/guide)
- Nest the application header, application menu, and content component inside `ix-application` rather than placing them as siblings. (https://ix.siemens.io/docs/components/application/guide)
- If using the app switcher, open target applications in a new tab (avoid reload delay) and don't open the same application in multiple tabs at once. (https://ix.siemens.io/docs/components/application/guide)

## Application header
- Always include the company logo and application name in the header; logo width adapts, height stays fixed, and the app name truncates first when space runs out. (https://ix.siemens.io/docs/components/application-header/guide)
- Only add the avatar slot if the application actually has user profiles/login; use its dropdown for user-related actions. (https://ix.siemens.io/docs/components/application-header/guide)
- Use the right-aligned slot for high-level info/actions (login, mode switching, context changes) and the left-aligned slot for lean, compact toolbars. (https://ix.siemens.io/docs/components/application-header/guide)
- At the `sm` breakpoint, expect the menu to hide behind an icon and the logo/name-suffix to hide; slots collapse into an overflow dropdown — don't rely on automatic overflow for a complex slot layout, reduce the slot's complexity instead. (https://ix.siemens.io/docs/components/application-header/guide)
- Keep the header lean: don't overload slots with excessive elements, and don't add an application-icon or name-suffix unless it earns its place (e.g. partner branding). (https://ix.siemens.io/docs/components/application-header/guide)

## Application menu
- Use icons in second-level navigation items only when they aid recognition, and never mix icon and non-icon items within the same second-level category. (https://ix.siemens.io/docs/components/application-menu/guide)
- Use a custom tooltip when a label is truncated or needs extra context; show label tooltips on hover by default. (https://ix.siemens.io/docs/components/application-menu/guide)
- Reserve the bottom section for settings/theme-toggle and other state-toggling or overlay-opening items only — never for navigation; the navigation section must not hold non-navigational items. (https://ix.siemens.io/docs/components/application-menu/guide)
- Use fixed widths for the collapsed and expanded states; don't make those widths configurable. (https://ix.siemens.io/docs/components/application-menu/guide)
- Enable vertical scrolling when items overflow, and support expand/collapse transitions. (https://ix.siemens.io/docs/components/application-menu/guide)
- Show notification badges on menu items when relevant, and avoid icons in submenu items unless they add clear value. (https://ix.siemens.io/docs/components/application-menu/guide)

## Content
- Use `ix-content` as the simple layout host for main page/section content, placed inside the application frame (not standalone). (https://ix.siemens.io/docs/components/content/guide)
- Use its optional header slot specifically for a content-header component rather than ad hoc heading markup. (https://ix.siemens.io/docs/components/content/guide)
- Don't nest multiple `ix-content` components inside each other. (https://ix.siemens.io/docs/components/content/guide)
- Don't omit the header slot when the page/section actually needs a title. (https://ix.siemens.io/docs/components/content/guide)

## Content header
- Put in it: an optional back button, a short descriptive title, an optional subtitle, an optional header-slot for status pills/counters, and action buttons for frequent tasks (e.g. Add/Edit). (https://ix.siemens.io/docs/components/content-header/guide)
- Left side (auto-aligned) holds back button/title/subtitle; right side (auto-aligned) holds action buttons. (https://ix.siemens.io/docs/components/content-header/guide)
- Header-slot elements are top-aligned by default; use margin if they need to be vertically centered with the title. (https://ix.siemens.io/docs/components/content-header/guide)
- Use the primary variant for the page's main headline and the secondary variant for contextual actions on a specific section — never use secondary as the page title, and never have more than one primary headline per page. (https://ix.siemens.io/docs/components/content-header/guide)
- Keep the header slot to space-efficient items only; don't overload it. (https://ix.siemens.io/docs/components/content-header/guide)

## Deferred — UNVERIFIED SLUGS, fetch just-in-time when building each row
The `menu` → `application-menu` miss proves slugs guessed from a component's PascalCase name are
not reliable — the same mistake will otherwise recur once per row, each time reading as "iX has no
guidance for this" rather than "wrong slug." **Rule:** before fetching a deferred component's
`/guide`, confirm its real slug against `https://ix.siemens.io/docs/components/overview`; if the
guessed slug 404s, try the `application-*` prefix before concluding the page doesn't exist.

Already confirmed real (safe to fetch directly, no overview check needed): `application`,
`application-header`, `application-menu`, `content`, `content-header`, `settings`.

Everything below is an unverified guess, not a confirmed slug — verify each against the overview
page before fetching, and expect some to actually live under `application-*` or another prefix:
menu-item, menu-category, menu-avatar, menu-settings, expanding-search, dropdown, dropdown-item, card, card-list, key-value, key-value-list, kpi, tile, pagination, category-filter, filter-chip, chip, pill, pane, pane-layout, blind, modal, popover, tooltip, tabs, tab-item, workflow-step, workflow-steps, empty-state, message-bar, toast, toast-container, spinner, progress-indicator, button, icon-button, split-button, toggle-button, input, select, slider, range-field, checkbox, avatar, breadcrumb, breadcrumb-item, typography, layout-grid, layout-auto, col, row.
