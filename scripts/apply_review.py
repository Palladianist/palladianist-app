#!/usr/bin/env python3
"""Apply the editor's corrections from the review Word file back to text.it.json / faq.*.json
and mark them as reviewed. Usage: python3 scripts/apply_review.py <article-id> <docx> "<reviewer>" <YYYY-MM-DD>"""
import sys, os, json, re, html
from docx import Document
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
aid, docx_path, who, day = sys.argv[1:5]; A = os.path.join(ROOT, 'content', 'articles', aid)
d = Document(docx_path)
it = json.load(open(f'{A}/text.it.json')); idx = {b['id']: b for b in it['blocks']}; nidx = {n['id']: n for n in it.get('notes', [])}
def cell_html(c):
    out = ''
    for p in c.paragraphs:
        for r in p.runs:
            t = html.escape(r.text, quote=False); out += f'<em>{t}</em>' if r.italic and t.strip() else t
    out = re.sub(r'</em>(\s*)<em>', r'\1', out); return re.sub(r'\s+', ' ', out).strip()
plain = lambda h: html.unescape(re.sub(r'<[^>]+>', '', h)).strip()
changed, notes = [], []
for r in d.tables[0].rows[1:]:
    c = r.cells; i = c[0].text.strip(); new = cell_html(c[2]); note = c[3].text.strip()
    if note: notes.append(f'{i}: {note}')
    if i == 'title':
        if plain(new) != plain(it['title']): it['title'] = plain(new); changed.append(i)
    elif i.startswith('abstract-'):
        k = int(i.split('-')[1]) - 1
        if plain(new) != plain(it['abstract'][k]): it['abstract'][k] = new; changed.append(i)
    elif i in idx and 'text' in idx[i]:
        # keep note markers: only update when the visible text changed
        if plain(new) != plain(re.sub(r'<sup[^>]*>.*?</sup>', lambda m: plain(m.group(0)), idx[i]['text'])):
            sup = re.findall(r'<sup[^>]*>.*?</sup>', idx[i]['text'])
            for s in sup:  # re-attach note markers by number
                n = plain(s); new = re.sub(rf'(?<![\d<]){re.escape(n)}(?=[\s.,;:)]|$)', s, new, count=1) if s not in new else new
            idx[i]['text'] = new; changed.append(i)
    elif i in idx and idx[i].get('type') == 'table':
        m = re.match(r'TABELLA:\s*(.*)$', plain(new), re.S)
        if m:
            rows = [[c.strip() for c in r.split(' | ')] for r in m.group(1).split(' || ')]
            if rows != idx[i]['rows']: idx[i]['rows'] = rows; changed.append(i)
    elif i in nidx:
        if plain(new) != plain(nidx[i]['text']): nidx[i]['text'] = new; changed.append(i)
    elif i.startswith('f-'):
        ref = next((b['ref'] for b in it['blocks'] if b['id'] == i), None)
        m = re.match(r'DIDASCALIA:\s*(.*?)\s+ALT:\s*(.*)$', plain(new), re.S)
        if ref and m:
            f = it['figures'][ref]
            if m.group(1) != plain(f['caption']): f['caption'] = m.group(1); changed.append(i + ':caption')
            if m.group(2) != plain(f['alt']): f['alt'] = m.group(2); changed.append(i + ':alt')
it['translation'].update({'status': 'reviewed', 'reviewedBy': who, 'reviewedOn': day})
json.dump(it, open(f'{A}/text.it.json', 'w'), ensure_ascii=False, indent=2)
faq_changed = 0
if len(d.tables) > 1:
    fi, fe = json.load(open(f'{A}/faq.it.json')), json.load(open(f'{A}/faq.en.json'))
    for k, r in enumerate(d.tables[1].rows[1:]):
        for col, obj, qa in ((1, fi, ('D: ', 'R: ')), (0, fe, ('Q: ', 'A: '))):
            m = re.match(re.escape(qa[0]) + r'(.*?)\n' + re.escape(qa[1]) + r'(.*)', r.cells[col].text, re.S)
            if m and k < len(obj['items']):
                q, a = m.group(1).strip(), m.group(2).strip(); x = obj['items'][k]
                if (q, a) != (x['q'], x['a']): x['q'], x['a'] = q, a; faq_changed += 1
    for o, n in ((fi, 'faq.it.json'), (fe, 'faq.en.json')):
        o['status'] = 'reviewed'; json.dump(o, open(f'{A}/{n}', 'w'), ensure_ascii=False, indent=2)
rv = json.load(open(f'{A}/review.json'))
rv['translation_it'] = {'status': 'reviewed', 'reviewedBy': who, 'reviewedOn': day}; rv['faq'] = {'status': 'reviewed', 'reviewedBy': who, 'reviewedOn': day}
json.dump(rv, open(f'{A}/review.json', 'w'), ensure_ascii=False, indent=2)
print(json.dumps({'article': aid, 'textChanged': changed, 'faqChanged': faq_changed, 'notes': notes}, ensure_ascii=False))
