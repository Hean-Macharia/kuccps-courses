# SEO architecture and maintenance

Updated: 2026-11-27

## Current application and canonical host

Courses Checker is a Flask/Jinja application. Public pages are rendered by Flask templates; the canonical origin is `https://www.studentsplacement.co.ke`. Requests to the apex host and HTTP variants are redirected to HTTPS on `www`. Canonicals are generated with `get_canonical_url()` and exclude query strings. Legacy guide aliases redirect to their current guide URLs.

Private result, payment, basket, account, and administrator views must remain access-controlled and must not be indexed. `robots.txt` rules are crawl guidance only; authorization and no-store response handling are the privacy controls. Do not put private pages or student data in XML sitemaps, analytics, public structured data, or logs intended for SEO.

## Keyword strategy

See [`keyword_research.md`](keyword_research.md) for the current intent-to-page map. It intentionally reports no search volumes, ranking positions, or difficulty estimates because no Search Console, Bing Webmaster, or Keyword Planner exports were available. Use Search Console/Bing query exports to validate demand and refresh the map; never turn guessed phrases into volume claims or repetitive hidden copy.

Each topic has one primary page: homepage for course checking by KCSE grades; category routes for degree, diploma, certificate, KMTC, artisan, and TTC pathways; and guides for application steps, admission requirements, and cluster-point terminology. Course and admission details change; link to official KUCCPS or institution sources and date-check time-sensitive claims.

## Metadata and structured data

- Shared `templates/base.html` supplies page descriptions, canonical, robots, Open Graph, Twitter, and optional verification tags for templates that extend it.
- Individual public routes supply their title and description in Flask route context or a template title block.
- Standalone pages (including chat and some account/system pages) maintain their own head metadata; review them when their copy or route changes.
- Use structured data only for accurate, visible content. Homepage organization/application and page breadcrumb markup are maintained in templates. Do not add `Course`, review/rating, FAQ, HowTo, affiliation, date, or author claims unless they are accurate and supported by visible content and current Google policies.
- A schema block is not a guarantee of a rich result. Validate representative rendered pages with Google's Rich Results Test and Schema Markup Validator after deployment.

## Sitemaps and robots

- `/robots.txt` references `/sitemap-index.xml`.
- `/sitemap-index.xml` lists `/sitemap.xml` (core public pages) and `/sitemap-guides.xml` (published guides).
- Sitemap routes are implemented in `app.py`; include only canonical public URLs that return indexable success responses. Do not synthesize `lastmod` from the current date. Add a true modification timestamp only when maintained by the publishing workflow.
- There are no public course-detail URLs in the current route inventory. Add course or institution URLs only if a real public detail route exists and uses genuine catalogue data.
- After deployment, inspect each sitemap with an XML parser and submit the index in Search Console/Bing Webmaster yourself. Code cannot submit or verify ownership on your behalf.

## Verification and analytics configuration

Copy optional values into the deployment environment (do not commit secret tokens):

- `GOOGLE_SITE_VERIFICATION`: token from Search Console's HTML meta-tag method.
- `BING_SITE_VERIFICATION`: token from Bing Webmaster Tools' meta-tag method.
- `GOOGLE_ANALYTICS_ID`: GA4 measurement ID (`G-...`); omit to disable Analytics.

Analytics is optional and is not loaded on private result, payment, dashboard, or admin routes. The page-view URL uses the query-free canonical URL. Assessment-start and assessment-submit events send only the pathway category; handlers never inspect or transmit form values. Search, registration, and course-detail events are not wired because those corresponding public workflows are not present in the inspected frontend. Do not add events containing student names, index numbers, grades, email, phone, payment references, or free-text queries. Add an appropriate consent/privacy flow if required by the deployment's legal obligations before enabling analytics.

Google Search Console verification, Bing site verification, GA4 property setup, sitemap submission, indexing, and rankings are external account actions. They are not claimed as completed by these code changes.

## Performance and cache policy

The Flask response hook gzips eligible text responses. Query-versioned static assets may be cached for one year as immutable; unversioned static names receive a short revalidation window. HTML is revalidated and sensitive pages/POST responses are `no-store`. When editing a long-lived asset URL, bump its `v` query value. Keep user-specific, payment, admin, and API content out of shared caches.

## Editorial workflow

1. Confirm claims against official KUCCPS, institution, or government sources. Keep a source link and date checked in the editor's change notes.
2. Use one clear title and H1 for the page intent; write a distinct description that accurately summarizes visible content.
3. Link relevant category pages and guides with descriptive anchor text.
4. Do not add course requirements, placement dates, costs, cut-offs, ratings, partnerships, or institutional claims unless verifiable and current.
5. Preview mobile layout and rendered HTML. Check for one H1, working links, meaningful image alt text, correct canonical, and no accidental student data in public output.
6. Run the SEO route/sitemap/render checks listed below before deployment.

## Verification checklist and commands

From the project root with its virtual environment active:

```powershell
python -m compileall app.py guide_routes.py
# Run the project's test suite if pytest and tests are present.
python -m pytest
```

At the time of this update, this checkout contains no test suite and its project virtual environment does not have `pytest`; the verification above therefore relies on compile checks and Flask test-client smoke tests unless a test suite is added.

Use the Flask test client or a local browser to verify `/`, all six category pages, `/guides`, each sitemap URL, `/robots.txt`, a guide alias redirect, a normal 404, and a private page's `noindex`/`no-store` behavior. Parse XML with an XML parser; parse rendered JSON-LD as JSON; inspect canonical/description/title and verify no private page appears in sitemaps. Run Lighthouse on representative mobile routes after deployment and record actual values; do not report unrun metrics.

## Deployment and external follow-up

Deploy through the existing Render/Gunicorn workflow and preserve the current environment settings. After a successful deployment, verify HTTPS/apex redirects, sitemap and robots responses, Search Console/Bing verification, analytics configuration, and page rendering on production. Request indexing through the relevant webmaster consoles. Search engines decide when and whether to index pages; no SEO implementation can guarantee a ranking.
