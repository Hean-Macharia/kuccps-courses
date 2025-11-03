import glob, re

files = glob.glob('templates/**/*.html', recursive=True)

aria_re = re.compile(r'<(?P<tag>\w+)(?P<attrs>[^>]*)aria-hidden\s*=\s*"true"(?P<rest>[^>]*)>(?P<inner>.*?)</(?P=tag)>', re.S | re.I)
focusable_re = re.compile(r'<(a|button|input|select|textarea)[\s>]', re.I)

problems = []
for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        text = f.read()
    for m in aria_re.finditer(text):
        tag = m.group('tag')
        inner = m.group('inner')
        start = m.start()
        focusables = focusable_re.findall(inner)
        if focusables:
            line_no = text.count('\n', 0, start) + 1
            problems.append((fp, line_no, tag, list(set([t.lower() for t in focusables]))))

if not problems:
    print('No aria-hidden elements containing focusable descendants (accurate check).')
else:
    print('Found problematic aria-hidden elements:')
    for p in problems:
        print(f'File: {p[0]} Line: {p[1]} Tag: {p[2]} Focusables: {p[3]}')
