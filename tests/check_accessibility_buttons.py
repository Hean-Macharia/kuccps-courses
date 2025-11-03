import re
import glob

pattern = re.compile(r'<button([\s\S]*?)>([\s\S]*?)</button>', re.IGNORECASE)

files = glob.glob('templates/**/*.html', recursive=True)
problems = []

for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        s = f.read()
    for m in pattern.finditer(s):
        attrs = m.group(1)
        inner = m.group(2).strip()
        has_aria = 'aria-label' in attrs or 'title=' in attrs
        # check visible text inside inner (strip tags)
        text_only = re.sub(r'<[^>]+>', '', inner).strip()
        # if text_only empty and no aria/title and not a close button with aria-label
        if not has_aria and text_only == '':
            # find approximate line number
            start_idx = m.start()
            line_no = s.count('\n', 0, start_idx) + 1
            snippet = s.splitlines()[line_no-1].strip()
            problems.append((fp, line_no, snippet, inner, attrs.strip()))

if not problems:
    print('No problematic buttons found')
else:
    print('Found problematic buttons:')
    for p in problems:
        print(f'File: {p[0]} Line: {p[1]}')
        print('Snippet:', p[2])
        print('Inner HTML:', p[3][:200])
        print('Attributes:', p[4])
        print('-'*40)
