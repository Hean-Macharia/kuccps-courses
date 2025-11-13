import importlib.util
import os
import traceback

# load app module
spec = importlib.util.spec_from_file_location('app', os.path.join(os.path.dirname(__file__), '..', 'app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = getattr(module, 'app')
user_coll = getattr(module, 'user_data_collection')

email = 'render_insert@example.com'
index_number = '55555555555/2025'

sample_courses = [
    {'programme_code': '3001', 'institution_name': 'DIPLOMA U', 'programme_name': 'DIPLOMA A', 'collection': 'Applied_Sciences'},
    {'programme_code': '3002', 'institution_name': 'DIPLOMA U', 'programme_name': 'DIPLOMA B', 'collection': 'Business_Related'},
    {'programme_code': '3003', 'institution_name': 'DIPLOMA U', 'programme_name': 'DIPLOMA C', 'collection': 'Applied_Sciences'},
]

try:
    user_coll.delete_many({'email': email, 'index_number': index_number})
except Exception:
    pass

try:
    doc = {
        'email': email,
        'index_number': index_number,
        'level': 'diploma',
        'courses': sample_courses,
        'payment_confirmed': True,
        'created_at': module.datetime.now()
    }
    user_coll.insert_one(doc)
    print('Inserted render record')
except Exception as e:
    print('Insert error', e)
    traceback.print_exc()

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['email'] = email
        sess['index_number'] = index_number
        sess['current_flow'] = 'diploma'
    r = client.get('/results/diploma')
    print('STATUS', r.status_code)
    print(r.get_data(as_text=True)[:2000])

# cleanup
try:
    user_coll.delete_many({'email': email, 'index_number': index_number})
except Exception:
    pass
