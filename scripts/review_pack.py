#!/usr/bin/env python3
"""Build the editor's review pack for an article: side-by-side EN/IT Word file and NotebookLM sources.
Usage: python3 scripts/review_pack.py <article-id> <output-folder>
"""
import sys, os, json, re, html
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.section import WD_ORIENT
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
aid, out = sys.argv[1], sys.argv[2]; A = os.path.join(ROOT, 'content', 'articles', aid)
J = lambda n: json.load(open(os.path.join(A, n), encoding='utf-8'))
en, it, figs, meta = J('text.en.json'), J('text.it.json'), J('figures.json')['figures'], J('meta.json')
epub = J('meta.epub.json'); fe, fi = J('faq.en.json')['items'], J('faq.it.json')['items']
itb = {b['id']: b for b in it['blocks']}; itn = {n['id']: n for n in it.get('notes', [])}
label = sys.argv[3] if len(sys.argv) > 3 else re.sub(r'\W+', ' ', meta['authors'][0]['family']).strip()
d = Document(); s = d.sections[0]; s.orientation = WD_ORIENT.LANDSCAPE; s.page_width, s.page_height = s.page_height, s.page_width
for m in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'): setattr(s, m, Cm(1.6))
d.styles['Normal'].font.name = 'Calibri'; d.styles['Normal'].font.size = Pt(10)
d.add_heading(f'Revisione traduzione IT – {", ".join(a["given"] + " " + a["family"] for a in meta["authors"])}, {meta["title"]}', 1)
d.add_paragraph('Confronta EN (versione di record) e IT riga per riga. Correggi nella colonna IT o annota nella colonna Note. Non modificare la colonna ID.')
if it.get('translationNotes'): d.add_paragraph('Nota del traduttore: ' + it['translationNotes'])
def rich(cell, t):
    p = cell.paragraphs[0]
    for part in re.split(r'(<em>.*?</em>)', t):
        if part: r = p.add_run(html.unescape(re.sub(r'<[^>]+>', '', part))); r.italic = part.startswith('<em>')
tb = d.add_table(rows=1, cols=4); tb.style = 'Table Grid'; W = [1.6, 11.5, 11.5, 3.5]
for c, h, w in zip(tb.rows[0].cells, ['ID', 'English (original)', 'Italiano (bozza)', 'Note'], W): c.text = h; c.width = Cm(w)
def row(i, e, t):
    r = tb.add_row().cells; r[0].text = i; rich(r[1], e); rich(r[2], t)
    for c, w in zip(r, W): c.width = Cm(w)
row('title', meta['title'], it['title'])
for k, (a, b) in enumerate(zip(epub.get('abstract', []), it.get('abstract', []))): row(f'abstract-{k+1}', a, b)
for b in en['blocks']:
    if b['type'] == 'figure':
        f = next(x for x in figs if x['id'] == b['ref']); g = it['figures'][b['ref']]
        row(b['id'], 'CAPTION: ' + f['caption'] + '  ALT: ' + f['alt'], 'DIDASCALIA: ' + g['caption'] + '  ALT: ' + g['alt'])
    elif b['type'] == 'table':
        tj = lambda rows: ' || '.join(' | '.join(r) for r in rows)
        row(b['id'], 'TABLE: ' + tj(b['rows']), 'TABELLA: ' + tj(itb[b['id']]['rows']))
    else: row(b['id'], b['text'], itb[b['id']]['text'])
for n in en.get('notes', []): row(n['id'], n['text'], itn[n['id']]['text'])
d.add_heading('FAQ', 2); t2 = d.add_table(rows=1, cols=2); t2.style = 'Table Grid'
t2.rows[0].cells[0].text = 'EN'; t2.rows[0].cells[1].text = 'IT'
for a, b in zip(fe, fi):
    r = t2.add_row().cells; r[0].text = f"Q: {a['q']}\nA: {a['a']}"; r[1].text = f"D: {b['q']}\nR: {b['a']}"
os.makedirs(out, exist_ok=True); d.save(os.path.join(out, f'Revisione traduzione IT – {label}.docx'))
md = lambda h: html.unescape(re.sub(r'</?em>', '*', re.sub(r'<sup[^>]*>(\d+)</sup>', r'[\1]', h)))
def build(doc, title, abstract, cap, notes, lang):
    aus = ', '.join(f'{a["given"]} {a["family"]}' for a in meta['authors'])
    L = [f'# {title}', '', f'{aus} – {meta["authors"][0]["affiliation"]}', '',
         f'*{meta["journal"]}*, Vol. {meta["volume"]}, n. {meta["number"]} ({meta["year"]}).' + (" Traduzione italiana assistita da AI e rivista; testo di riferimento: originale inglese." if lang == 'it' else ''), '', '## Abstract', ''] + [md(a) + '\n' for a in abstract]
    for b in doc['blocks']:
        if b['type'] == 'heading': L += ['', f"## {md(b['text'])}", '']
        elif b['type'] == 'listitem': L.append(f"- {md(b['text'])}")
        elif b['type'] == 'figure': L += ['', f"[{md(cap(b['ref']))}]", '']
        elif b['type'] == 'table':
            R = b['rows']; L += [''] + ['| ' + ' | '.join(md(c) for c in r) + ' |' for r in R[:1]] + ['|' + '---|' * len(R[0])] + ['| ' + ' | '.join(md(c) for c in r) + ' |' for r in R[1:]] + ['']
        else: L += [md(b['text']), '']
    if notes: L += ['', '## ' + ('Note' if lang == 'it' else 'Notes'), ''] + [f"{i}. {md(n['text'])}" for i, n in enumerate(notes, 1)]
    return '\n'.join(L) + '\n'
fmap = {f['id']: f for f in figs}
open(os.path.join(out, f'NotebookLM – {label} EN.md'), 'w', encoding='utf-8').write(build(en, meta['title'], epub.get('abstract', []), lambda r: fmap[r]['caption'], en.get('notes'), 'en'))
open(os.path.join(out, f'NotebookLM – {label} IT.md'), 'w', encoding='utf-8').write(build(it, it['title'], it.get('abstract', []), lambda r: it['figures'][r]['caption'], it.get('notes'), 'it'))
print('ok', out)
