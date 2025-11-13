import importlib.util
import os
import json
import re

# load app module
spec = importlib.util.spec_from_file_location('app', os.path.join(os.path.dirname(__file__), '..', 'app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = getattr(module, 'app')

# sample courses with multiple collections
sample_courses = [
    {"programme_code": "3001", "institution_name": "DIPLOMA U", "programme_name": "DIPLOMA A", "collection": "Applied_Sciences", "minimum_grade": {"mean_grade": "C+"}, "minimum_subject_requirements": {"MAT": "C"}},
    {"programme_code": "3002", "institution_name": "DIPLOMA U", "programme_name": "DIPLOMA B", "collection": "Business_Related", "minimum_grade": {"mean_grade": "C"}, "minimum_subject_requirements": {"ENG": "C"}},
    {"programme_code": "3003", "institution_name": "DIPLOMA U", "programme_name": "DIPLOMA C", "collection": "Applied_Sciences", "minimum_grade": {"mean_grade": "C+"}, "minimum_subject_requirements": {}},
]

# Pre-serialized JSON as backend would provide
courses_json = json.dumps(sample_courses)

# Render the template directly
tpl = app.jinja_env.get_template('diploma_results.html')
rendered = tpl.render(courses=sample_courses, courses_json=courses_json, user_grades={}, user_mean_grade='', subjects=getattr(module, 'SUBJECTS'), email='sample@example.com', index_number='00000000000/2025')

# Extract clusters div
m = re.search(r"(<div id=\"clusters\"[\s\S]*?</div>)", rendered)
clusters_html = m.group(1) if m else ''

# Extract the courses-data script snippet
m2 = re.search(r"<script id=\"courses-data\" type=\"application/json\">([\s\S]*?)</script>", rendered)
courses_json_text = m2.group(1).strip() if m2 else '[]'

# Build sample filtered HTML for one category (Applied_Sciences)
def build_cards(courses):
    parts = ['<div class="row">']
    for c in courses:
        parts.append('<div class="col-md-6 mb-3">')
        parts.append('<div class="card h-100"><div class="card-body">')
        parts.append(f"<h5 class=\"card-title\">{c.get('programme_name')}</h5>")
        parts.append(f"<h6 class=\"card-subtitle mb-2 text-muted\">{c.get('institution_name')}</h6>")
        parts.append('<p class=\"card-text\">')
        parts.append(f"<strong>Programme Code:</strong> {c.get('programme_code')}<br>")
        parts.append(f"<strong>Category:</strong> {c.get('collection')}<br>")
        if c.get('minimum_grade') and c['minimum_grade'].get('mean_grade'):
            parts.append(f"<strong>Minimum Mean Grade:</strong> {c['minimum_grade'].get('mean_grade')}<br>")
        if c.get('minimum_subject_requirements'):
            reqs = ', '.join([f"{s}: {g}" for s,g in c['minimum_subject_requirements'].items()])
            if reqs:
                parts.append(f"<strong>Subject Requirements:</strong> {reqs}")
        parts.append('</p>')
        parts.append('</div></div></div>')
    parts.append('</div>')
    return '\n'.join(parts)

applied = [c for c in sample_courses if c.get('collection') == 'Applied_Sciences']
filtered_html = build_cards(applied)

print('\n--- CLUSTERS HTML ---\n')
print(clusters_html)
print('\n--- COURSES JSON (first 400 chars) ---\n')
print(courses_json_text[:400])
print('\n--- FILTERED (Applied_Sciences) HTML ---\n')
print(filtered_html)
