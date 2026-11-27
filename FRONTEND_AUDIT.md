# Frontend audit and performance baseline

**Date:** 2026-11-26  |  **Audit base:** `3a68422`  |  **Active implementation branch:** `frontend-midnight-blue`  |  **Stack:** Flask + Jinja2 + Bootstrap 5 + MongoDB/PyMongo

## Scope and safety

This is a Step 0 audit only. No application source, route, business rule, session, payment, database or PWA code was modified in the audit. The audit was first collected on `frontend-rebuild`; `frontend-midnight-blue` was then created from the same `3a68422` base for this implementation. Both branches carry the pre-existing local changes. No reset, stash, cleanup or checkout of user data was performed. The audit document and baseline table are the only new audit outputs. Do not commit or revert the existing dirty tree as part of later frontend work without first preserving and reviewing those changes.

### Existing working-tree state at audit start

At audit start, the dirty tree had 44 already-modified tracked files and 19 untracked entries. Existing changes include backend/deployment files (`app.py`, `courses.py`, `Procfile`, `render.yaml`, `requirements.txt`, `robots.txt`), many templates/assets, and generated/user-data areas such as `flask_session/`, `work/`, payment-issue uploads and a generated PDF. They are pre-existing and have been preserved. Because these changes mix frontend, backend, deployment, data and generated artifacts, later implementation must not treat the tree as clean or make broad reset/stash operations.

During the isolated local app import used for response sampling, startup output included a truncated provider-key preview. The preview is deliberately omitted here; treat application startup logs as sensitive. Addressing that backend log is outside this frontend-only audit scope.

## Architecture and backend integration context

- Server-rendered Flask/Jinja application; 66 HTML templates in this checkout. 37 templates directly extend `templates/base.html`; the remaining 29 are standalone pages or include/component fragments. The actual guides route renders `templates/guides/guides_index.html`; the similarly named root `templates/guides_index.html` is a separate legacy/standalone template.
- Public grade flows remain the six existing paths: degree, diploma, KMTC, certificate, artisan and TTC. Results, basket, payment, news, guides and chat are server-rendered routes. Frontend forms must continue posting to the existing route and preserve their Jinja/session hooks.
- `app.py` is 509,952 bytes and contains most routes; `courses.py`, `basket.py` and `guide_routes.py` provide supporting route/service code. MongoDB connection and payment/session flows are backend-owned.
- The working tree already contains custom gzip and cache middleware in `app.py`; no `Flask-Compress` package is listed. `SEND_FILE_MAX_AGE_DEFAULT` is already 31,536,000 seconds. Current response middleware marks static files `public, max-age=31536000, immutable`, compresses eligible text responses when the client advertises gzip, and marks admin/mutation responses no-store. This audit did not alter it.
- Deployment definitions present: `Procfile`, `render.yaml`, `fly.toml`, `koyeb.yaml`, and `Dockerfile`. These files are dirty at audit start and were not changed.

## Page/template inventory

The inventory below includes all 66 templates, including admin pages and partials. Direct inheritance and page-specific asset links are listed separately from the common base resources. Pages extending `base.html` receive the base stylesheet/font/icon/CDN resources unless a page overrides a block.

