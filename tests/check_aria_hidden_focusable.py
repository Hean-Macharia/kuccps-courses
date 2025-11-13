import glob, re

focusable_sel = re.compile(r'<(a|button|input|select|textarea)[\s>]', re.I)
aria_hidden_pattern = re.compile(r'(<[^>]+aria-hidden\s*=\s*"true"[^>]*>)', re.I)

files = glob.glob('templates/**/*.html', recursive=True)
problems = []
for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        text = f.read()
    for m in aria_hidden_pattern.finditer(text):
        tag = m.group(1)
        start = m.start(1)
        # find the end of this element's outer HTML by searching for matching closing tag; naive approach
        # We'll search forward for next </div> or </section> within 2000 chars
        snippet = text[start:start+2000]
        # find focusable descendants within snippet
        focusables = focusable_sel.findall(snippet)
        if focusables:
            # line number
            line_no = text.count('\n', 0, start) + 1
            problems.append((fp, line_no, tag.strip(), list(set([f.lower() for f in focusables]))))

if not problems:
    print('No aria-hidden elements with focusable descendants found in templates')
else:
    print('Found aria-hidden elements containing focusable descendant tags:')
    for p in problems:
        print(f'File: {p[0]} Line: {p[1]}')
        print('Element start:', p[2])
        print('Focusable descendants:', p[3])
        print('-'*60)
