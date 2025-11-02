import importlib.util
import os
import traceback

# load app module
spec = importlib.util.spec_from_file_location('app', os.path.join(os.path.dirname(__file__), '..', 'app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = getattr(module, 'app')

# get DB collection
user_coll = getattr(module, 'user_data_collection')

# Prepare test record
email = 'debug_diploma@example.com'
index_number = '88888888888/2025'
mpesa_receipt = 'DIPLOMA99'

sample_courses = [
    {'programme_code': '2001', 'institution_name': 'DIPLOMA UNIV', 'programme_name': 'DIPLOMA TEST', 'collection': 'Applied_Sciences'}
]

# cleanup previous
try:
    user_coll.delete_many({'email': email, 'index_number': index_number})
except Exception as e:
    print('DB delete error (continuing):', e)

# insert test record
try:
    doc = {
        'email': email,
        'index_number': index_number,
        'level': 'diploma',
        'courses': sample_courses,
        'mpesa_receipt': mpesa_receipt,
        'transaction_ref': mpesa_receipt,
        'payment_confirmed': True,
        'created_at': module.datetime.now()
    }
    user_coll.insert_one(doc)
    print('Inserted diploma test record')
except Exception as e:
    print('DB insert error:', e)
    traceback.print_exc()

# Run test client flow
try:
    with app.test_client() as client:
        resp = client.post('/verify-payment', data={'mpesa_receipt': mpesa_receipt, 'index_number': index_number})
        print('POST /verify-payment status:', resp.status_code, 'json:', resp.get_json())

        j = resp.get_json() or {}
        if j.get('success'):
            url = j.get('redirect_url')
            r2 = client.get(url)
            print('GET results status:', r2.status_code)
            # print fragment containing the sentence we expect
            html = r2.get_data(as_text=True)
            start = html.find('You qualify for')
            print(html[start:start+200])
        else:
            print('Verify failed, not fetching results')
except Exception:
    traceback.print_exc()
finally:
    # cleanup
    try:
        user_coll.delete_many({'email': email, 'index_number': index_number})
    except Exception:
        pass
