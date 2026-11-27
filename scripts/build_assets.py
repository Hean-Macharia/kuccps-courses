from pathlib import Path
from cssmin import cssmin
from jsmin import jsmin

ROOT = Path(__file__).resolve().parents[1]

CSS = ['static/css/main.css', 'static/css/midnight.css']
JS = ['static/js/ui-motion.js', 'static/js/writing.js', 'static/js/base-ui.js']
for relative in CSS:
    source = ROOT / relative
    (source.with_name(source.stem + '.min.css')).write_text(cssmin(source.read_text(encoding='utf-8')), encoding='utf-8')
for relative in JS:
    source = ROOT / relative
    (source.with_name(source.stem + '.min.js')).write_text(jsmin(source.read_text(encoding='utf-8')), encoding='utf-8')
print('Generated minified shared CSS/JavaScript assets.')
