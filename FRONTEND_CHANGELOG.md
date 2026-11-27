# Frontend changelog — Emerald and white revision

Date: 2026-11-27
Branch: `frontend-midnight-blue`

## Changed

- `templates/base.html`: extracted shared inline CSS and the shared runtime JavaScript to cacheable files; added critical/token CSS and cached shared stylesheets, dark-mode prepaint setup, and a labelled theme toggle. Existing SEO metadata, JSON-LD, route URLs, forms, IDs, Bootstrap hooks and PWA script references remain present.
- `templates/index.html`: replaced the visual homepage hero with the two-column Midnight Blue 3D illustration and trust/features strip. Removed unsupported animated course/institution/student counters from visible content; hidden SEO/schema content was left intact.
- `templates/degree.html`: changed the cluster-points explainer video to `preload="none"`; switched the shared favicon to the existing local PWA icon; reduced subsection headings to h2 so the degree page has one h1.
- `static/css/tokens.css`, `critical.css`, `main.css`, `midnight.css`: defined palette and dark tokens, compact above-fold rules, extracted the old shared design rules, and added responsive styling/motion fallbacks.
- `static/js/base-ui.js`: extracted the shared 28,851-byte inline interaction script for caching.
- `static/js/writing.js`: added bounded text reveal, scroll-triggered section-heading reveal, hero type cycle, low-resource static scene fallback, and persistent light/dark theme toggle. Shared CSS and JS are minified into `.min` files by `scripts/build_assets.py` using already-pinned `cssmin`/`jsmin`.
- `static/service-worker.js`: resilient same-origin app-shell/asset caching, root-scoped worker registration, a working accept-update/skip-waiting path, updated cache names, old-cache cleanup, offline HTML fallback, and exclusions for private/transactional pages and APIs.
- `app.py`: refined the existing response hook for gzip of small compressible static files plus no-cache/no-store headers. No route or business logic changed.
- `FRONTEND_AUDIT.md`: includes inventory/baseline from Step 0 and this implementation report.

## Removed

No files or routes were removed. The nonexistent `/static/js/main.js` service-worker cache entry is removed.

## Rebuild and rollback

No dependency was added; run `venv\Scripts\python.exe scripts\build_assets.py` to regenerate minified CSS/JS outputs. The Flask app serves these assets directly. Run locally with the project virtual environment activated and `python app.py` (using the existing `.env` configuration). CSS/JS URLs carry `?v=midnight-20261126`; change the query version when changing those files under the long static cache policy. Review/revert only this implementation's hunks; the project tree contained substantial pre-existing edits and user data. A pre-implementation tracked-tree patch is saved outside the project at `C:\Users\ADMIN\Documents\Codex\2026-11-26\venv-ps-c-users-admin-documents\work\kuccps-pre-midnight-blue-20261126\tracked-working-tree.patch`.

## Verification and open items

Python compile, Node syntax, Jinja parsing of all 66 templates, route smoke tests against an empty fake Mongo database, and CSS brace checks passed. Test-client compressed HTML bodies fell 35.4%–41.7% on `/`, `/degree`, `/guides`, and `/news`; `/chat` is standalone and unchanged. No project test suite, Playwright, or browser was available; local socket binding was denied, so there are no device/browser screenshots or Lighthouse before/after metrics. The legacy Google Fonts, Bootstrap and Font Awesome CDNs remain due existing template/runtime dependencies and failed TLS fetches; local WOFF2 subsets and a local icon sprite are not present. The 36 MB video is on-demand but was not re-encoded because ffmpeg is unavailable. No stage commits were created because git index access was denied and the tree had pre-existing mixed changes.


## Visual direction update — 2026-11-27

The active shared interface and homepage now use the requested white, deep ink navy (#071B2F), and emerald (#137E4E) system. The former Midnight Blue palette and manual/system dark-theme control were removed from the shared shell. The hero copy and calls to action now use “Discover the courses you qualify for,” “Check my eligibility,” and “Explore programmes.” The “courses” word is revealed letter by letter, with reduced-motion support; category cards and hero elements use restrained entrance/hover motion. Added homepage pathway steps, an accessible FAQ, and a KUCCPS placement guidance disclaimer. Course pathway forms and backend assessment logic are unchanged; the homepage presents the steps descriptively and does not create a new wizard.

Latest verification after this visual update: asset minification succeeded with `venv\Scripts\python.exe scripts\build_assets.py`; Jinja parsed all 66 templates; Flask test-client smoke checks passed for the homepage, all six category routes, guides, news, chat, offline, service worker and generated assets (basket returned its existing 302 for unauthenticated access); Python compileall passed. Browser/Lighthouse/device checks remain unavailable in this environment.


## Color consistency and contrast follow-up — 2026-11-27

Fixed an emerald-on-emerald category action label and white-on-white card hover text. Primary actions now use a consistent high-contrast emerald fill with white labels; card title, description, and icon colors remain legible across normal and hover states. Bootstrap primary/success/link tokens now resolve to the same palette. Added the shared token, critical, and theme stylesheets to standalone full-document templates so the palette also reaches chat, guide, offline, and standalone admin/auth/payment pages. Updated the shared asset version to invalidate the previous long-lived CSS cache.

## Hero cleanup and shared template theme — 2026-11-27

Removed the decorative “Course match preview / Illustrative example / Your options, clearly organized” card from the homepage. The hero now uses a single-column layout with a constrained copy width at desktop and mobile breakpoints. Added shared palette rules for tables, dropdowns, accordions, pagination, and footer links. The 37 templates extending `base.html` inherit the shared theme; all 25 standalone full-document templates load the same tokens and theme CSS. The remaining include/component fragments inherit styles from their parent document.

## Course pathway page consistency — 2026-11-27

Unified the visual styling of `/degree`, `/diploma`, `/artisan`, `/kmtc`, `/ttc`, and `/certificate`. Their previously distinct red, orange, purple, cyan and blue palettes now use the shared ink/navy, emerald, light-emerald, white and slate tokens. Shared rules cover pathway heroes, subject groups, grade controls, submit actions, cards, status alerts, accordions and informational sections. Existing form names, IDs, actions, methods, validation scripts and backend submission routes were left intact. The UI/UX Pro Max targeted UX search informed the 46–48px touch controls, spacing, and contrast decisions.

## Compact course-entry pages — 2026-11-27

Simplified Diploma, Artisan, KMTC, TTC, and Certificate pages to a concise pathway heading, one short instruction, and the existing KCSE grade form. Removed the visible overview, benefits, FAQ, success-story, and extended requirements sections from these five pages. Preserved the hidden SEO text/schema, complete form fields, form IDs/actions, and page validation/submission scripts.

## Consistent heading typewriter — 2026-11-27

The shared writing module types the first visible page H1 one character at a time on route load, then holds, erases, and repeats the cycle continuously. Pacing adapts to heading length, punctuation gets a brief pause, and a subtle blinking caret marks the effect. Original inline accent spans are preserved. The heading's complete accessible name remains available to assistive technology, and `prefers-reduced-motion` leaves the original heading immediately visible. The animation pauses while the tab is hidden. No assessment or route behavior changed.

## Homepage section motion and navigation — 2026-11-27

The navigation “Get Started” button now goes to `/#course-categories`. Homepage section headings (Explore programmes, How It Works, Why Choose CourseChecker, and Frequently asked questions) start a continuous type/hold/erase/retype cycle when they enter the viewport. Existing staggered card/step reveals are enabled again, with static visible fallbacks when JavaScript is unavailable or reduced motion is requested.
