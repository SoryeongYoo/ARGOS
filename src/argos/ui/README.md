# ARGOS Design System

**ARGOS** — *Airline Route & Ground Operations System*
An AI-powered **OCC (Operations Control Center)** decision-support tool for an Incheon-hub carrier (modeled on Korean Air). Portfolio project. Python 3.12, Streamlit UI, LangGraph multi-agent backend, OR-Tools optimization, LightGBM prediction.

> 지연 감지 → 전파 시뮬레이션 → 회복 시나리오 3개 자동 생성 → OCC 관리자 최종 승인
> *Delay detection → Propagation simulation → 3 recovery scenarios → OCC manager approval*

This design system captures ARGOS' visual identity: the calm, technical, **dual-language (Korean / English)** aesthetic of an airline operations control center, paired with the **lavender + ink-black** chrome introduced in the official OCC user-flow diagram.

---

## Sources & references

| Source | URL / path | Notes |
|---|---|---|
| GitHub repo | <https://github.com/SoryeongYoo/ARGOS> | Python + Streamlit codebase. Public. |
| Local clone | `ARGOS/` (mounted) | Same as above, optional re-mount via Import menu |
| OCC user flow | `uploads/AI OCC 운항 의사결정 지원 시스템_2026-05-28.png` | Source of the brand purple + dark CTA-pill motif |

> **Browse the repo** — the README, `CLAUDE.md`, and `src/argos/ui/dashboard.py` were the primary inputs for this system. Explore the simulation, optimization, and agent modules for deeper context if you're building production surfaces.

---

## Product context

ARGOS implements the **core OCC workflow** for an airline:

1. **Dashboard (대시보드)** — fleet-wide KPIs, departure schedule, route map
2. **Delay prediction (지연 예측)** — LightGBM `P(delay ≥ 15 min)`
3. **Propagation simulation (전파 시뮬레이션)** — NetworkX DAG of aircraft rotations
4. **Recovery scenarios (회복 시나리오)** — auto-generated *Accept / Swap / Cancel* options
5. **UAM / ACROSS (UAM/ACROSS)** — eVTOL alternate routing through Korean UTM

**Safety primitives are immutable**: FAR 117 crew-duty limits are a hard constraint; every recovery action requires explicit human approval (the LangGraph `human_gate` interrupt).

Surfaces:
- **OCC Dashboard** (`src/argos/ui/dashboard.py`) — Streamlit, two tabs (Operations, UAM/ACROSS). This is the *only* live UI in the codebase today; everything else is service-layer Python.

---

## Content fundamentals

ARGOS speaks in the register of an **airline operations manual**, not consumer SaaS marketing. Voice:

- **Bilingual, Korean-led headings, English-led technical terms.** Korean labels for user-facing categories (`날짜 선택`, `항공편 필터링`, `회복 시나리오`); English for module names, code, ICAO/IATA identifiers, and the product mark (ARGOS, OCC, UAM, ACROSS, FAR 117). The README itself mixes both registers freely — that's the house style.
- **Procedural, declarative.** Short sentences. Active voice. The codebase reads like a checklist: *"기재 재배정 최적화 (CP-SAT ILP). 혼란 발생 편에 기종 호환성과 시간 중복 없는 조건…"*
- **Numbers are tabular and load-bearing.** `161,868건`, `60개 노선`, `58대`. Always show the unit (`min`, `NM`, `ft AGL`, `편`, `명`).
- **No first/second person.** No "we", no "you". Subject is the *system* or the *flight*. Status, not invitation.
- **No emoji in product UI.** The only emoji-adjacent characters used in code are the airplane mark `✈` and arrow glyphs (`→`, `▶`). Even those are sparing. CSS `content` symbols and Unicode arrows OK; emoji ❌.
- **Action language is imperative + short.** Pill buttons in the flowchart read `날짜 선택`, `항공편 선택`, `승인`, `거부/중단`, `시뮬레이션 실행`. Verb + noun, ≤ 8 Hangul characters or 2 English words.
- **Safety-first qualifiers.** Where stakes are high the docs surface the caveat explicitly — *"회복 조치는 반드시 인간의 명시적 승인 후에만 실행됩니다."* / *"FAR 117은 하드 컨스트레인트입니다."* Use the same tone for any new copy.

