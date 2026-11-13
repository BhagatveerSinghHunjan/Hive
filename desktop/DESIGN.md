# HIVE Desktop — Design System

Quiet black + honey SaaS UI. Altitude-like coherence: flat surfaces, thin borders, sparse accent.

## Direction

Near-black field (`#0b0b0b`). Panels are flat `#111` with **1px** white-8% borders and **12px** radius.
Honey is the sole accent — primary CTAs, active nav dot, focus. No glass blur stacks, no honey glow chrome.

**Primary actions** → honey fill, black label  
**Secondary / ghost** → transparent + white-8% border  
**Never** candy blue, purple gradients, or cartoon bee stickers.

## Brand / logo

- File: `desktop/public/logo.svg`
- Sidebar brand row (flat, no chip)
- Keep the mark readable at ~24×24

## Color

| Token | Value | Use |
|---|---|---|
| `--void` | `#0B0B0B` | App field |
| `--surface` | `#111111` | Cards / panels |
| `--surface-2` | `#161616` | Nested cells |
| `--border` | `rgba(255,255,255,0.08)` | Hairlines |
| `--white` | `#FFFFFF` | Titles |
| `--ink` | `#F5F5F5` | Body |
| `--muted` | `#A3A3A3` | Secondary |
| `--faint` | `#737373` | Meta |
| `--honey` | `#F5B800` | Accent / CTA |
| `--ok` | `#3DCF8E` | Connected |
| `--bad` | `#E85D5D` | Deny / error |

Legacy aliases `--glass`, `--line`, `--line-soft` map to surface/border for older rules.

## Spacing

Scale: **8 / 12 / 16 / 24**. Screen padding 24. Card padding 20. Grid gap 16.

## Buttons

1. **Honey** — solid `--honey`, no outer glow  
2. **Ghost** — transparent, `--border`  
3. **Deny** — transparent + soft red border  
Height **32px**, radius **8px**.

## Type

- UI: Bricolage Grotesque  
- Mono: JetBrains Mono  
- Page title ~28px white; body 14; meta 12 muted

## Motifs

Barely-visible honeycomb watermark (2% opacity). Easter eggs unchanged (`buzz` / `nectar` / `queen`, brand 5×).
