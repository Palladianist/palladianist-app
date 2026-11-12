import fs from 'node:fs';
import path from 'node:path';
const ROOT = path.join(process.cwd(), 'content');
const read = (p) => JSON.parse(fs.readFileSync(p, 'utf-8'));
const maybe = (p) => (fs.existsSync(p) ? read(p) : null);
const OK = ['reviewed', 'published'];

export const LANGS = ['en', 'it'];

export function listArticles() {
  const dir = path.join(ROOT, 'articles');
  return fs.readdirSync(dir).filter((d) => fs.existsSync(path.join(dir, d, 'text.en.json')));
}

export function loadArticle(id) {
  const d = path.join(ROOT, 'articles', id);
  const review = maybe(path.join(d, 'review.json')) || {};
  const text = { en: read(path.join(d, 'text.en.json')) };
  const it = maybe(path.join(d, 'text.it.json'));
  if (it && OK.includes(review.translation_it?.status)) text.it = it;
  const faqs = {};
  for (const l of LANGS) {
    const f = maybe(path.join(d, `faq.${l}.json`));
    if (f && OK.includes(f.status)) faqs[l] = f.items;
  }
  const audio = maybe(path.join(d, 'audio.json'));
  const episodes = (audio?.episodes || []).filter((e) => OK.includes(e.status) && e.file);
  return {
    id,
    meta: maybe(path.join(d, 'meta.json')),
    epub: maybe(path.join(d, 'meta.epub.json')) || {},
    text,
    faqs,
    audio: { disclaimer: audio?.disclaimer || {}, episodes },
    figures: (maybe(path.join(d, 'figures.json'))?.figures) || [],
    review
  };
}

export function loadIssue(id) { return read(path.join(ROOT, 'issues', `${id}.json`)); }
export function listIssues() {
  return fs.readdirSync(path.join(ROOT, 'issues')).filter((f) => f.endsWith('.json')).map((f) => read(path.join(ROOT, 'issues', f)));
}
