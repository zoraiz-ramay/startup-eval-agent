# iX Design Tokens (ix 5.1.1, classic theme)

Extracted from `@siemens/ix/dist/siemens-ix/theme/classic-light.css` and `classic-dark.css`.
Total distinct custom properties: **240** (light defines 240, dark defines 240).

All tokens are scoped under `[data-ix-theme=classic][data-ix-color-schema=light|dark]`. Values that are identical between light and dark are theme-invariant (mostly typography/shadow-shape tokens); values that differ carry the actual color-scheme change.

## Color (125)

| Token | Light | Dark |
|---|---|---|
| `--theme-color-0` | `hsla(0,0%,100%,0)` | `transparent` |
| `--theme-color-1` | `#fff` | `#0f1619` |
| `--theme-color-1--active` | `#e2e4e6` | `#222b2f` |
| `--theme-color-1--hover` | `#eff0f1` | `#283236` |
| `--theme-color-2` | `#eff0f1` | `#283236` |
| `--theme-color-3` | `#e2e4e6` | `#3c484d` |
| `--theme-color-4` | `#d8dadd` | `#4c5a60` |
| `--theme-color-5` | `#cfd2d5` | `#59686f` |
| `--theme-color-6` | `#c8cbcf` | `#63737b` |
| `--theme-color-7` | `#c2c6ca` | `#6b7c85` |
| `--theme-color-8` | `#92979b` | `#94a1a9` |
| `--theme-color-alarm` | `#d72332` | `#ff2453` |
| `--theme-color-alarm--active` | `#b41d2a` | `#ff335f` |
| `--theme-color-alarm--contrast` | `#fff` | `#000` |
| `--theme-color-alarm--hover` | `#c11f2d` | `#ff577b` |
| `--theme-color-alarm-10` | `rgba(215,35,50,.1)` | `rgba(255,38,85,.1)` |
| `--theme-color-alarm-40` | `rgba(215,35,50,.4)` | `rgba(255,38,85,.4)` |
| `--theme-color-alarm-bdr` | `#d72332` | `#ff2453` |
| `--theme-color-alarm-text` | `#b81e3f` | `#ff7694` |
| `--theme-color-backdrop` | `hsla(0,0%,100%,.85)` | `rgba(0,0,0,.85)` |
| `--theme-color-backdrop-3` | `hsla(210,7%,89%,.85)` | `rgba(55,70,77,.85)` |
| `--theme-color-component-1` | `hsla(213,7%,68%,.2)` | `rgba(140,161,171,.2)` |
| `--theme-color-component-1--active` | `hsla(213,7%,68%,.3)` | `rgba(140,161,171,.25)` |
| `--theme-color-component-1--hover` | `hsla(213,7%,68%,.15)` | `rgba(140,161,171,.45)` |
| `--theme-color-component-10` | `rgba(0,81,89,.75)` | `rgba(0,234,255,.75)` |
| `--theme-color-component-10--active` | `rgba(0,70,77,.75)` | `rgba(10,235,255,.75)` |
| `--theme-color-component-10--disabled` | `rgba(0,81,89,.15)` | `rgba(0,234,255,.2)` |
| `--theme-color-component-10--hover` | `rgba(0,93,102,.75)` | `rgba(107,243,255,.6)` |
| `--theme-color-component-11` | `rgba(213,219,226,.2)` | `rgba(86,97,103,.2)` |
| `--theme-color-component-2` | `rgba(0,18,36,.1)` | `rgba(211,239,253,.15)` |
| `--theme-color-component-3` | `rgba(4,20,37,.2)` | `rgba(217,243,255,.4)` |
| `--theme-color-component-4` | `rgba(5,18,31,.3)` | `rgba(214,242,255,.42)` |
| `--theme-color-component-5` | `rgba(7,18,29,.45)` | `rgba(224,245,255,.6)` |
| `--theme-color-component-6` | `rgba(11,18,25,.6)` | `rgba(217,234,242,.65)` |
| `--theme-color-component-7` | `rgba(0,234,255,.2)` | `rgba(0,234,255,.15)` |
| `--theme-color-component-7--active` | `#00def2` | `#16565c` |
| `--theme-color-component-7--hover` | `#00eaff` | `#196269` |
| `--theme-color-component-8` | `#ebf7f8` | `#00273b` |
| `--theme-color-component-8--hover` | `#d1fbff` | `#002639` |
| `--theme-color-component-9` | `#0b5e65` | `#00eaff` |
| `--theme-color-component-9--active` | `#00464d` | `#0aebff` |
| `--theme-color-component-9--disabled` | `rgba(0,81,89,.3)` | `rgba(0,234,255,.3)` |
| `--theme-color-component-9--hover` | `#005d66` | `#52f1ff` |
| `--theme-color-component-error` | `#fcccd0` | `#4b1a28` |
| `--theme-color-component-info` | `#ccdefc` | `#001c4d` |
| `--theme-color-component-warning` | `#ffe8a8` | `#4b463a` |
| `--theme-color-contrast-bdr` | `#000` | `#fff` |
| `--theme-color-contrast-text` | `#000` | `#fff` |
| `--theme-color-critical` | `#bc5b01` | `#eb7a0a` |
| `--theme-color-critical--active` | `#9d4d01` | `#eb8014` |
| `--theme-color-critical--contrast` | `#fff` | `#000` |
| `--theme-color-critical--hover` | `#ad5401` | `#ed8721` |
| `--theme-color-critical-40` | `rgba(188,91,1,.4)` | `rgba(235,122,10,.4)` |
| `--theme-color-dynamic` | `#005e66` | `#00eaff` |
| `--theme-color-dynamic--active` | `#0e494e` | `#5cd5e0` |
| `--theme-color-dynamic--hover` | `#0f5157` | `#62e2ee` |
| `--theme-color-dynamic-alt` | `#00eaff` | `#00eaff` |
| `--theme-color-dynamic-alt--active` | `#5cd5e0` | `#5cd5e0` |
| `--theme-color-dynamic-alt--hover` | `#62e2ee` | `#62e2ee` |
| `--theme-color-focus-bdr` | `#199fff` | `#199fff` |
| `--theme-color-ghost` | `hsla(70,16%,61%,0)` | `hsla(0,0%,100%,0)` |
| `--theme-color-ghost--active` | `hsla(213,7%,68%,.3)` | `rgba(140,161,171,.15)` |
| `--theme-color-ghost--hover` | `hsla(213,7%,68%,.2)` | `rgba(140,161,171,.2)` |
| `--theme-color-ghost--selected` | `rgba(0,234,255,.2)` | `rgba(0,255,255,.1)` |
| `--theme-color-ghost--selected-active` | `rgba(0,145,158,.2)` | `rgba(115,221,221,.2)` |
| `--theme-color-ghost--selected-hover` | `rgba(32,184,197,.2)` | `rgba(104,253,253,.2)` |
| `--theme-color-ghost-alt` | `rgba(0,20,40,.05)` | `hsla(0,0%,100%,.05)` |
| `--theme-color-ghost-alt--active` | `hsla(213,7%,68%,.35)` | `rgba(140,161,171,.15)` |
| `--theme-color-ghost-alt--hover` | `hsla(213,7%,68%,.2)` | `rgba(140,161,171,.2)` |
| `--theme-color-ghost-alt--selected` | `rgba(0,216,236,.2)` | `rgba(58,255,255,.15)` |
| `--theme-color-ghost-alt--selected-active` | `rgba(0,148,161,.2)` | `rgba(132,225,225,.25)` |
| `--theme-color-ghost-alt--selected-hover` | `rgba(30,171,184,.25)` | `rgba(123,253,253,.25)` |
| `--theme-color-ghost-primary--active` | `rgba(0,190,207,.2)` | `rgba(0,128,128,.2)` |
| `--theme-color-ghost-primary--hover` | `rgba(0,234,255,.2)` | `rgba(0,255,255,.15)` |
| `--theme-color-gradient-effect-1` | `#006e93` | `#1aecff` |
| `--theme-color-gradient-effect-2` | `#16565c` | `#00bde3` |
| `--theme-color-hard-bdr` | `#b2b8be` | `#6b7c85` |
| `--theme-color-info` | `#0041b2` | `#357fff` |
| `--theme-color-info--active` | `#003694` | `#3d84ff` |
| `--theme-color-info--contrast` | `#fff` | `#000` |
| `--theme-color-info--hover` | `#003a9e` | `#4d8eff` |
| `--theme-color-info-40` | `rgba(0,65,177,.4)` | `rgba(53,127,255,.4)` |
| `--theme-color-inv-contrast-text` | `#fff` | `#000` |
| `--theme-color-inv-soft-text` | `rgba(229,242,255,.6)` | `rgba(0,13,20,.6)` |
| `--theme-color-inv-std-text` | `rgba(245,250,255,.9)` | `rgba(0,10,20,.9)` |
| `--theme-color-inv-weak-text` | `rgba(219,237,255,.45)` | `rgba(0,13,20,.45)` |
| `--theme-color-lightbox` | `hsla(0,0%,100%,.65)` | `rgba(0,0,0,.65)` |
| `--theme-color-logo` | `#000` | `#fff` |
| `--theme-color-logo-login` | `#000` | `#fff` |
| `--theme-color-neutral` | `#66727e` | `#b6b8b9` |
| `--theme-color-neutral--active` | `#545e68` | `#acaeaf` |
| `--theme-color-neutral--contrast` | `#fff` | `#000` |
| `--theme-color-neutral--hover` | `#5b6671` | `#c8cacb` |
| `--theme-color-neutral-40` | `rgba(102,114,126,.4)` | `hsla(200,2%,72%,.4)` |
| `--theme-color-primary` | `#006e93` | `#00bde3` |
| `--theme-color-primary--active` | `#16565c` | `#00d3e5` |
| `--theme-color-primary--contrast` | `#fff` | `#000` |
| `--theme-color-primary--disabled` | `rgba(0,110,147,.3)` | `rgba(0,170,204,.45)` |
| `--theme-color-primary--hover` | `#196269` | `#1aecff` |
| `--theme-color-secondary` | `#fff` | `#000` |
| `--theme-color-secondary--active` | `#b8edf2` | `#001d2b` |
| `--theme-color-secondary--hover` | `#ccfbff` | `#002639` |
| `--theme-color-shadow-1` | `rgba(0,0,0,.1)` | `rgba(0,0,0,.6)` |
| `--theme-color-shadow-2` | `rgba(0,0,0,.2)` | `#000` |
| `--theme-color-shadow-3` | `rgba(0,0,0,.1)` | `rgba(0,0,0,.6)` |
| `--theme-color-soft-bdr` | `rgba(0,20,40,.2)` | `rgba(211,236,248,.4)` |
| `--theme-color-soft-text` | `rgba(0,10,20,.6)` | `rgba(229,247,255,.65)` |
| `--theme-color-std-bdr` | `rgba(0,20,40,.3)` | `rgba(211,236,248,.55)` |
| `--theme-color-std-text` | `rgba(0,10,20,.9)` | `rgba(245,252,255,.9)` |
| `--theme-color-success` | `#2c8500` | `#4c0` |
| `--theme-color-success--active` | `#246b00` | `#47d600` |
| `--theme-color-success--contrast` | `#fff` | `#000` |
| `--theme-color-success--hover` | `#277500` | `#4eeb00` |
| `--theme-color-success-40` | `rgba(44,133,0,.4)` | `rgba(68,204,0,.4)` |
| `--theme-color-warning` | `#fb0` | `#fb0` |
| `--theme-color-warning--active` | `#ffba0a` | `#ffba0a` |
| `--theme-color-warning--contrast` | `#000` | `#000` |
| `--theme-color-warning--hover` | `#ffc533` | `#ffc533` |
| `--theme-color-warning-10` | `rgba(255,187,0,.1)` | `rgba(255,187,0,.1)` |
| `--theme-color-warning-40` | `rgba(255,187,0,.4)` | `rgba(255,187,0,.4)` |
| `--theme-color-warning-bdr` | `#947100` | `#fb0` |
| `--theme-color-warning-text` | `#947100` | `#fb0` |
| `--theme-color-weak-bdr` | `rgba(35,48,60,.15)` | `rgba(224,245,255,.25)` |
| `--theme-color-weak-text` | `rgba(0,10,20,.4)` | `rgba(219,244,255,.4)` |
| `--theme-color-x-weak-bdr` | `rgba(174,181,189,.2)` | `rgba(142,157,165,.2)` |