| Template | Classification | Extends |
| --- | --- | --- |
| templates/about.html | standalone | — |
| templates/admin_ai_stats.html | standalone | — |
| templates/admin_cached_answers.html | standalone | — |
| templates/admin_clear_cache.html | extends base | base.html |
| templates/admin_create_news.html | standalone | — |
| templates/admin_dashboard.html | standalone | — |
| templates/admin_edit_news.html | standalone | — |
| templates/admin_financial_reports.html | standalone | — |
| templates/admin_login.html | standalone | — |
| templates/admin_manual_activation.html | standalone | — |
| templates/admin_missing_courses.html | standalone | — |
| templates/admin_news.html | standalone | — |
| templates/admin_payment_issues.html | extends base | base.html |
| templates/admin_payment_management.html | standalone | — |
| templates/admin_payments.html | standalone | — |
| templates/admin_regenerate_degree.html | standalone | — |
| templates/admin_system_health.html | standalone | — |
| templates/admin_system_monitoring.html | standalone | — |
| templates/admin_users.html | standalone | — |
| templates/artisan.html | extends base | ./base.html |
| templates/artisan_results.html | extends base | base.html |
| templates/auth.html | extends base | ./base.html |
| templates/base.html | standalone | — |
| templates/basket.html | extends base | base.html |
| templates/certificate.html | extends base | ./base.html |
| templates/certificate_results.html | extends base | base.html |
| templates/chat.html | standalone | — |
| templates/collection_results.html | extends base | base.html |
| templates/components/install_prompt.html | partial | — |
| templates/contact.html | standalone | — |
| templates/degree.html | extends base | ./base.html |
| templates/degree_results.html | extends base | base.html |
| templates/diploma.html | extends base | ./base.html |
| templates/diploma_results.html | extends base | base.html |
| templates/enter_details.html | extends base | ./base.html |
| templates/google-search-console-verification.html | standalone | — |
| templates/guides/artisan_courses.html | extends base | base.html |
| templates/guides/base_guide.html | extends base | base.html |
| templates/guides/certificate_courses.html | extends base | base.html |
| templates/guides/cluster_points.html | extends base | base.html |
| templates/guides/diploma_courses.html | extends base | base.html |
| templates/guides/guides_index.html | extends base | base.html |
| templates/guides/kcse_admission.html | extends base | base.html |
| templates/guides/kmtc_courses.html | extends base | base.html |
| templates/guides/kuccps_application.html | extends base | base.html |
| templates/guides/kuccps_check.html | extends base | base.html |
| templates/guides/scholarships.html | extends base | base.html |
| templates/guides/ttc_courses.html | extends base | base.html |
| templates/guides_index.html | standalone | — |
| templates/includes/flash_messages.html | partial | — |
| templates/index.html | extends base | ./base.html |
| templates/kmtc.html | extends base | ./base.html |
| templates/kmtc_results.html | extends base | base.html |
| templates/manual_activation_request.html.html | standalone | — |
| templates/news.html | extends base | ./base.html |
| templates/news_article.html | extends base | base.html |
| templates/offline.html | standalone | — |
| templates/payment.html | extends base | base.html |
| templates/payment_issue.html | extends base | base.html |
| templates/payment_wait.html | standalone | — |
| templates/results.html | extends base | base.html |
| templates/seo_meta.html | standalone | — |
| templates/ttc.html | extends base | ./base.html |
| templates/user-guide.html | standalone | — |
| templates/user_info.html | extends base | base.html |
| templates/verified_dashboard.html | extends base | base.html |

### Shared resources from `base.html`

- Inline `<style>`: 48,390 bytes in one block; inline `<script>`: 35,175 bytes in two blocks (the raw script-block total can include JSON-LD data). The full template is 133,088 bytes.
- Bootstrap 5.3.3 CSS and JS bundle from jsDelivr; Font Awesome 6.5.0 full `all.min.css` from cdnjs; Google Fonts CSS for Syne (400–800) and DM Sans (300–600/italic) and `fonts.gstatic.com`. Remote payload sizes are not measured in this local/offline audit.
- Local base dependencies: `/static/js/offline-storage.js` (9,124 bytes), `/static/js/pwa.js` (3,095 bytes), manifest and 152px touch icon. The base also references an external Icons8 favicon. The rendered test-client pages include 3rd-party asset URLs but do not fetch them.

### Page-specific resource links

