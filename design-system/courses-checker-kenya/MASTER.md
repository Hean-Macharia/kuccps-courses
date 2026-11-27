# Courses Checker Kenya — Frontend Design System

This project uses Flask/Jinja templates and Bootstrap with existing JavaScript interactions. Keep the current server-rendered routes and form field contracts. This file records the project-specific adaptation of UI/UX Pro Max search guidance; do not add mock admissions data or client-side eligibility calculations.

## Visual direction

Professional academic guidance: precise, calm, approachable, and Kenyan-context aware. Use the existing KUCCPS identity and logo as supplied. The generated search recommended Minimalism for education tools and a readable professional sans pairing. The LMS palette search matched education teal and grade semantics; this project adapts those findings to the requested academic navy/green identity.

## Colors

- Navy primary: `#18345B`; deep navy: `#122746`; blue accent: `#2D5B8C`.
- Academic green: `#176B4A`; pale green: `#E8F4ED`.
- Amber: `#A96F13` on pale amber `#FFF5DD` for caution/borderline states.
- Qualified/success: `#176B4A`; danger: `#B4233A` with pale red surface `#FCECEE`.
- Page: `#F4F7FB`; card: `#FFFFFF`; text: `#17253A`; muted: `#58677A`; border: `#D9E1EA`.
- Keep 4.5:1 contrast for body text. Never use color alone for eligibility status.

## Typography and layout

Use Lexend for headings and Source Sans 3 for body text (UI/UX Pro Max “Corporate Trust” pairing), with system fallbacks. Body text starts at 16px; line-height 1.5 or more. Use an 8px spacing rhythm, max content width around 1280px, responsive gutters, and 12–18px radii. Prefer clean surfaces, restrained shadows, and no decorative blur over reading surfaces.

## Components and interaction

- One clear primary action per page; secondary controls stay visually quieter.
- Form labels remain visible; errors and help text stay close to fields.
- Inputs and buttons have at least 44px touch height and visible `:focus-visible` rings.
- Search/filter controls keep their existing IDs, names, data attributes, handlers, and submit behavior.
- Qualification status always includes text and/or an icon. Do not derive it in the browser.
- Motion is restrained (150–280ms), supports `prefers-reduced-motion`, and never gates content.
- Use semantic headings, skip links, keyboard-operable menus/dialogs, and responsive tables/cards.

## Page pattern

Homepage: value proposition → real course-checker action → supported pathways → how it works → benefits → FAQ → official placement disclaimer/contact. Do not use invented review scores, testimonials, institution counts, eligibility results, or placement guarantees.

Assessment and results: preserve current grade fields, cluster fields, server POST routes, session behavior, actual backend results, filters, basket/payment controls, and result templates. Visual restyling only.

Admin and account/payment pages: maintain existing access controls and actions; style existing data as clear dashboards, forms, and responsive tables without fabricating statistics or hiding controls.
