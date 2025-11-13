import traceback
import importlib.util
import os

# Attempt to import the Flask app from app.py reliably
try:
    from app import app
except Exception:
    # Fallback: load module from file path
    spec = importlib.util.spec_from_file_location('app', os.path.join(os.path.dirname(__file__), '..', 'app.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = getattr(module, 'app')

# This script uses Flask test client to simulate a session and GET /results/degree
with app.test_client() as client:
    try:
        with client.session_transaction() as sess:
            sess['email'] = 'joanyaki0o@gmail.com'
            sess['index_number'] = '12345678902/2025'
            sess['current_flow'] = 'degree'
            sess['bypass_payment_check'] = True
            # minimal stored session state used by show_results
            sess['degree_grades'] = {'mathematics': 'A', 'english': 'B'}
            sess['degree_cluster_points'] = {'cluster_1': 42}

        resp = client.get('/results/degree')
        print('STATUS:', resp.status_code)
        print('HEADERS:', resp.headers)
        data = resp.get_data(as_text=True)
        print('\n--- RESPONSE START ---\n')
        print(data[:8000])
        print('\n--- RESPONSE END ---\n')
    except Exception:
        traceback.print_exc()