## Chart (40)

| Token | Light | Dark |
|---|---|---|
| `--theme-chart-1` | `#008a7c` | `#00ffe7` |
| `--theme-chart-1-40` | `rgba(0,138,124,.4)` | `rgba(0,255,231,.4)` |
| `--theme-chart-10` | `#7c40ff` | `#b999ff` |
| `--theme-chart-10-40` | `rgba(124,64,255,.4)` | `rgba(185,153,255,.4)` |
| `--theme-chart-11` | `#900eec` | `#d08fff` |
| `--theme-chart-11-40` | `rgba(144,14,236,.4)` | `rgba(208,143,255,.4)` |
| `--theme-chart-12` | `#aa32be` | `#ed85ff` |
| `--theme-chart-12-40` | `rgba(170,50,190,.4)` | `rgba(237,133,255,.4)` |
| `--theme-chart-13` | `#6f2542` | `#f38fc2` |
| `--theme-chart-13-40` | `rgba(111,37,66,.4)` | `rgba(243,143,194,.4)` |
| `--theme-chart-14` | `#9e5833` | `#ef9a9a` |
| `--theme-chart-14-40` | `rgba(158,88,51,.4)` | `hsla(0,73%,77%,.4)` |
| `--theme-chart-15` | `#b74e2a` | `#ffb180` |
| `--theme-chart-15-40` | `rgba(183,78,42,.4)` | `rgba(255,177,128,.4)` |
| `--theme-chart-16` | `#73735e` | `#cacab4` |
| `--theme-chart-16-40` | `rgba(115,115,94,.4)` | `hsla(60,17%,75%,.4)` |
| `--theme-chart-17` | `#7a8000` | `#b5bd00` |
| `--theme-chart-17-40` | `rgba(122,128,0,.4)` | `rgba(181,189,0,.4)` |
| `--theme-chart-2` | `#00572b` | `#94ffc9` |
| `--theme-chart-2-40` | `rgba(0,87,43,.4)` | `rgba(148,255,201,.4)` |
| `--theme-chart-3` | `#00838f` | `#00c2cc` |
| `--theme-chart-3-40` | `rgba(0,131,143,.4)` | `rgba(0,194,204,.4)` |
| `--theme-chart-4` | `#003c61` | `#a3eeff` |
| `--theme-chart-4-40` | `rgba(0,60,97,.4)` | `rgba(163,238,255,.4)` |
| `--theme-chart-5` | `#61778c` | `#90b4c5` |
| `--theme-chart-5-40` | `rgba(97,119,140,.4)` | `rgba(144,180,197,.4)` |
| `--theme-chart-6` | `#0076a8` | `#42c6ff` |
| `--theme-chart-6-40` | `rgba(0,118,168,.4)` | `rgba(66,198,255,.4)` |
| `--theme-chart-7` | `#182171` | `#7aaaff` |
| `--theme-chart-7-40` | `rgba(24,33,113,.4)` | `rgba(122,170,255,.4)` |
| `--theme-chart-8` | `#0041d6` | `#9ebbff` |
| `--theme-chart-8-40` | `rgba(0,65,214,.4)` | `rgba(158,187,255,.4)` |
| `--theme-chart-9` | `#4a52f2` | `#9ea3ff` |
| `--theme-chart-9-40` | `rgba(74,82,242,.4)` | `rgba(158,163,255,.4)` |
| `--theme-chart-axes` | `rgba(0,0,0,.3)` | `hsla(0,0%,100%,.3)` |
| `--theme-chart-grid-fill` | `#fff` | `#23233c` |
| `--theme-chart-grid-lines` | `rgba(0,0,0,.1)` | `hsla(0,0%,100%,.1)` |
| `--theme-chart-ticks` | `rgba(0,0,0,.3)` | `hsla(0,0%,100%,.35)` |
| `--theme-chart-tooltip-bdr` | `rgba(0,0,0,.2)` | `hsla(0,0%,100%,.25)` |
| `--theme-chart-tooltip-fill` | `hsla(0,0%,100%,.8)` | `rgba(15,22,25,.8)` |

