# Notícies al dia

Pàgina petita, pensada per a l'iPhone, amb un giny que va rotant notícies i una llista per categories:
**UBS · Suïssa · Catalunya · Espanya · Món · Tecnologia · Recerca**. Tot en català, amb titulars
descriptius, un resum curt i l'enllaç a la font original.

## Com funciona

```
fonts RSS  ──▶  news/build_news.py  ──▶  news/news.json  ──▶  news/index.html
(BBC, Reuters, SRF,    filtra esports/famosos,     (dades)         (la pàgina)
 NZZ, Ara, El País,    treu duplicats, tria i
 Nature, Science…)     redacta en català
```

- `build_news.py` llegeix una trentena de fonts (vegeu `SOURCES` dins del fitxer), descarta esports,
  famosos i sensacionalisme, elimina duplicats i es queda amb les notícies de les darreres 36 h.
- **Amb `ANTHROPIC_API_KEY`** (recomanat): Claude tria les notícies rellevants segons els criteris
  (política general, tractats, decisions, conflictes, banca suïssa, Catalunya, tecnologia, recerca)
  i redacta per a cadascuna un titular descriptiu i neutre i un resum de 2-3 frases en català.
- **Sense clau**: selecció per regles i traducció automàtica del titular i el resum originals
  (la pàgina ho indica amb «traducció automàtica»). Funciona, però la qualitat dels titulars és la de la font.
- La GitHub Action `.github/workflows/noticies.yml` ho executa cada 3 hores i publica `news.json`.
- `index.html` només llegeix `news.json`: no cal servidor ni base de dades.

## Posada en marxa (un sol cop)

1. **Secret opcional**: a GitHub, *Settings → Secrets and variables → Actions → New repository secret*,
   nom `ANTHROPIC_API_KEY`. Sense secret la pàgina funciona igualment en mode traducció.
2. **GitHub Pages**: *Settings → Pages → Build and deployment → Source: Deploy from a branch*,
   branca `main`, carpeta `/ (root)`. Al cap d'un minut la pàgina queda a
   `https://gemmagf.github.io/investment/news/`.
3. **Primera execució**: *Actions → Actualitza notícies → Run workflow* (o espera la propera hora programada).
4. **A l'iPhone**: obre l'adreça a Safari, *Compartir → Afegir a la pantalla d'inici*. S'obre com una app.

## Executar-ho en local

```bash
pip install -r news/requirements.txt
python news/build_news.py            # genera news/news.json (1-3 minuts)
python -m http.server 8000           # i obre http://localhost:8000/news/
```

## Ajustos habituals

- Afegir o treure fonts: llista `SOURCES` a `build_news.py` (nom, URL del RSS, idioma, categoria).
- Quantes notícies per categoria: diccionari `CATEGORIES`.
- Paraules a descartar: expressió `EXCLUDE`.
- Freqüència: `cron` al workflow (`17 */3 * * *` = cada 3 hores).
- Velocitat de rotació del giny: `ROTATE_MS` a `index.html` (8 segons).
