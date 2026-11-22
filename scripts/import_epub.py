#!/usr/bin/env python3
"""Import one article from an InDesign reflowable EPUB into the Palladianist content model.

Usage:
  python3 scripts/import_epub.py <file.epub> <article-id> [--file 01_HEMSOLL.xhtml]
                                 [--issue v1n1] [--section article] [--list]

--list    prints the chapter files contained in the EPUB (one per article in a full-issue EPUB).
--file    selects the chapter to import (default: all non-cover/toc chapters, for single-article EPUBs).

Writes content/articles/<id>/{meta.epub.json,text.en.json,figures.json,review.json}
and copies figures to public/figures/<id>/. Mapping is based on InDesign paragraph-style
class names (STYLE_MAP), so export tags are not required. Standard library only.
"""
import argparse, html, json, os, re, shutil, sys, zipfile
from html.parser import HTMLParser

STYLE_MAP = {
    "Heading-1": "h2", "Heading-2": "h3",
    "Normal": "p", "List-Paragraph": "li",
    "abstract": "abstract", "parole-chiave": "keyword", "didascalie": "caption",
    "References": "reference", "Endnote-text": "marker",
    "affiliazione-autore": "author", "titolo-sottoparagrafo": "front", "Paragrafo-base": "front",
}
BLOCK = ("p", "li", "h1", "h2", "h3", "h4")

class Doc(HTMLParser):
    def __init__(self, italic_classes):
        super().__init__(convert_charrefs=True)
        self.italic = italic_classes
        self.blocks, self.cur, self.stack, self.noteref = [], None, [], None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); cls = (a.get("class") or "").split()
        if tag in BLOCK:
            style = next((STYLE_MAP[c] for c in cls if c in STYLE_MAP), None)
            self.cur = {"style": style or "unknown", "raw": " ".join(cls), "html": ""}
        elif tag == "img":
            self.blocks.append({"style": "img", "src": a.get("src", ""), "alt": a.get("alt", "")})
        elif tag == "a" and self.cur is not None and ("noteref" in (a.get("epub:type") or "") or "doc-noteref" in (a.get("role") or "")):
            m = re.search(r"(\d+)\D*$", a.get("href", "")); self.noteref = m.group(1) if m else "?"
            self.cur["html"] += f'<sup class="noteref" data-note="n-{int(self.noteref) if self.noteref.isdigit() else self.noteref}">'
            self.stack.append("a")
        elif tag == "span" and self.cur is not None:
            it = any(c in self.italic for c in cls); self.stack.append(it)
            if it: self.cur["html"] += "<em>"
        elif tag == "br" and self.cur is not None:
            self.cur["html"] += " "
    def handle_endtag(self, tag):
        if tag == "a" and self.stack and self.stack[-1] == "a":
            self.stack.pop(); self.cur["html"] += "</sup>"; self.noteref = None
        elif tag == "span" and self.cur is not None and self.stack and self.stack[-1] != "a":
            if self.stack.pop() is True: self.cur["html"] += "</em>"
        elif tag in BLOCK and self.cur is not None:
            t = re.sub(r"\s+", " ", self.cur["html"]).strip()
            t = re.sub(r"<em>(\s*)</em>", r"\1", t).replace("</em><em>", "")
            if re.sub(r"<[^>]+>", "", t).strip():
                self.cur["html"] = t; self.blocks.append(self.cur)
            self.cur = None; self.stack = []
    def handle_data(self, data):
        if self.cur is not None: self.cur["html"] += html.escape(data, quote=False)

def italic_classes(css):
    out = set()
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        if re.search(r"font-style\s*:\s*italic", body): out.update(re.findall(r"span\.([\w-]+)", sel))
    return out

def plain(h): return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()

def fig_numbers(text):
    nums = []
    for grp in re.findall(r"\b[Ff]ig(?:ure)?s?\.?\s*((?:\d+\s*(?:[-–,]|and|&amp;|&)?\s*)+)", text):
        for a, b in re.findall(r"(\d+)(?:\s*[-–]\s*(\d+))?", grp):
            nums += list(range(int(a), int(b) + 1)) if b else [int(a)]
    return nums

