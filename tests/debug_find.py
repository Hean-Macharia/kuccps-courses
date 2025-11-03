import importlib.util
import os

spec = importlib.util.spec_from_file_location('app', os.path.join(os.path.dirname(__file__), '..', 'app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
user_coll = getattr(module, 'user_data_collection')

query = {'index_number': '88888888888/2025', '$or': [{'transaction_ref': 'DIPLOMA99'}, {'mpesa_receipt': 'DIPLOMA99'}]}
print('Running find_one with query:', query)
res = user_coll.find_one(query)
print('Result:', res)
if res:
    import pprint
    pprint.pprint(res)