## Typography (2)

| Token | Light | Dark |
|---|---|---|
| `--theme-font-code` | `"JetBrains Mono"` | `"JetBrains Mono"` |
| `--theme-font-sans` | `"Siemens Sans"` | `"Siemens Sans"` |

## Typography (composite) (39)

| Token | Light | Dark |
|---|---|---|
| `--theme-body` | `var(--theme-font-weight-normal) var(--theme-ms-0)/var(--theme-line-height-md) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms-0)/var(--theme-line-height-md) var(--theme-font-sans)` |
| `--theme-body-lg` | `var(--theme-font-weight-normal) var(--theme-ms-1)/var(--theme-line-height-lg) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms-1)/var(--theme-line-height-lg) var(--theme-font-sans)` |
| `--theme-body-sm` | `var(--theme-font-weight-normal) var(--theme-ms--1)/var(--theme-line-height-lg) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms--1)/var(--theme-line-height-lg) var(--theme-font-sans)` |
| `--theme-body-xs` | `var(--theme-font-weight-normal) var(--theme-ms--2)/var(--theme-line-height-lg) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms--2)/var(--theme-line-height-lg) var(--theme-font-sans)` |
| `--theme-code` | `var(--theme-font-weight-normal) var(--theme-ms-0)/var(--theme-line-height-lg) var(--theme-font-code)` | `var(--theme-font-weight-normal) var(--theme-ms-0)/var(--theme-line-height-lg) var(--theme-font-code)` |
| `--theme-code-lg` | `var(--theme-font-weight-normal) var(--theme-ms-1)/var(--theme-line-height-lg) var(--theme-font-code)` | `var(--theme-font-weight-normal) var(--theme-ms-1)/var(--theme-line-height-lg) var(--theme-font-code)` |
| `--theme-code-sm` | `var(--theme-font-weight-normal) var(--theme-ms--1)/var(--theme-line-height-lg) var(--theme-font-code)` | `var(--theme-font-weight-normal) var(--theme-ms--1)/var(--theme-line-height-lg) var(--theme-font-code)` |
| `--theme-display` | `var(--theme-font-weight-normal) var(--theme-ms-3)/var(--theme-line-height-xs) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms-3)/var(--theme-line-height-xs) var(--theme-font-sans)` |
| `--theme-display-lg` | `var(--theme-font-weight-normal) var(--theme-ms-4)/var(--theme-line-height-xs) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms-4)/var(--theme-line-height-xs) var(--theme-font-sans)` |
| `--theme-display-sm` | `var(--theme-font-weight-normal) var(--theme-ms-2)/var(--theme-line-height-xs) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms-2)/var(--theme-line-height-xs) var(--theme-font-sans)` |
| `--theme-display-xl` | `var(--theme-font-weight-bold) var(--theme-ms-5)/var(--theme-line-height-xs) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-ms-5)/var(--theme-line-height-xs) var(--theme-font-sans)` |
| `--theme-display-xs` | `var(--theme-font-weight-normal) var(--theme-ms-1)/var(--theme-line-height-xs) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms-1)/var(--theme-line-height-xs) var(--theme-font-sans)` |
| `--theme-display-xxl` | `var(--theme-font-weight-bold) var(--theme-ms-6)/var(--theme-line-height-xs) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-ms-6)/var(--theme-line-height-xs) var(--theme-font-sans)` |
| `--theme-h1` | `var(--theme-font-weight-bold) var(--theme-ms-4)/var(--theme-line-height-sm) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-ms-4)/var(--theme-line-height-sm) var(--theme-font-sans)` |
| `--theme-h2` | `var(--theme-font-weight-bold) var(--theme-ms-3)/var(--theme-line-height-md) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-ms-3)/var(--theme-line-height-md) var(--theme-font-sans)` |
| `--theme-h3` | `var(--theme-font-weight-bold) var(--theme-ms-2)/var(--theme-line-height-lg) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-ms-2)/var(--theme-line-height-lg) var(--theme-font-sans)` |
| `--theme-h4` | `var(--theme-font-weight-bold) var(--theme-ms-1)/var(--theme-line-height-lg) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-ms-1)/var(--theme-line-height-lg) var(--theme-font-sans)` |
| `--theme-h5` | `var(--theme-font-weight-bold) var(--theme-ms-0)/var(--theme-line-height-md) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-ms-0)/var(--theme-line-height-md) var(--theme-font-sans)` |
| `--theme-h6` | `var(--theme-font-weight-bold) var(--theme-ms--1)/var(--theme-line-height-lg) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-ms--1)/var(--theme-line-height-lg) var(--theme-font-sans)` |
| `--theme-label` | `var(--theme-font-weight-normal) var(--theme-ms-0)/var(--theme-line-height-sm) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms-0)/var(--theme-line-height-sm) var(--theme-font-sans)` |
| `--theme-label-lg` | `var(--theme-font-weight-normal) var(--theme-ms-1)/var(--theme-line-height-sm) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms-1)/var(--theme-line-height-sm) var(--theme-font-sans)` |
| `--theme-label-sm` | `var(--theme-font-weight-normal) var(--theme-ms--1)/var(--theme-line-height-sm) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms--1)/var(--theme-line-height-sm) var(--theme-font-sans)` |
| `--theme-label-xs` | `var(--theme-font-weight-normal) var(--theme-ms--2)/var(--theme-line-height-sm) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-ms--2)/var(--theme-line-height-sm) var(--theme-font-sans)` |
| `--theme-text-caption` | `var(--theme-font-weight-bold) var(--theme-font-size-caption)/var(--theme-line-height-caption) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-font-size-caption)/var(--theme-line-height-caption) var(--theme-font-sans)` |
| `--theme-text-caption-single` | `var(--theme-font-weight-bold) var(--theme-font-size-caption)/var(--theme-line-height-caption-single) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-font-size-caption)/var(--theme-line-height-caption-single) var(--theme-font-sans)` |
| `--theme-text-default` | `var(--theme-font-weight-normal) var(--theme-font-size-default)/var(--theme-line-height-default) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-default)/var(--theme-line-height-default) var(--theme-font-sans)` |
| `--theme-text-default-single` | `var(--theme-font-weight-normal) var(--theme-font-size-default)/var(--theme-line-height-default-single) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-default)/var(--theme-line-height-default-single) var(--theme-font-sans)` |
| `--theme-text-default-title` | `var(--theme-font-weight-bold) var(--theme-font-size-default)/var(--theme-line-height-default) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-font-size-default)/var(--theme-line-height-default) var(--theme-font-sans)` |
| `--theme-text-default-title-single` | `var(--theme-font-weight-bold) var(--theme-font-size-default)/var(--theme-line-height-default-single) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-font-size-default)/var(--theme-line-height-default-single) var(--theme-font-sans)` |
| `--theme-text-default-underline` | `var(--theme-font-weight-normal) var(--theme-font-size-default)/var(--theme-line-height-default) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-default)/var(--theme-line-height-default) var(--theme-font-sans)` |
| `--theme-text-h2` | `var(--theme-font-weight-bold) var(--theme-font-size-xl)/var(--theme-line-height-h2) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-font-size-xl)/var(--theme-line-height-h2) var(--theme-font-sans)` |
| `--theme-text-l` | `var(--theme-font-weight-normal) var(--theme-font-size-l)/var(--theme-line-height-l) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-l)/var(--theme-line-height-l) var(--theme-font-sans)` |
| `--theme-text-l-single` | `var(--theme-font-weight-normal) var(--theme-font-size-l)/var(--theme-line-height-l-single) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-l)/var(--theme-line-height-l-single) var(--theme-font-sans)` |
| `--theme-text-l-title` | `var(--theme-font-weight-bold) var(--theme-font-size-l)/var(--theme-line-height-l) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-font-size-l)/var(--theme-line-height-l) var(--theme-font-sans)` |
| `--theme-text-l-title-single` | `var(--theme-font-weight-bold) var(--theme-font-size-l)/var(--theme-line-height-l-single) var(--theme-font-sans)` | `var(--theme-font-weight-bold) var(--theme-font-size-l)/var(--theme-line-height-l-single) var(--theme-font-sans)` |
| `--theme-text-s` | `var(--theme-font-weight-normal) var(--theme-font-size-s)/var(--theme-line-height-s) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-s)/var(--theme-line-height-s) var(--theme-font-sans)` |
| `--theme-text-s-single` | `var(--theme-font-weight-normal) var(--theme-font-size-s)/var(--theme-line-height-s-single) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-s)/var(--theme-line-height-s-single) var(--theme-font-sans)` |
| `--theme-text-xl` | `var(--theme-font-weight-normal) var(--theme-font-size-xl)/var(--theme-line-height-xl) var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-xl)/var(--theme-line-height-xl) var(--theme-font-sans)` |
| `--theme-text-xs` | `var(--theme-font-weight-normal) var(--theme-font-size-xs)/140% var(--theme-font-sans)` | `var(--theme-font-weight-normal) var(--theme-font-size-xs)/140% var(--theme-font-sans)` |

