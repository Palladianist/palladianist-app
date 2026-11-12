# Palladianist — app di lettura aumentata

App (PWA, poi iOS/Android con Capacitor) per la lettura aumentata di **Palladianist. The Future of Drawing**, rivista scientifica Open Access edita da INTBAU Italia APS.

- Rivista (versione di record): https://journal.palladianist.org (OJS 3.5)
- App: https://read.palladianist.org (in preparazione)
- Licenza dei contenuti: CC BY 4.0, salvo diversa indicazione nei crediti delle immagini.

## Struttura

```
content/
  issues/                 numeri (sincronizzati da OJS)
  articles/<id>/          un articolo = una cartella
    meta.json             metadati OJS (fonte autorevole)
    meta.epub.json        metadati provvisori estratti dall'EPUB
    text.en.json          testo a blocchi con ID stabili (h-01, p-001, l-001, f-01)
    text.it.json          traduzione allineata (stessi ID)
    faq.{en,it}.json      FAQ
    audio.json            episodi podcast
    figures.json          figure, didascalie, testi alternativi, crediti
    review.json           stato editoriale di ogni contenuto AI
  extra/                  call for papers, news, eventi, video, gallerie
  glossary.json           lessico disciplinare EN/IT/ES
public/figures/<id>/      immagini delle figure
scripts/                  pipeline editoriale
```

## Pipeline

1. `python3 scripts/import_epub.py <file.epub> <id> --issue v1n1 --section editorial`
2. Traduzione, FAQ e copione podcast (assistiti da AI, rivisti dalla redazione)
3. Audio (NotebookLM) → Cloudflare R2
4. Embedding → Cloudflare Vectorize
5. Revisione in `review.json`: in app compare solo ciò che è `reviewed` o `published`.

Regole: l'originale inglese è la versione di record; ogni contenuto AI è etichettato e rivisto; nessun tracciamento degli utenti.