| Template | Direct page-only CSS/JS/CDN references |
| --- | --- |
| templates/about.html | https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js |
| templates/admin_ai_stats.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css |
| templates/admin_cached_answers.html | https://cdn.tailwindcss.com |
| templates/admin_clear_cache.html | shared base stack |
| templates/admin_create_news.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/summernote@0.8.18/dist/summernote-lite.min.css, https://code.jquery.com/jquery-3.6.0.min.js, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js, https://cdn.jsdelivr.net/npm/summernote@0.8.18/dist/summernote-lite.min.js |
| templates/admin_dashboard.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/admin_edit_news.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js, https://cdn.jsdelivr.net/npm/summernote@0.8.18/dist/summernote-lite.min.js |
| templates/admin_financial_reports.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/admin_login.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css |
| templates/admin_manual_activation.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/admin_missing_courses.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css |
| templates/admin_news.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/admin_payment_issues.html | shared base stack; https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/admin_payment_management.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/chart.js, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/admin_payments.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css |
| templates/admin_regenerate_degree.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/admin_system_health.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css |
| templates/admin_system_monitoring.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/admin_users.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css |
| templates/artisan.html | shared base stack; /static/styles-01.css |
| templates/artisan_results.html | shared base stack |
| templates/auth.html | shared base stack |
| templates/base.html | https://www.kuccpscourses.co.ke/, /static/icons/icon-152x152.png, https://img.icons8.com/color/96/000000/graduation-cap.png, https://fonts.googleapis.com, https://fonts.gstatic.com, https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&display=swap, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js, /static/js/offline-storage.js, /static/js/pwa.js |
| templates/basket.html | shared base stack |
| templates/certificate.html | shared base stack; /static/styles-01.css |
| templates/certificate_results.html | shared base stack |
| templates/chat.html | https://www.kuccpscourses.co.ke/chat, https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css, https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap, /static/icons/icon-192x192.png, https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js |
| templates/collection_results.html | shared base stack; https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css |
| templates/contact.html | https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js |
| templates/degree.html | shared base stack; /static/styles-01.css, /static/videos/cluster-points.mp4 |
| templates/degree_results.html | shared base stack |
| templates/diploma.html | shared base stack; /static/styles-01.css |
| templates/diploma_results.html | shared base stack |
| templates/enter_details.html | shared base stack |
| templates/guides/artisan_courses.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/base_guide.html | shared base stack |
| templates/guides/certificate_courses.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/cluster_points.html | shared base stack; /static/images/guide-banner.jpg, /static/images/cluster-points-howto.jpg |
| templates/guides/diploma_courses.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/guides_index.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/kcse_admission.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/kmtc_courses.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/kuccps_application.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/kuccps_check.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/scholarships.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides/ttc_courses.html | shared base stack; /static/images/guide-banner.jpg |
| templates/guides_index.html | /static/css/style.css, /static/css/guides.css |
| templates/index.html | shared base stack; https://www.studentsplacement.co.ke/ |
| templates/kmtc.html | shared base stack; /static/styles-01.css |
| templates/kmtc_results.html | shared base stack |
| templates/manual_activation_request.html.html | https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css, https://kit.fontawesome.com/your-font-awesome-kit.js, https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js |
| templates/news.html | shared base stack |
| templates/news_article.html | shared base stack; /static/images/og-image.jpg |
| templates/offline.html | https://www.kuccpscourses.co.ke/offline |
| templates/payment.html | shared base stack |
| templates/payment_issue.html | shared base stack |
| templates/results.html | shared base stack |
| templates/ttc.html | shared base stack; /static/styles-01.css |
| templates/user-guide.html | https://www.kuccpscourses.co.ke/user-guide, https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css, https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css, https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js |
| templates/user_info.html | shared base stack |
| templates/verified_dashboard.html | shared base stack |

### Local CSS and JS files

Files without template references may be stale or loaded only by a runtime path; verify before deleting. The `app-redesign.css` and `ui-motion.js` files exist in this checkout but are not linked by `base.html` or a template found by filename search.

| Asset | Bytes | Template reference(s) |
| --- | --- | --- |
| static/css/app-redesign.css | 30,259 | no template reference found |
| static/css/chat.css | 10,176 | no template reference found |
| static/css/guides.css | 13,280 | templates/guides_index.html |
| static/css/styles-01.css | 0 | templates/artisan.html, templates/certificate.html, templates/degree.html, templates/diploma.html, templates/kmtc.html, templates/ttc.html |
| static/css/styles.css | 6,292 | no template reference found |
| static/js/chat.js | 9,678 | no template reference found |
| static/js/offline-storage.js | 9,124 | templates/base.html |
| static/js/pwa.js | 3,095 | templates/base.html |
| static/js/script.js | 17,965 | no template reference found |
| static/js/ui-motion.js | 2,094 | no template reference found |
| static/service-worker.js | 6,481 | templates/base.html |

### Inline block byte inventory

the following sizes are UTF-8 bytes of each complete `<style>` or inline `<script>` block per template; script totals include any non-JavaScript script types such as JSON-LD. Zero values are omitted.