## Border (28)

| Token | Light | Dark |
|---|---|---|
| `--theme-alarm-bdr-1` | `0.0625rem solid var(--theme-color-alarm)` | `0.0625rem solid var(--theme-color-alarm)` |
| `--theme-alarm-bdr-2` | `0.125rem solid var(--theme-color-alarm)` | `0.125rem solid var(--theme-color-alarm)` |
| `--theme-contrast-bdr-1` | `0.0625rem solid var(--theme-color-contrast-bdr)` | `0.0625rem solid var(--theme-color-contrast-bdr)` |
| `--theme-contrast-bdr-2` | `0.125rem solid var(--theme-color-contrast-bdr)` | `0.125rem solid var(--theme-color-contrast-bdr)` |
| `--theme-critical-bdr-1` | `0.0625rem solid var(--theme-color-critical)` | `0.0625rem solid var(--theme-color-critical)` |
| `--theme-critical-bdr-2` | `0.125rem solid var(--theme-color-critical)` | `0.125rem solid var(--theme-color-critical)` |
| `--theme-dynamic-bdr-1` | `0.0625rem solid var(--theme-color-dynamic)` | `0.0625rem solid var(--theme-color-dynamic)` |
| `--theme-dynamic-bdr-2` | `0.125rem solid var(--theme-color-dynamic)` | `0.125rem solid var(--theme-color-dynamic)` |
| `--theme-info-bdr-1` | `0.0625rem solid var(--theme-color-info)` | `0.0625rem solid var(--theme-color-info)` |
| `--theme-info-bdr-2` | `0.125rem solid var(--theme-color-info)` | `0.125rem solid var(--theme-color-info)` |
| `--theme-neutral-bdr-1` | `0.0625rem solid var(--theme-color-neutral)` | `0.0625rem solid var(--theme-color-neutral)` |
| `--theme-neutral-bdr-2` | `0.125rem solid var(--theme-color-neutral)` | `0.125rem solid var(--theme-color-neutral)` |
| `--theme-primary-bdr-1` | `0.0625rem solid var(--theme-color-primary)` | `0.0625rem solid var(--theme-color-primary)` |
| `--theme-primary-bdr-2` | `0.125rem solid var(--theme-color-primary)` | `0.125rem solid var(--theme-color-primary)` |
| `--theme-soft-bdr-1` | `0.0625rem solid var(--theme-color-soft-bdr)` | `0.0625rem solid var(--theme-color-soft-bdr)` |
| `--theme-soft-bdr-2` | `0.125rem solid var(--theme-color-soft-bdr)` | `0.125rem solid var(--theme-color-soft-bdr)` |
| `--theme-soft-dashed-bdr-1` | `0.0625rem dashed var(--theme-color-soft-bdr)` | `0.0625rem dashed var(--theme-color-soft-bdr)` |
| `--theme-soft-dashed-bdr-2` | `0.125rem dashed var(--theme-color-soft-bdr)` | `0.125rem dashed var(--theme-color-soft-bdr)` |
| `--theme-std-bdr-1` | `0.0625rem solid var(--theme-color-std-bdr)` | `0.0625rem solid var(--theme-color-std-bdr)` |
| `--theme-std-bdr-2` | `0.125rem solid var(--theme-color-std-bdr)` | `0.125rem solid var(--theme-color-std-bdr)` |
| `--theme-success-bdr-1` | `0.0625rem solid var(--theme-color-success)` | `0.0625rem solid var(--theme-color-success)` |
| `--theme-success-bdr-2` | `0.125rem solid var(--theme-color-success)` | `0.125rem solid var(--theme-color-success)` |
| `--theme-warning-bdr-1` | `0.0625rem solid var(--theme-color-warning)` | `0.0625rem solid var(--theme-color-warning)` |
| `--theme-warning-bdr-2` | `0.125rem solid var(--theme-color-warning)` | `0.125rem solid var(--theme-color-warning)` |
| `--theme-weak-bdr-1` | `0.0625rem solid var(--theme-color-weak-bdr)` | `0.0625rem solid var(--theme-color-weak-bdr)` |
| `--theme-weak-bdr-2` | `0.125rem solid var(--theme-color-weak-bdr)` | `0.125rem solid var(--theme-color-weak-bdr)` |
| `--theme-x-weak-bdr-1` | `0.0625rem solid var(--theme-color-x-weak-bdr)` | `0.0625rem solid var(--theme-color-x-weak-bdr)` |
| `--theme-x-weak-bdr-2` | `0.125rem solid var(--theme-color-x-weak-bdr)` | `0.125rem solid var(--theme-color-x-weak-bdr)` |