def chapters(z):
    return [n for n in z.namelist() if n.endswith(".xhtml") and not re.search(r"(cover|toc|nav)\.xhtml$", n)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("epub"); ap.add_argument("id", nargs="?")
    ap.add_argument("--file"); ap.add_argument("--issue", default=""); ap.add_argument("--section", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()
    z = zipfile.ZipFile(a.epub)
    if a.list:
        print("\n".join(chapters(z))); return
    files = [n for n in chapters(z) if (not a.file or n.endswith(a.file))]
    if not files: sys.exit(f"chapter not found: {a.file}")
    blocks_all = []
    for n in files:
        src = z.read(n).decode("utf-8")
        # only the stylesheets linked by this chapter (InDesign reuses class names across chapters)
        links = [os.path.normpath(os.path.join(os.path.dirname(n), h)).replace("\\", "/") for h in re.findall(r'<link[^>]+href="([^"]+\.css)"', src)]
        css = "".join(z.read(l).decode("utf-8", "ignore") for l in links if l in z.namelist())
        d = Doc(italic_classes(css)); d.feed(src); blocks_all += d.blocks
    class _D: pass
    doc = _D(); doc.blocks = blocks_all
    B = doc.blocks

    front, authors, keywords, abstract, byline = [], [], [], [], []
    body, refs, further, notes, captions, imgs = [], [], [], [], [], []
    started, zone = False, "body"
    for b in B:
        s = b["style"]
        if s == "img": imgs.append(b); continue
        t = b["html"]; pt = plain(t)
        if s == "caption": captions.append(t); continue
        if not started and s in ("p", "h2"): started = True
        if not started:
            if s == "author" and any(x.upper() not in ("EDITORIAL", "ARTICLE", "ESSAY") for x in front): byline.append(pt); continue
            {"keyword": keywords, "abstract": abstract, "author": authors}.get(s, front).append(pt); continue
        if s == "caption": captions.append(t); continue
        if s == "marker" or (s in ("li", "p", "h2") and pt.lower() in ("notes", "references", "further readings", "further reading", "bibliography")):
            zone = {"notes": "notes", "references": "refs", "bibliography": "refs"}.get(pt.lower(), "further"); continue
        if s == "reference" or zone != "body":
            {"notes": notes, "refs": refs, "further": further}.get(zone if zone != "body" else "refs").append(t); continue
        body.append((s, t))

    # metadata from front matter
    title, cite = [], []
    in_cite = False
    for line in front:
        if line.lower().startswith("how to cite"): in_cite = True; continue
        (cite if in_cite else title).append(line)
    title = [x for x in title if x.upper() not in ("EDITORIAL", "ARTICLE", "ESSAY")]
    pages = next((m.group(1) for c in cite for m in [re.search(r",\s*\d+\s*,\s*(\d+\s*[–-]\s*\d+)", c)] if m), None)
    dates = next((c for c in cite if c.startswith("Received")), "")
    email = next((x for x in authors if "@" in x), None)
    name, aff = (byline + [None, None])[:2]
    bio = " ".join(x for x in authors if "@" not in x)

    # figures: pair images (excluding licence icons/decor) with captions by number
    imgs = [i for i in imgs if not re.search(r"(by\.png|cc_by|icon|logo|sfondo|P_2|intbau\.png)", i["src"], re.I)]
    capby = {}
    for c in captions:
        m = re.match(r"\s*Fig(?:ure)?\.?\s*(\d+)", plain(c));
        if m: capby[int(m.group(1))] = c
    fig_dir = os.path.join(a.root, "public", "figures", a.id); os.makedirs(fig_dir, exist_ok=True)
    base = os.path.dirname(files[0]); figs = []
    for k, img in enumerate(imgs, 1):
        src = os.path.normpath(os.path.join(base, img["src"])).replace("\\", "/")
        fn = re.sub(r"[^\w.-]", "_", os.path.basename(src))
        with z.open(src) as f, open(os.path.join(fig_dir, fn), "wb") as o: shutil.copyfileobj(f, o)
        alt = re.sub(r"^[\w-]+\.\s+", "", html.unescape(img["alt"]).strip())
        figs.append({"id": f"fig-{k}", "src": f"/figures/{a.id}/{fn}", "alt": alt,
                     "caption": capby.get(k, captions[k-1] if k-1 < len(captions) else ""), "downloadable": True, "credit": ""})

    blocks, placed, hn, pn, ln = [], set(), 0, 0, 0
    for s, t in body:
        if s in ("h2", "h3"):
            hn += 1; blocks.append({"id": f"h-{hn:02d}", "type": "heading", "level": 2 if s == "h2" else 3, "text": t})
        elif s == "li":
            ln += 1; blocks.append({"id": f"l-{ln:03d}", "type": "listitem", "text": t})
        else:
            pn += 1; blocks.append({"id": f"p-{pn:03d}", "type": "paragraph", "text": t})
            for k in fig_numbers(plain(t)):
                if 1 <= k <= len(figs) and k not in placed:
                    placed.add(k); blocks.append({"id": f"f-{k:02d}", "type": "figure", "ref": f"fig-{k}"})
    for k in range(1, len(figs) + 1):
        if k not in placed: blocks.append({"id": f"f-{k:02d}", "type": "figure", "ref": f"fig-{k}"})
    notes_out = []
    for i, n in enumerate(notes, 1):
        notes_out.append({"id": f"n-{i}", "text": re.sub(r"^\s*\d+\.\s*", "", n)})

    out = os.path.join(a.root, "content", "articles", a.id); os.makedirs(out, exist_ok=True)
    def w(name, obj):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2); f.write("\n")
    w("meta.epub.json", {"articleId": a.id, "issue": a.issue, "section": a.section, "chapterFile": files[0] if len(files) == 1 else None,
        "title": title, "author": {"name": name, "affiliation": aff, "email": email, "bio": bio},
        "keywords": keywords, "abstract": abstract, "pages": pages, "datesLine": dates,
        "source": os.path.basename(a.epub), "note": "Provisional metadata from EPUB. OJS meta.json is authoritative once synced."})
    w("text.en.json", {"articleId": a.id, "lang": "en", "blocks": blocks, "notes": notes_out, "references": refs, "furtherReading": further})
    w("figures.json", {"articleId": a.id, "figures": figs})
    if not os.path.exists(os.path.join(out, "review.json")):
        w("review.json", {"text_en": {"status": "imported"}, "translation_it": {"status": "todo"},
                          "faq": {"status": "todo"}, "audio_en": {"status": "todo"}, "audio_it": {"status": "todo"}})
    words = sum(len(plain(b["text"]).split()) for b in blocks if "text" in b)
    print(json.dumps({"title": title, "author": name, "affiliation": aff, "pages": pages, "headings": hn, "paragraphs": pn,
        "listItems": ln, "figures": len(figs), "figuresPlacedByReference": sorted(placed), "notes": len(notes_out),
        "references": len(refs), "furtherReading": len(further), "bodyWords": words, "keywords": keywords,
        "altMissing": sum(1 for f in figs if not f["alt"])}, ensure_ascii=False, indent=1))
    unknown = sorted({b["raw"] for b in B if b.get("style") == "unknown"})
    if unknown: print("WARNING unmapped styles:", unknown, file=sys.stderr)

if __name__ == "__main__": main()