| Template | Style blocks | Style bytes | Inline script blocks | Inline script bytes |
| --- | --- | --- | --- | --- |
| templates/about.html | 1 | 8075 | 2 | 2110 |
| templates/admin_ai_stats.html | 0 | 0 | 1 | 503 |
| templates/admin_cached_answers.html | 0 | 0 | 1 | 1816 |
| templates/admin_clear_cache.html | 1 | 487 | 1 | 770 |
| templates/admin_create_news.html | 1 | 491 | 1 | 1815 |
| templates/admin_dashboard.html | 1 | 2043 | 1 | 9076 |
| templates/admin_edit_news.html | 0 | 0 | 1 | 1815 |
| templates/admin_financial_reports.html | 1 | 1304 | 0 | 0 |
| templates/admin_login.html | 1 | 274 | 0 | 0 |
| templates/admin_manual_activation.html | 1 | 2285 | 1 | 8179 |
| templates/admin_missing_courses.html | 1 | 2545 | 1 | 19828 |
| templates/admin_news.html | 1 | 979 | 1 | 304 |
| templates/admin_payment_issues.html | 1 | 1339 | 1 | 17263 |
| templates/admin_payment_management.html | 1 | 766 | 1 | 3517 |
| templates/admin_regenerate_degree.html | 1 | 1137 | 1 | 16494 |
| templates/artisan.html | 1 | 9606 | 4 | 8251 |
| templates/artisan_results.html | 1 | 2046 | 1 | 2709 |
| templates/base.html | 1 | 48390 | 2 | 35175 |
| templates/basket.html | 1 | 2371 | 1 | 9651 |
| templates/certificate.html | 1 | 9704 | 4 | 8334 |
| templates/certificate_results.html | 1 | 1198 | 1 | 2129 |
| templates/chat.html | 1 | 16432 | 5 | 25136 |
| templates/collection_results.html | 2 | 4940 | 1 | 17743 |
| templates/components/install_prompt.html | 1 | 1237 | 1 | 1981 |
| templates/contact.html | 1 | 7194 | 2 | 1800 |
| templates/degree.html | 1 | 3654 | 2 | 4595 |
| templates/degree_results.html | 1 | 1045 | 2 | 2464 |
| templates/diploma.html | 1 | 9606 | 4 | 8131 |
| templates/diploma_results.html | 1 | 771 | 2 | 3015 |
| templates/enter_details.html | 0 | 0 | 1 | 684 |
| templates/guides/artisan_courses.html | 1 | 12055 | 3 | 3598 |
| templates/guides/base_guide.html | 1 | 1292 | 0 | 0 |
| templates/guides/certificate_courses.html | 1 | 12055 | 3 | 3654 |
| templates/guides/cluster_points.html | 1 | 13612 | 4 | 7531 |
| templates/guides/diploma_courses.html | 1 | 12339 | 3 | 3489 |
| templates/guides/guides_index.html | 1 | 9379 | 3 | 4740 |
| templates/guides/kcse_admission.html | 1 | 13188 | 3 | 5363 |
| templates/guides/kmtc_courses.html | 1 | 11279 | 3 | 2975 |
| templates/guides/kuccps_application.html | 1 | 9836 | 3 | 5091 |
| templates/guides/kuccps_check.html | 1 | 9583 | 2 | 1059 |
| templates/guides/scholarships.html | 1 | 11222 | 3 | 5164 |
| templates/guides/ttc_courses.html | 1 | 11279 | 3 | 2949 |
| templates/guides_index.html | 0 | 0 | 1 | 399 |
| templates/includes/flash_messages.html | 1 | 2104 | 1 | 1286 |
| templates/index.html | 1 | 19859 | 4 | 9792 |
| templates/kmtc.html | 1 | 9704 | 4 | 8086 |
| templates/kmtc_results.html | 1 | 1723 | 1 | 2257 |
| templates/manual_activation_request.html.html | 1 | 740 | 1 | 1471 |
| templates/news.html | 1 | 2853 | 2 | 13595 |
| templates/news_article.html | 0 | 0 | 1 | 854 |
| templates/offline.html | 1 | 1915 | 2 | 1049 |
| templates/payment.html | 1 | 1333 | 1 | 5897 |
| templates/payment_issue.html | 1 | 472 | 1 | 3500 |
| templates/payment_wait.html | 1 | 11215 | 1 | 9467 |
| templates/results.html | 1 | 212 | 4 | 6776 |
| templates/ttc.html | 1 | 9613 | 4 | 8233 |
| templates/user-guide.html | 1 | 6350 | 2 | 1825 |
| templates/verified_dashboard.html | 1 | 4593 | 1 | 3339 |

## Bootstrap component and icon usage

template-level class usage was searched across public, guides, chat, and admin templates. Grid is widely used. Modals, dropdowns, collapse, accordions, alerts, progress, toasts and spinners are in active use and therefore cannot be removed from public pages without replacing their behavior. Bootstrap component names are sometimes used only in JavaScript or ARIA, so counts below indicate references, not unique runtime instances.