## Shadow (5)

| Token | Light | Dark |
|---|---|---|
| `--theme-inset-shadow-1` | `inset 0 2px 4px 0 rgba(0,0,0,.1)` | `inset 0 2px 4px 0 rgba(0,0,0,.6)` |
| `--theme-shadow-1` | `0 2px 2px 0 rgba(0,0,0,.2),0 1px 1px 0 rgba(0,0,0,.1)` | `0 2px 2px 0 #000,0 1px 1px 0 rgba(0,0,0,.6)` |
| `--theme-shadow-2` | `-4px 0 8px 0 rgba(0,0,0,.2),4px 0 8px 0 rgba(0,0,0,.2),0 0 16px 0 rgba(0,0,0,.1)` | `-4px 0 8px 0 #000,4px 0 8px 0 #000,0 0 16px 0 rgba(0,0,0,.6)` |
| `--theme-shadow-3` | `0 2px 6px 0 rgba(0,0,0,.2),0 0 8px 0 rgba(0,0,0,.1)` | `0 2px 6px 0 #000,0 0 8px 0 rgba(0,0,0,.6)` |
| `--theme-shadow-4` | `0 0 2px 0 rgba(0,0,0,.2),0 4px 8px 0 rgba(0,0,0,.1),0 12px 18px 0 rgba(0,0,0,.1)` | `0 0 2px 0 #000,0 4px 8px 0 rgba(0,0,0,.6),0 12px 18px 0 rgba(0,0,0,.6)` |