**Casing.** Sentence case for headers and labels. ALL-CAPS reserved for codes (`ICN`, `RKSI`, `KST`, `CNX`, `KE001`, `HL7xxx`). Eyebrow micro-labels use **UPPERCASE + 0.08em tracking**.

**Code-shaped values are always monospaced** with tabular numerals: flight numbers, registrations, IATA delay codes, UTC timestamps, distances.

---

## Visual foundations

### Color

The palette is **lavender + ink-black on neutral white**. It draws directly from the OCC user-flow diagram:
- Soft **violet** rectangles indicate screens / category headers.
- **Ink-black pills** indicate the operator's interactive actions.
- The background is a quiet near-white.

Primary brand color is `--argos-violet-500` (`#8B5CF6`). The dark CTA color is `--argos-ink-900` (`#16161D`).

A **semantic / operational status** scale layers on top: `--status-ontime` (green), `--status-delay` (amber), `--status-critical` (red), `--status-info` (sky blue). These map 1:1 to flight states in the dashboard. Five **module accents** (`--module-prediction`, `--module-sim`, `--module-recovery`, `--module-uam`, `--module-dashboard`) tag the five OCC workflow stages without competing with status colors.

### Typography

| Family | Use |
|---|---|
| **Noto Sans** (variable, weight 100–900, width 62.5–100%) | UI, body, headings — bilingual Hangul + Latin support |
| **JetBrains Mono** (CDN) | Flight numbers, codes, timestamps, KPI numerals, tabular data |

Scale: `40 / 28 / 22 / 18 / 15 / 14 / 13 / 12 / 11`. Body is **14 px**; tables are **13 px**; dashboard KPI numerals run **40 px** with tabular figures. Headings tighten letter-spacing by `-0.02em`; eyebrows use `+0.08em` UPPERCASE.

### Spacing & layout

`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64` px scale. The dashboard layout idiom is a **2- or 3-column grid** at the top (map / schedule / KPI), then a full-width simulation panel, then a chart strip — explicit, calm, no marketing carousels. Pages always have a **left sidebar** for filters and a **top tab bar** for module switching (matches the Streamlit defaults the live dashboard uses).

### Borders, radii, surfaces

Cards and panels: `--radius-lg` (12 px), `1px` hairline border in `--border-1`, white surface. **Buttons** are either pill (`--radius-pill`, OCC action style from the flowchart) or square-cornered `--radius-md`. **Inputs** are `--radius-md` with a 1.5 px focused border. Map / chart containers get `--radius-lg` and a soft `--bg-2` background tint.

### Backgrounds & imagery

The product backdrop is mostly flat white (`--bg-1`) with a lavender-tinted secondary surface (`--bg-tint = --argos-violet-100`) used for highlights, the sidebar header, empty states, and category chips. **No gradients in the chrome.** When color does shade, it's a single soft purple wash — never a multi-stop rainbow gradient.

Imagery is **data, not photography**: Plotly choropleths, geo line-traces, histograms, NetworkX graphs over OpenStreetMap. When real imagery is used it stays **muted and aerial** — runway tarmac, terminal interiors, sky — never warm hero photography.

### Animation & state

Motion is **utilitarian** — `--dur-fast: 140ms` for hover, `--dur-base: 200ms` for menus and tabs, `--dur-slow: 320ms` for panel reveals. Easing is `cubic-bezier(0.2, 0, 0, 1)` (standard) with a slightly more emphasized variant for primary CTAs. No bounces. No spring physics. No celebratory micro-interactions.

**Hover** = subtle background tint shift (e.g. ink-pill → 12% lighter, violet button → `--argos-violet-600`). **Press** = darker fill, no scale shrink in data tables; mild `scale(0.98)` on pill buttons. **Focus** = `--focus-ring` violet glow (`box-shadow 0 0 0 3px rgba(139,92,246,0.35)`) — required because controllers may keyboard-navigate.