| Bootstrap component/class family | Templates containing it |
| --- | --- |
| Grid/layout | templates/about.html, templates/admin_ai_stats.html, templates/admin_clear_cache.html, templates/admin_create_news.html, templates/admin_dashboard.html, templates/admin_edit_news.html, templates/admin_financial_reports.html, templates/admin_login.html, templates/admin_manual_activation.html, templates/admin_missing_courses.html, templates/admin_news.html, templates/admin_payment_issues.html, templates/admin_payment_management.html, templates/admin_payments.html, templates/admin_regenerate_degree.html, templates/admin_system_health.html, templates/admin_system_monitoring.html, templates/admin_users.html, templates/artisan.html, templates/artisan_results.html, templates/auth.html, templates/base.html, templates/basket.html, templates/certificate.html, templates/certificate_results.html, templates/chat.html, templates/collection_results.html, templates/contact.html, templates/degree.html, templates/degree_results.html, templates/diploma.html, templates/diploma_results.html, templates/enter_details.html, templates/guides/artisan_courses.html, templates/guides/base_guide.html, templates/guides/certificate_courses.html, templates/guides/cluster_points.html, templates/guides/diploma_courses.html, templates/guides/guides_index.html, templates/guides/kcse_admission.html, templates/guides/kmtc_courses.html, templates/guides/kuccps_application.html, templates/guides/kuccps_check.html, templates/guides/scholarships.html, templates/guides/ttc_courses.html, templates/guides_index.html, templates/includes/flash_messages.html, templates/index.html, templates/kmtc.html, templates/kmtc_results.html, templates/manual_activation_request.html.html, templates/news.html, templates/news_article.html, templates/offline.html, templates/payment.html, templates/payment_issue.html, templates/results.html, templates/ttc.html, templates/user-guide.html, templates/user_info.html, templates/verified_dashboard.html |
| Modal | templates/admin_cached_answers.html, templates/admin_manual_activation.html, templates/admin_news.html, templates/admin_payment_issues.html, templates/admin_payment_management.html, templates/admin_regenerate_degree.html, templates/base.html, templates/chat.html, templates/index.html, templates/news.html, templates/payment.html, templates/user-guide.html, templates/verified_dashboard.html |
| Collapse | templates/about.html, templates/admin_manual_activation.html, templates/admin_payment_management.html, templates/artisan.html, templates/certificate.html, templates/contact.html, templates/degree.html, templates/diploma.html, templates/guides/cluster_points.html, templates/guides/kcse_admission.html, templates/guides/kuccps_check.html, templates/kmtc.html, templates/ttc.html, templates/user-guide.html |
| Dropdown | templates/artisan.html, templates/certificate.html, templates/diploma.html, templates/kmtc.html, templates/kmtc_results.html, templates/ttc.html, templates/user-guide.html |
| Accordion | templates/artisan.html, templates/certificate.html, templates/degree.html, templates/diploma.html, templates/kmtc.html, templates/ttc.html |
| Toast | templates/admin_manual_activation.html, templates/admin_missing_courses.html, templates/base.html, templates/chat.html, templates/collection_results.html, templates/verified_dashboard.html |
| Tabs | templates/admin_financial_reports.html |
| Alert | templates/admin_cached_answers.html, templates/admin_clear_cache.html, templates/admin_dashboard.html, templates/admin_financial_reports.html, templates/admin_login.html, templates/admin_manual_activation.html, templates/admin_missing_courses.html, templates/admin_news.html, templates/admin_payment_issues.html, templates/admin_payment_management.html, templates/admin_payments.html, templates/admin_regenerate_degree.html, templates/admin_system_health.html, templates/admin_system_monitoring.html, templates/admin_users.html, templates/artisan.html, templates/artisan_results.html, templates/base.html, templates/basket.html, templates/certificate.html, templates/certificate_results.html, templates/collection_results.html, templates/components/install_prompt.html, templates/degree.html, templates/degree_results.html, templates/diploma.html, templates/diploma_results.html, templates/includes/flash_messages.html, templates/kmtc.html, templates/kmtc_results.html, templates/manual_activation_request.html.html, templates/news.html, templates/offline.html, templates/payment.html, templates/payment_issue.html, templates/results.html, templates/ttc.html, templates/verified_dashboard.html |
| Progress | templates/admin_payment_issues.html, templates/admin_regenerate_degree.html, templates/artisan.html, templates/guides/artisan_courses.html, templates/guides/diploma_courses.html, templates/guides/kcse_admission.html, templates/index.html, templates/payment_wait.html |
| Spinner | templates/admin_dashboard.html, templates/admin_missing_courses.html, templates/admin_payment_issues.html, templates/admin_regenerate_degree.html, templates/artisan.html, templates/certificate.html, templates/degree.html, templates/diploma.html, templates/kmtc.html, templates/news.html, templates/payment.html, templates/ttc.html |

Font Awesome classes found in templates: **144 unique icon names**. The full list is:

