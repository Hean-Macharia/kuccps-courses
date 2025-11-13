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
email = 'debug_test@example.com'
index_number = '99999999999/2025'
mpesa_receipt = 'ABC123DE45'

sample_courses = [
    {'programme_code': '1001', 'institution_name': 'TEST UNIVERSITY', 'programme_name': 'TEST PROGRAMME', 'cluster': 'cluster_1'}
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
        'level': 'degree',
        'courses': sample_courses,
        'mpesa_receipt': mpesa_receipt,
        'transaction_ref': mpesa_receipt,
        'payment_confirmed': True,
        'created_at': module.datetime.now()
    }
    user_coll.insert_one(doc)
    print('Inserted test record')
except Exception as e:
    print('DB insert error:', e)
    traceback.print_exc()

# Run test client flow
try:
    with app.test_client() as client:
        # POST verify-payment with raw string containing the receipt
        resp = client.post('/verify-payment', data={'mpesa_receipt': mpesa_receipt, 'index_number': index_number})
        print('POST /verify-payment status:', resp.status_code, 'json:', resp.get_json())

        # If verify succeeded, follow redirect URL
        j = resp.get_json() or {}
        if j.get('success'):
            url = j.get('redirect_url')
            print('Fetching results at', url)
            r2 = client.get(url)
            print('GET results status:', r2.status_code)
            print(r2.get_data(as_text=True)[:2000])
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
