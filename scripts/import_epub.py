#!/usr/bin/env python3
"""Import an InDesign reflowable EPUB into the Palladianist content model.

Usage: python3 scripts/import_epub.py <file.epub> <article-id> [--issue v1n1] [--section editorial]

Writes content/articles/<id>/{meta.epub.json,text.en.json,figures.json,review.json}
and copies figures to public/figures/<id>/.
Mapping is based on InDesign paragraph-style class names (see STYLE_MAP), so
export tags are not required. Standard library only.
"""
import argparse, html, json, os, re, shutil, sys, zipfile
from html.parser import HTMLParser

STYLE_MAP = {            # InDesign paragraph style -> block role
    "Heading-1": "h2",
    "Normal": "p",
    "List-Paragraph": "li",
    "abstract": "abstract",
    "parole-chiave": "keyword",
    "didascalie": "caption",
    "References": "reference",
    "affiliazione-autore": "author",
    "titolo-sottoparagrafo": "front",
    "Paragrafo-base": "front",
}

class Doc(HTMLParser):
    def __init__(self, italic_classes):
        super().__init__(convert_charrefs=True)
        self.italic = italic_classes
        self.blocks, self.cur, self.stack = [], None, []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag in ("p", "li", "h1", "h2", "h3", "h4"):
            style = next((STYLE_MAP[c] for c in cls if c in STYLE_MAP), None)
            self.cur = {"style": style or "unknown", "raw": " ".join(cls), "html": ""}
        elif tag == "img":
            self.blocks.append({"style": "img", "src": a.get("src", ""), "alt": a.get("alt", "")})
        elif tag == "span" and self.cur is not None:
            it = any(c in self.italic for c in cls)
            self.stack.append(it)
            if it: self.cur["html"] += "<em>"
        elif tag == "br" and self.cur is not None:
            self.cur["html"] += " "
    def handle_endtag(self, tag):
        if tag == "span" and self.cur is not None and self.stack:
            if self.stack.pop(): self.cur["html"] += "</em>"
        elif tag in ("p", "li", "h1", "h2", "h3", "h4") and self.cur is not None:
            t = re.sub(r"\s+", " ", self.cur["html"]).strip()
            t = t.replace("<em></em>", "").replace("</em><em>", "")
            if re.sub(r"<[^>]+>", "", t).strip():
                self.cur["html"] = t
                self.blocks.append(self.cur)
            self.cur = None
    def handle_data(self, data):
        if self.cur is not None:
            self.cur["html"] += html.escape(data, quote=False)

def italic_classes(css):
    out = set()
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        if re.search(r"font-style\s*:\s*italic", body):
            out.update(re.findall(r"span\.([\w-]+)", sel))
    return out

def plain(h): return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("epub"); ap.add_argument("id")
    ap.add_argument("--issue", default=""); ap.add_argument("--section", default="")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()
    z = zipfile.ZipFile(a.epub)
    names = z.namelist()
    css = "".join(z.read(n).decode("utf-8", "ignore") for n in names if n.endswith(".css"))
    xhtml = [n for n in names if n.endswith(".xhtml") and not re.search(r"(cover|toc|nav)\.xhtml$", n)]
    doc = Doc(italic_classes(css))
    for n in xhtml: doc.feed(z.read(n).decode("utf-8"))
    B = doc.blocks

    meta = {"title": [], "authors": [], "keywords": [], "abstract": [], "front": []}
    body, refs, figs, captions, pending_img = [], [], [], [], []
    started = False
    for b in B:
        s = b["style"]
        if s == "img":
            pending_img.append(b); continue
        t = b["html"]
        if s == "h2": started = True
        if not started:
            {"keyword": meta["keywords"], "abstract": meta["abstract"], "author": meta["authors"]}.get(s, meta["front"]).append(plain(t))
            continue
        if s == "caption": captions.append(t); continue
        if s == "reference": refs.append(t); continue
        if s == "h2" and plain(t).lower() == "references": continue
        body.append((s, t))

    # figures: pair images (excluding licence icon/decor) with captions in order
    imgs = [i for i in pending_img if not re.search(r"(by\.png|cc_|icon|logo|sfondo|P_2)", i["src"], re.I)]
    fig_dir = os.path.join(a.root, "public", "figures", a.id); os.makedirs(fig_dir, exist_ok=True)
    base = os.path.dirname(xhtml[0])
    for k, img in enumerate(imgs, 1):
        src = os.path.normpath(os.path.join(base, img["src"])).replace("\\", "/")
        fn = os.path.basename(src)
        with z.open(src) as f, open(os.path.join(fig_dir, fn), "wb") as o: shutil.copyfileobj(f, o)
        alt = html.unescape(img["alt"]).strip()
        alt = re.sub(r"^[\w-]+\.\s+", "", alt)   # drop "fig1_pipeline. " prefix
        figs.append({"id": f"fig-{k}", "src": f"/figures/{a.id}/{fn}", "alt": alt,
                     "caption": captions[k-1] if k-1 < len(captions) else "",
                     "downloadable": True, "credit": ""})

    # body blocks with stable ids; insert figure refs after first paragraph mentioning "Fig. N"
    blocks, placed, hn, pn, ln = [], set(), 0, 0, 0
    for s, t in body:
        if s == "h2":
            hn += 1; blocks.append({"id": f"h-{hn:02d}", "type": "heading", "level": 2, "text": t})
        elif s == "li":
            ln += 1; blocks.append({"id": f"l-{ln:03d}", "type": "listitem", "text": t})
        else:
            pn += 1; blocks.append({"id": f"p-{pn:03d}", "type": "paragraph", "text": t})
            for m in re.findall(r"Fig(?:s?\.|ure)\s*(\d+)", plain(t)):
                k = int(m)
                if k <= len(figs) and k not in placed:
                    placed.add(k); blocks.append({"id": f"f-{k:02d}", "type": "figure", "ref": f"fig-{k}"})
    for k in range(1, len(figs)+1):
        if k not in placed: blocks.append({"id": f"f-{k:02d}", "type": "figure", "ref": f"fig-{k}"})

    out = os.path.join(a.root, "content", "articles", a.id); os.makedirs(out, exist_ok=True)
    def w(name, obj):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2); f.write("\n")
    w("meta.epub.json", {"articleId": a.id, "issue": a.issue, "section": a.section,
        "keywords": meta["keywords"], "abstract": meta["abstract"], "authorsRaw": meta["authors"],
        "frontMatter": meta["front"], "source": os.path.basename(a.epub),
        "note": "Provisional metadata from EPUB. OJS meta.json is authoritative once synced."})
    w("text.en.json", {"articleId": a.id, "lang": "en", "blocks": blocks, "references": refs})
    w("figures.json", {"articleId": a.id, "figures": figs})
    rv = os.path.join(out, "review.json")
    if not os.path.exists(rv):
        w("review.json", {"text_en": {"status": "imported"}, "translation_it": {"status": "todo"},
                          "faq": {"status": "todo"}, "audio_en": {"status": "todo"}, "audio_it": {"status": "todo"}})
    words = sum(len(plain(b["text"]).split()) for b in blocks if "text" in b)
    print(json.dumps({"headings": hn, "paragraphs": pn, "listItems": ln, "figures": len(figs),
                      "figuresPlacedByReference": sorted(placed), "references": len(refs),
                      "bodyWords": words, "keywords": meta["keywords"]}, ensure_ascii=False, indent=1))
    unknown = sorted({b["raw"] for b in B if b.get("style") == "unknown"})
    if unknown: print("WARNING unmapped styles:", unknown, file=sys.stderr)

if __name__ == "__main__": main()
