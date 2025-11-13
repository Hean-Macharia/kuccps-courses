import importlib.util
import os

# load app module
spec = importlib.util.spec_from_file_location('app', os.path.join(os.path.dirname(__file__), '..', 'app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = getattr(module, 'app')

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['email'] = 'render_test@example.com'
        sess['index_number'] = '77777777777/2025'
        sess['current_flow'] = 'diploma'
        sess['bypass_payment_check'] = True
    r = client.get('/results/diploma')
    print('STATUS', r.status_code)
    html = r.get_data(as_text=True)
    start = html.find('<div id="clusters"')
    print(html[start:start+1000])