fa-arrow-left, fa-arrow-right, fa-arrow-up, fa-at, fa-award, fa-ban, fa-bars, fa-basket-shopping, fa-bell, fa-bolt, fa-book, fa-book-open, fa-bookmark, fa-books, fa-brain, fa-briefcase, fa-broom, fa-bullhorn, fa-bullseye, fa-business-time, fa-calculator, fa-calendar, fa-calendar-alt, fa-calendar-check, fa-calendar-day, fa-calendar-week, fa-camera, fa-cart-plus, fa-certificate, fa-chalkboard, fa-chalkboard-teacher, fa-chalkboard-user, fa-chart-bar, fa-chart-line, fa-chart-pie, fa-check, fa-check-circle, fa-check-double, fa-chevron-left, fa-chevron-right, fa-clipboard-list, fa-clock, fa-cloud-upload-alt, fa-code, fa-coins, fa-comment, fa-comments, fa-compass, fa-copy, fa-database, fa-download, fa-edit, fa-envelope, fa-envelope-open-text, fa-eraser, fa-exclamation-circle, fa-exclamation-triangle, fa-external-link-alt, fa-eye, fa-eye-slash, fa-facebook-f, fa-file-alt, fa-file-contract, fa-file-csv, fa-file-export, fa-filter, fa-flask, fa-folder, fa-folder-tree, fa-graduation-cap, fa-hammer, fa-hand-holding-usd, fa-hands-helping, fa-hashtag, fa-headset, fa-heart-pulse, fa-heartbeat, fa-history, fa-home, fa-hospital, fa-hospital-alt, fa-id-card, fa-image, fa-inbox, fa-info-circle, fa-instagram, fa-key, fa-laptop-code, fa-layer-group, fa-lightbulb, fa-link, fa-list, fa-list-alt, fa-magic, fa-mobile-alt, fa-money-bill-wave, fa-moon, fa-newspaper, fa-paper-plane, fa-phone, fa-plus, fa-plus-circle, fa-print, fa-question-circle, fa-receipt, fa-redo, fa-redo-alt, fa-robot, fa-rocket, fa-save, fa-school, fa-search, fa-search-dollar, fa-server, fa-share-alt, fa-share-square, fa-shield-alt, fa-shopping-basket, fa-sign-out-alt, fa-sparkles, fa-spinner, fa-star, fa-stethoscope, fa-sun, fa-sync-alt, fa-tachometer-alt, fa-tag, fa-tasks, fa-th-list, fa-times, fa-times-circle, fa-tools, fa-trash, fa-trash-alt, fa-twitter, fa-university, fa-user, fa-user-check, fa-user-friends, fa-user-plus, fa-user-shield, fa-user-tie, fa-users, fa-whatsapp

## Images, video and static weight

`static/` contains 27 files totaling 37,149,411 bytes (35.43 MiB); the cluster-points video alone is 36,166,448 bytes (~97.4% of that total). Two payment-issue upload images were found; filenames are intentionally omitted from this report to avoid exposing user identifiers.

| Asset | Dimensions | Bytes | Reference |
| --- | --- | --- | --- |
| static/icons/icon-128x128.png | 128×128 | 1,369 | static/manifest.json |
| static/icons/icon-144x144.png | 144×144 | 1,525 | static/manifest.json |
| static/icons/icon-152x152.png | 152×152 | 1,591 | templates/base.html, static/manifest.json |
| static/icons/icon-192x192.png | 192×192 | 2,014 | templates/chat.html, static/service-worker.js, static/manifest.json |
| static/icons/icon-384x384.png | 384×384 | 4,580 | static/manifest.json |
| static/icons/icon-512x512.png | 512×512 | 6,133 | static/service-worker.js, static/manifest.json |
| static/icons/icon-72x72.png | 72×72 | 774 | static/service-worker.js, static/manifest.json |
| static/icons/icon-96x96.png | 96×96 | 994 | static/manifest.json |
| static/images/graduation.jpg | 736×1104 | 64,127 | not referenced directly |
| static/images/kuccps.png | 4036×348 | 199,583 | templates/about.html, templates/news_article.html |
| static/images/og-image.jpg | 1200×800 | 272,890 | templates/news_article.html |
| static/images/twitter-card.jpg | 1200×800 | 155,421 | not referenced directly |
| static/videos/cluster-points.mp4 | n/a | 36,166,448 | templates/degree.html |

## PWA / cache / compression findings

- `static/service-worker.js` is 6,481 bytes. Its static precache list includes `/static/js/main.js`, which does not exist (`/static/js/script.js` does exist), and its `cache.addAll()` batches are all-or-nothing. The code catches precache errors, so installation may proceed while the intended static precache fails. The list also includes an external `short-courses.onrender.com` URL and API URLs; these require separate review for CORS/offline semantics.
- The service worker has network-first logic for HTML and API paths and cache-first for static assets. Before changing it, inspect all current PWA/update/offline behaviors and keep payment/admin/POST data out of caches.
- `static/css/styles-01.css` is empty (0 bytes) but referenced by the five grade-entry templates. `templates/guides_index.html` references `/static/css/style.css`, which does not exist; `static/css/guides.css` exists and is separately linked.
- The repository has a one-year static cache policy while asset URLs do not use a content hash/version query in the inspected base template. Cache invalidation is therefore a review item.
- A `<video>` in `templates/degree.html` references the 36.17 MB `cluster-points.mp4` without an explicit `preload` policy or poster in the inspected markup.
- No compression or static-cache code was changed in this audit.

