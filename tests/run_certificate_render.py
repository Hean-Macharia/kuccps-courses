import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, user_data_collection, database_connected, save_user_qualification
import json

sample_courses = [
    {
        'programme_code': 'C1001',
        'programme_name': 'Certificate in Agriculture',
        'institution_name': 'Kenya College',
        'collection': 'Agricultural_Sciences',
        'minimum_grade': {'mean_grade': 'C'},
        'minimum_subject_requirements': {'MAT': 'C', 'BIO': 'C'}
    },
    {
        'programme_code': 'C2002',
        'programme_name': 'Certificate in Computing',
        'institution_name': 'Tech Institute',
        'collection': 'Computing_IT_Related',
        'minimum_grade': {'mean_grade': 'B-'},
        'minimum_subject_requirements': {'MAT': 'B-', 'ENG': 'C'}
    }
]

email = 'test_user@example.com'
index = '00000000000/2025'
level = 'certificate'

# Save qualification to DB/session
if database_connected:
    # save via save_user_qualification which will upsert to DB
    save_user_qualification(email, index, sample_courses, level, transaction_ref='TESTREF123')
    # mark payment confirmed in DB
    try:
        user_data_collection.update_one({'email': email, 'index_number': index, 'level': level}, {'$set': {'payment_confirmed': True}})
        print('Updated DB record with payment_confirmed=True')
    except Exception as e:
        print('DB update failed:', e)
else:
    # fallback: save to session via client session will be done below
    print('Database not connected; test will use session fallback')

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['email'] = email
        sess['index_number'] = index
        sess['certificate_grades'] = {'MAT': 'B', 'ENG': 'B'}
        sess['certificate_mean_grade'] = 'B'

    resp = client.get('/results/certificate')
    print('STATUS:', resp.status_code)
    html = resp.get_data(as_text=True)
    # print small snippet around courses-data
    import re
    m = re.search(r"<script id=\"courses-data\" type=\"application/json\">(.*?)</script>", html, re.S)
    if m:
        print('Found courses-data JSON:')
        text = m.group(1).strip()
        print(text[:1000])
    else:
        print('No courses-data script found in rendered HTML')
    # Optionally write output to file
    open('tests/certificate_render_output.html', 'w', encoding='utf-8').write(html)
    print('Wrote tests/certificate_render_output.html')
