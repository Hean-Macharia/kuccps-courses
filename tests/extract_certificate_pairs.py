import re
p = 'tests/certificate_render_output.html'
with open(p, 'r', encoding='utf-8') as f:
    html = f.read()
# extract clusters div
m = re.search(r'<div id="clusters".*?>.*?</div>', html, re.S)
clusters_html = m.group(0) if m else ''
# find all button tags inside clusters
buttons = re.findall(r'(<button[^>]*data-coll="[^"]*"[^>]*>.*?</button>)', clusters_html, re.S)

pairs = []
for b in buttons:
    coll_m = re.search(r'data-coll="([^"]*)"', b)
    coll = coll_m.group(1) if coll_m else ''
    # find server-side category-list opening tag
    server_m = re.search(r'(<div[^>]*class="category-list"[^>]*data-coll="' + re.escape(coll) + r'"[^>]*>)', html)
    server_tag = server_m.group(1) if server_m else '(no server list found)'
    pairs.append((b.strip(), server_tag.strip()))

# print pairs
for btn, srv in pairs:
    print('BUTTON:')
    print(btn)
    print('SERVER LIST:')
    print(srv)
    print('\n' + '-'*60 + '\n')

print('TOTAL BUTTONS:', len(pairs))