## Local response-size baseline (not a Lighthouse run)

Routes were measured with Flask `test_client` in the current checkout, with MongoDB replaced by a connection-failure stub to avoid accessing student or production data. The page response status was 200 for every listed route. Gzip sizes were measured by sending `Accept-Encoding: gzip`; the earlier identity sizes came from the same test-client method in a separate run. These values are document-body bytes only; they exclude browser requests to CDN/fonts/images and are not equivalent to transfer totals or a browser benchmark.

| Route | HTTP | HTML identity bytes | HTML gzip bytes | Notes |
| --- | --- | --- | --- | --- |
| / | 200 | 187,038 | 36,687 | Home |
| /degree | 200 | 193,485 | 35,957 | Grade entry; 36MB video is a separate resource |
| /guides | 200 | 163,118 | 33,281 | Guides landing |
| /news | 200 | 153,068 | 31,800 | News landing |
| /chat | 200 | 58,339 | 12,000 | Standalone chat template |
| /offline | 200 | 4,577 | 1,588 | Offline fallback |

### Lighthouse/device metrics

**Not collected:** LCP, CLS, TBT, INP, Lighthouse Performance/Accessibility, browser request count, full transfer size, Moto G Power 4G-throttled run, 6× CPU, 360×800/768×1024/1440×900 layout capture, keyboard-only, dark mode and reduced-motion browser checks. Lighthouse, Playwright and Selenium are not installed/detectable in the local toolchain. `test_client` does not execute JavaScript, layout, media loading, CDN requests or PWA installation. `/results` was not measured because this requires a valid student session/payment/data and this audit intentionally used no production DB or fake course result. Do not infer Lighthouse scores from the HTML byte samples.

## Main findings to resolve after audit review

1. The shared base sends 48 KB of inline CSS plus 35 KB of inline script/data on every inherited page, in addition to a 133 KB base template. Page-specific inline styles/scripts add repeated bytes; grade-entry templates each have roughly 9.6 KB of styles and ~8 KB of inline script blocks.
2. Public pages depend on render-blocking external Bootstrap, Font Awesome and Google Fonts CDNs, with version drift between templates (Bootstrap 5.1.3/5.3.0/5.3.3 and Font Awesome 6.0/6.4/6.5); admin Summernote also loads jQuery. A third-party Tailwind CDN appears on an admin page.
3. The 36.17 MB explanatory video and image payloads are the largest local transfer risks; media dimensions and current use are listed above.
4. PWA precache has a missing JS URL and all-or-nothing groups; there is also a missing `style.css` link and empty `styles-01.css` references.
5. Current `app.py`, business code and deployment files are already modified in the working tree. Future work must be strictly scoped to frontend unless a permitted safe performance helper is reviewed independently.

## Baseline validation run

- Flask test-client GETs: `/`, `/degree`, `/guides`, `/news`, `/chat`, `/offline` → HTTP 200 with DB disabled; HTML bytes recorded above.
- No API/eligibility/payment mutation was invoked; no student records were read or written.
- Remote CDN bytes and browser-level failures were not observable in the test client.
- This report does not claim any Lighthouse, accessibility, cross-device or offline-install score.


## Implementation update — 2026-11-26

The Midnight Blue implementation began on `frontend-midnight-blue` after the audit. Existing edits and generated/user-data paths listed above remain preserved. A binary recovery patch of the tracked pre-implementation working tree is stored outside the project at `C:\Users\ADMIN\Documents\Codex\2026-11-26\venv-ps-c-users-admin-documents\work\kuccps-pre-midnight-blue-20261126\tracked-working-tree.patch`.

### Implemented

- Extracted the 48,370-byte shared inline CSS block from `templates/base.html` to `static/css/main.css`, then removed duplicate legacy token definitions; retained compact token and critical rules inline (about 6.6 KB combined). The Midnight Blue override stylesheet is `static/css/midnight.css`; the page styles block remains available to templates.
- Added the exact Midnight Blue palette, compatibility aliases for existing template CSS, explicit dark theme tokens, a pre-paint system/manual theme choice, and a keyboard accessible theme toggle.
- Rebuilt the homepage hero with a CSS 3D course-preview illustration, reduced-motion/low-resource static fallback, keyboard focus treatment, letter-write heading motion, and a finite type-cycle line. The content is labelled and available as plain text when motion is disabled or JavaScript is unavailable.
- Replaced visual homepage counters for courses, institutions, and students with feature statements; retained the page's existing JSON-LD and hidden SEO content. The hero keeps the existing results-modal and course-category links.
- Changed the degree explainer video to `preload="none"`, preserving its existing source and controls; switched the shared favicon to the local PWA icon.
- Replaced the broken service-worker precache list with individual best-effort fetches, root-scope registration, a functional update prompt, a bumped cache namespace, static-asset refresh, an offline HTML fallback, and exclusions for API, payment, admin, results, basket, and account routes. No POST requests are intercepted.
- Extended the already-present Flask response hook to gzip smaller compressible responses, including text static files under 1 MB; HTML is `no-cache`, private/mutation routes are `no-store`, and large assets remain streamed. No route or business rule changed.
- Extracted the 28,851-byte shared runtime script to `static/js/base-ui.js` so browsers can cache it between pages.
- Added version query strings to new shared CSS/JavaScript resources to avoid stale content under the existing one-year static cache policy. Added `scripts/build_assets.py`; its minified outputs are generated with the project-pinned `cssmin` and `jsmin` libraries.

