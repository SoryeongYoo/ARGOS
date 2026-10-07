---
name: argos-design
description: Use this skill to generate well-branded interfaces and assets for ARGOS, an AI-powered OCC (Operations Control Center) flight decision-support system for an Incheon-hub carrier — either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the `README.md` file within this skill, and explore the other available files (`colors_and_type.css` for all design tokens, `ui_kits/occ_dashboard/` for the dashboard components, `preview/` for visual specimens, `assets/` for the logo and glyph).

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

Key things to honor:
- **Lavender + ink-black** palette on neutral white. Violet 500 (`#8B5CF6`) primary; ink 900 (`#16161D`) for action pills.
- **Bilingual, Korean-led** UI copy; **English** for codes/modules. Procedural, no emoji, safety-first qualifiers.
- **Noto Sans** for UI, **JetBrains Mono** for all codes/numerals/timestamps (tabular figures).
- **Operational status colors** map to flight states (on-time/delay/critical/info). Don't invent new hues.
- **Lucide** icons, 1.5px outline (substitution — flag if a real mark library exists).

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.
