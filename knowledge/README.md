# KUCCPS assistant knowledge

`kuccps_corpus.jsonl` is a local snapshot of public, official KUCCPS pages and text-readable PDF resources. The chat assistant retrieves passages from it before asking Gemini or OpenRouter to answer. Its responses are instructed to avoid unsupported admission claims and include source links.

Refresh public official material from the project root:

```powershell
.\venv\Scripts\python.exe scripts/ingest_kuccps_knowledge.py --max-pages 80
```

The ingester only visits HTTPS pages on the explicit KUCCPS host allowlist, follows same-host links from `kuccps_sources.json`, and keeps normal certificate verification enabled. PDFs with extractable text are indexed. A failed or empty crawl leaves the existing corpus intact. Review new material and refresh it regularly, especially around application cycles. Dynamic student-portal pages may not expose their content in HTML; the optional official-domain web search remains available when `SERPAPI_KEY` is set.

The assistant can also retrieve course and requirement fields from a local snapshot of the existing MongoDB course catalogs. Create or refresh it with:

```powershell
.\venv\Scripts\python.exe scripts/index_course_catalog.py
```

This export is read-only and limited to the `Degree`, `diploma`, `kmtc`, `certificate`, `artisan`, and `Teachers` catalog databases. It excludes the `user_data` database, student records, payments and database identifiers. Catalog entries are explicitly labelled as a Courses Checker snapshot, not an official placement decision. On deployment, run this command from a job or machine with read access to the production MongoDB URI; do not expose the URI to clients.

Set `KUCCPS_KNOWLEDGE_PATH` or `KUCCPS_CATALOG_PATH` to use a different local JSONL file. No additional Python dependency is needed beyond packages already listed in `requirements.txt`.