### Verification results and limits

- Flask/Python compilation: passed for `app.py`, `courses.py`, `basket.py`, and `guide_routes.py`.
- Node syntax checks: passed for the service worker, updated PWA registration script, minified writing script, and minified shared interaction script.
- Asset build: `scripts/build_assets.py` ran successfully using the pinned `cssmin` and `jsmin` packages.
- JavaScript syntax: passed for the writing-motion module and service worker using Node's stdin checker.
- Jinja syntax: all 66 templates parsed with the project virtual environment; zero syntax errors.
- Flask test-client smoke run against a stubbed Mongo client: `/`, all six category routes, `/guides`, `/news`, `/chat`, `/offline`, `/service-worker.js`, and all generated minified asset URLs returned HTTP 200; `/basket` returned its existing HTTP 302 unauthenticated redirect. The new CSS returned HTTP 200 with gzip encoding and `public, max-age=31536000, immutable`.
- The smoke run uses an empty fake database, so it does not verify live Mongo data, account/payment flows, live AI, or eligibility values.
- No test files, pytest, Playwright, or local browser automation package are present in this checkout. The environment denied binding a local TCP server socket; therefore no browser screenshots, viewport/keyboard checks, Lighthouse run, accessibility score, or INP/TBT/LCP post-redesign measurements were possible. The earlier audit's before baseline remains document-byte measurements only, not Lighthouse data.
- Self-hosted font files were not present and the prior attempted CDN fetches failed TLS negotiation. Existing Google Fonts, Bootstrap and Font Awesome references are retained to avoid breaking legacy pages, icons, modal/collapse behavior, and standalone templates. They have not yet been removed or subsetted.
- `ffmpeg`/`ffprobe` were unavailable; the 36 MB cluster video was not transcoded. It now avoids eager download. Existing heavy image encodings were not changed.
- No new Python or JavaScript dependencies were added. Browser-level quality and the <500 KB initial transfer / Lighthouse targets remain unverified and are not claimed as met.
- The repository's existing modified files include unrelated/backend/user data changes. Git staging/commit was blocked by `.git/index.lock` access restrictions during the audit. No commit was created and no broad stage/reset was attempted.


### Response-size comparison (Flask test client, empty fake Mongo)

These are rendered HTML response bodies only. The “gzip” measurement is the response body delivered by the Flask test client with `Accept-Encoding: gzip`; it excludes stylesheets/fonts/icons/images and is not a Lighthouse transfer-size measurement.

| Route | Audit baseline raw | After raw | Audit baseline gzip | After gzip |
|---|---:|---:|---:|---:|
| `/` | 187,038 B | 119,764 B | 36,687 B | 23,682 B |
| `/degree` | 193,485 B | 123,954 B | 35,957 B | 22,405 B |
| `/guides` | 163,118 B | 97,875 B | 33,281 B | 20,568 B |
| `/news` | 153,068 B | 83,522 B | 31,800 B | 18,531 B |
| `/chat` | 58,339 B | 58,339 B | 12,000 B | 12,000 B |

The four pages using the shared base are 35.4%–41.7% smaller by compressed document body. `/chat` is standalone and unchanged. No request count, CLS, LCP, TBT or INP value is inferred from these measurements.


## Visual revision — 2026-11-27

The later approved visual direction supersedes the Midnight Blue implementation details above: the shared layout and homepage now use a pure-white canvas, ink navy `#071B2F`, emerald `#137E4E`, light emerald `#EEF9F3`, cool slate `#475569`, and slate borders `#E2E8F0`. The manual/system dark-theme toggle was removed. Typography uses Manrope with a system fallback. The homepage now uses the “Discover the courses you qualify for” headline with letter-by-letter emphasis, existing pathway links, descriptive three-step guidance, FAQ and an explicit placement disclaimer. Current browser-level results remain unmeasured; the audit’s original metrics are only test-client HTML sizes.