### Shadows & elevation

Three shadow tokens: `--shadow-1` (resting card), `--shadow-2` (raised), `--shadow-3` (modal / scenario card). Pills have a dedicated `--shadow-pill`. Brand-tinted `--shadow-violet` is reserved for the *primary* CTA on light backgrounds — never used as decoration.

### Transparency & blur

Mostly avoided. The only places translucency appears: status-color backgrounds (use the `*-bg` token, which is the hue at ~10% saturation — already opaque, not `alpha`), focus rings (`rgba(139,92,246,0.35)`), and shadow casts. No glassmorphism, no backdrop-filter. Operational dashboards need crisp legibility.

### Fixed elements

- The **sidebar** is always present, ~280 px wide, white surface, divided by hairline borders.
- The **tab bar** sits at the top of the main column; tabs are square-cornered with an underline indicator in `--argos-violet-500`.
- A **footer hint** (e.g. `DB: 161,868 flights loaded`) sits at the bottom of the sidebar in `--fg-3`.

### Color vibe of imagery

Cool — leaning to neutral. No warm filters. Maps default to gray landmasses and **alice-blue oceans** (this is what the Streamlit dashboard codes today). When color is added to a map, it tracks status: red for delayed traces, sky-blue for normal, gold star for the ICN hub.

---

## Iconography

The live ARGOS codebase ships **no icon font, no SVG icon set, no PNG icon assets**. The Streamlit dashboard uses a small number of Unicode glyphs inline (`✈ ▶ → ✅ ❌`) and emoji-rendered status hints (`:green[…]`, `:red[…]`).

**This design system substitutes [Lucide Icons](https://lucide.dev)** (loaded from CDN) as the canonical icon set — same stroke weight (1.5 px), same outlined style, matched to the calm/technical voice. *(Flagging this substitution — happy to swap to a different set if Korean Air or 인천국제공항공사 has an internal mark library.)*

Rules:
- **Stroke 1.5 px, outline style only.** No solid/duotone variants in the UI.
- **Icon size cadence:** 14 px (in-line with body), 16 px (form fields, table actions), 20 px (sidebar nav), 24 px (KPI module mark).
- **Color follows context:** `--fg-2` by default, `--fg-1` on hover, `--argos-violet-500` for the active state, status-token color when the icon is annotating a status (e.g. `AlertTriangle` in `--status-delay`).
- **No emoji in product UI.** The README uses some inline Unicode arrows; that's the limit.

**Logo / wordmark.** ARGOS has no fixed visual logo in the codebase. The project mark in the dashboard is the literal string `ARGOS` followed by `Airline Route & Ground Operations System`. This design system provides a typographic logo lockup (Noto Sans, 700 weight, `-0.02em` tracking) plus a violet airplane glyph as the favicon. See `assets/logo-argos.svg` and the Brand cards in the Design System tab.

---

## Index

| File | What it is |
|---|---|
| `README.md` | This document |
| `SKILL.md` | Cross-compatible Agent Skill entry point |
| `colors_and_type.css` | All design tokens — colors, type, spacing, radii, shadows, motion |
| `fonts/` | Noto Sans variable font files (uploaded by user) |
| `assets/` | Logo, glyph, sample imagery |
| `preview/` | HTML cards that populate the Design System tab |
| `ui_kits/occ_dashboard/` | The OCC dashboard UI kit — index + JSX components (Operations + UAM/ACROSS tabs, interactive simulation + scenario approval) |

---

## Caveats & known substitutions

1. **Icon set substitution:** Lucide via CDN, since the codebase has no native iconography. Flag for the user.
2. **No mono font shipped:** JetBrains Mono pulled from Google Fonts CDN. The user did not upload one.
3. **No production logo:** the wordmark + glyph are typographic, not a finalized brand mark.
4. **One product surface only:** Streamlit OCC dashboard is the only live UI. UAM/ACROSS is the second tab inside it, not a separate product. Marketing surfaces, mobile apps, etc. do not exist and have not been speculatively designed.