## Misc (1)

| Token | Light | Dark |
|---|---|---|
| `--theme-company-logo` | `company-logo-alt` | `company-logo-alt` |

## Mapping: `ui/src/tokens.css` ↔ iX tokens

37 custom properties found in the current app's `ui/src/tokens.css`. That file's own header comments already record that most of it derives from iX (classic, light schema) on purpose — see the file for the full rationale. This table makes the mapping explicit for grep-ability.

| App token | App value | iX equivalent | Notes |
|---|---|---|---|
| `--chrome-900` | `#0f1619` | `literal (not var)` | iX dark-schema theme-color-1, applied as a literal because the app runs the light schema overall; there is no "dark chrome in a light app" construct in iX |
| `--chrome-800` | `#283236` | `literal (not var)` | iX dark-schema theme-color-2, same reason as --chrome-900 |
| `--chrome-700` | `#3c484d` | `literal (not var)` | iX dark-schema theme-color-3 |
| `--chrome-border` | `#4c5a60` | `literal (not var)` | iX dark-schema theme-color-4 |
| `--chrome-text` | `rgba(245, 252, 255, 0.9)` | `literal (not var)` | iX dark-schema std-text |
| `--chrome-muted` | `rgba(229, 247, 255, 0.65)` | `literal (not var)` | iX dark-schema soft-text |
| `--canvas` | `var(--theme-color-2)` | `--theme-color-2` |  |
| `--surface` | `var(--theme-color-1)` | `--theme-color-1` |  |
| `--surface-2` | `var(--theme-color-2)` | `--theme-color-2` |  |
| `--border` | `var(--theme-color-3)` | `--theme-color-3` |  |
| `--border-2` | `var(--theme-color-4)` | `--theme-color-4` |  |
| `--text-1` | `var(--theme-color-std-text)` | `--theme-color-std-text` |  |
| `--text-2` | `var(--theme-color-soft-text)` | `--theme-color-soft-text` |  |
| `--text-3` | `var(--theme-color-weak-text)` | `--theme-color-weak-text` |  |
| `--accent` | `var(--theme-color-primary)` | `--theme-color-primary` |  |
| `--accent-soft` | `var(--theme-color-primary-10, rgba(0, 110, 147, 0.1))` | `--theme-color-primary-10 (fallback literal)` | no --theme-color-primary-10 token actually exists in classic theme; app supplies a literal fallback |
| `--success` | `var(--theme-color-success)` | `--theme-color-success` |  |
| `--success-soft` | `rgba(44, 133, 0, 0.1)` | — | no --theme-color-success-10 exists; app hand-derives a 10% tint |
| `--warning` | `var(--theme-color-warning-text)` | `--theme-color-warning-text` | deliberately NOT --theme-color-warning (#ffbb00 fails contrast as text on white) |
| `--warning-soft` | `var(--theme-color-warning-10, rgba(255, 187, 0, 0.1))` | `--theme-color-warning-10 (fallback literal)` |  |
| `--danger` | `var(--theme-color-alarm-text)` | `--theme-color-alarm-text` | deliberately NOT --theme-color-alarm, for the same contrast reason as --warning |
| `--danger-soft` | `var(--theme-color-alarm-10, rgba(215, 35, 50, 0.1))` | `--theme-color-alarm-10 (fallback literal)` |  |
| `--ai` | `#7d4dff` | — | subtle violet, AI-feature-only; iX classic theme has no equivalent semantic slot |
| `--ai-soft` | `rgba(125, 77, 255, 0.1)` | — | tint of --ai |
| `--pillar-connect` | `#246b00` | — | derived from --theme-color-success--active (#246b00) but hand-darkened further for AA on a filled pill; not a direct alias |
| `--pillar-collaborate` | `#006b6b` | — | cyan hue kept from pre-iX palette, darkened to clear 4.5:1; no iX source token |
| `--pillar-empower` | `var(--theme-color-primary)` | `--theme-color-primary` | the one pillar color that is a direct alias; already clears AA (4.98:1) |
| `--pillar-pass` | `#5f6672` | — | --theme-color-weak-text was tried and failed AA (2.69:1) as a pill label; replaced with an opaque blue-grey literal |
| `--fs-title` | `23px` | — | no --theme-font-size-* scale used; app keeps its own px scale for Tracxn table density |
| `--fs-section` | `16px` | — | see --fs-title |
| `--fs-body` | `13.5px` | — | see --fs-title |
| `--fs-table` | `12.5px` | — | see --fs-title |
| `--fs-meta` | `11.5px` | — | see --fs-title |
| `--radius` | `6px` | — | iX classic theme (this version) has no public --theme-radius-* scale to alias; component radii are internal to iX components |
| `--topbar-h` | `56px` | — | Tracxn layout geometry, not a color/theme concern |
| `--rail-w` | `68px` | — | Tracxn layout geometry |
| `--sidenav-w` | `236px` | — | Tracxn layout geometry |

### Tokens with no iX equivalent (15)

Pillar colors, AI accent, typography scale and layout geometry are Tracxn/app-specific and will need an explicit decision during migration — either keep as an app-level overlay on top of iX tokens, or redesign onto iX's scale where one gets added upstream.

- `--success-soft` = `rgba(44, 133, 0, 0.1)` — no --theme-color-success-10 exists; app hand-derives a 10% tint
- `--ai` = `#7d4dff` — subtle violet, AI-feature-only; iX classic theme has no equivalent semantic slot
- `--ai-soft` = `rgba(125, 77, 255, 0.1)` — tint of --ai
- `--pillar-connect` = `#246b00` — derived from --theme-color-success--active (#246b00) but hand-darkened further for AA on a filled pill; not a direct alias
- `--pillar-collaborate` = `#006b6b` — cyan hue kept from pre-iX palette, darkened to clear 4.5:1; no iX source token
- `--pillar-pass` = `#5f6672` — --theme-color-weak-text was tried and failed AA (2.69:1) as a pill label; replaced with an opaque blue-grey literal
- `--fs-title` = `23px` — no --theme-font-size-* scale used; app keeps its own px scale for Tracxn table density
- `--fs-section` = `16px` — see --fs-title
- `--fs-body` = `13.5px` — see --fs-title
- `--fs-table` = `12.5px` — see --fs-title
- `--fs-meta` = `11.5px` — see --fs-title
- `--radius` = `6px` — iX classic theme (this version) has no public --theme-radius-* scale to alias; component radii are internal to iX components
- `--topbar-h` = `56px` — Tracxn layout geometry, not a color/theme concern
- `--rail-w` = `68px` — Tracxn layout geometry
- `--sidenav-w` = `236px` — Tracxn layout geometry

