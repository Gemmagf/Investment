#!/usr/bin/env python3
"""
Genera news/news.json: un recull de notícies objectives, en català, per a la
pàgina news/index.html.

Flux:
  1. Llegeix fonts RSS (món, UBS, Suïssa, Catalunya, Espanya, tecnologia, recerca).
  2. Neteja, descarta esports/famosos/sensacionalisme, elimina duplicats.
  3. Si hi ha ANTHROPIC_API_KEY: Claude tria les notícies rellevants i redacta
     un titular descriptiu i un resum breu en català.
     Si no: selecció per regles i traducció automàtica (Google Translate gratuït).
  4. Fusiona amb el news.json anterior (es conserven 48 h) i el desa.

Ús:  python news/build_news.py                      (des de l'arrel del repositori)
     python news/build_news.py --candidates cand.json   només recull candidates (per a una sessió de Claude)
     python news/build_news.py --selection sel.json     escriu news.json a partir d'una selecció ja redactada
"""
from __future__ import annotations

import calendar
import difflib
import html
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "news.json"

USER_AGENT = "Mozilla/5.0 (compatible; noticies-ca/1.0; +https://github.com/gemmagf/investment)"
MAX_AGE_CANDIDATES = timedelta(hours=36)   # finestra de notícies noves
MAX_AGE_BY_CATEGORY = {"ubs": timedelta(hours=72)}  # poc volum: finestra més llarga
KEEP_PUBLISHED = timedelta(hours=48)        # quant de temps es conserven al JSON
MAX_TOTAL = 70

# Categories (clau -> etiqueta en català i màxim de notícies noves per execució)
CATEGORIES = {
    "ubs":        {"label": "UBS",        "max": 5},
    "suissa":     {"label": "Suïssa",     "max": 6},
    "catalunya":  {"label": "Catalunya",  "max": 6},
    "espanya":    {"label": "Espanya",    "max": 5},
    "mon":        {"label": "Món",        "max": 10},
    "tecnologia": {"label": "Tecnologia", "max": 7},
    "recerca":    {"label": "Recerca",    "max": 7},
}


def gnews(query: str, hl: str = "en-US", gl: str = "US", ceid: str = "US:en") -> str:
    from urllib.parse import quote
    return f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"


# (nom, url, idioma, categoria per defecte)
SOURCES = [
    # --- UBS ---
    ("Google News · UBS", gnews('UBS -"UBS Arena" -Islanders when:3d', "en-CH", "CH", "CH:en"), "en", "ubs"),
    ("finews", "https://www.finews.com/news/english-news?format=feed&type=rss", "en", "ubs"),
    # --- Suïssa ---
    ("SRF", "https://www.srf.ch/news/bnf/rss/1646", "de", "suissa"),
    ("NZZ in English", "https://www.nzz.ch/english.rss", "en", "suissa"),
    ("swissinfo", gnews("site:swissinfo.ch when:2d", "en-CH", "CH", "CH:en"), "en", "suissa"),
    # --- Catalunya ---
    ("Ara · Política", "https://www.ara.cat/rss/politica/", "ca", "catalunya"),
    ("Ara · Economia", "https://www.ara.cat/rss/economia/", "ca", "catalunya"),
    ("El Periódico", "https://www.elperiodico.cat/ca/rss/rss_portada.xml", "ca", "catalunya"),
    ("VilaWeb", "https://www.vilaweb.cat/feed/", "ca", "catalunya"),
    # --- Espanya ---
    ("El País", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada", "es", "espanya"),
    ("RTVE", "https://api2.rtve.es/rss/temas_noticias.xml", "es", "espanya"),
    ("EFE", gnews("site:efe.com", "es", "ES", "ES:es"), "es", "espanya"),
    ("Europa Press", "https://www.europapress.es/rss/rss.aspx", "es", "espanya"),
    # --- Món (política, tractats, decisions, conflictes) ---
    ("Reuters", gnews("site:reuters.com world", "en-US", "US", "US:en"), "en", "mon"),
    ("AP News", gnews("site:apnews.com", "en-US", "US", "US:en"), "en", "mon"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "en", "mon"),
    ("The Guardian · World", "https://www.theguardian.com/world/rss", "en", "mon"),
    ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "en", "mon"),
    ("Comissió Europea", "https://ec.europa.eu/commission/presscorner/api/rss?language=en", "en", "mon"),
    ("Euronews", "https://www.euronews.com/rss", "en", "mon"),
    # --- Tecnologia i desenvolupament ---
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "en", "tecnologia"),
    ("The Verge", "https://www.theverge.com/rss/index.xml", "en", "tecnologia"),
    ("TechCrunch", "https://techcrunch.com/feed/", "en", "tecnologia"),
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", "en", "tecnologia"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", "en", "tecnologia"),
    ("Hacker News", "https://hnrss.org/frontpage", "en", "tecnologia"),
    # --- Recerca i ciència ---
    ("Nature", "https://www.nature.com/nature.rss", "en", "recerca"),
    ("Science", "https://www.science.org/rss/news_current.xml", "en", "recerca"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/top/science.xml", "en", "recerca"),
    ("The Guardian · Science", "https://www.theguardian.com/science/rss", "en", "recerca"),
    ("BBC Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "en", "recerca"),
]

# Paraules que indiquen esports, famosos o sensacionalisme: es descarten sempre.
EXCLUDE = re.compile(
    r"\b(fútbol|futbol|football|soccer|barça|barca|real madrid|liga|laliga|champions|premier league|"
    r"nba|nfl|mlb|tennis|tenis|wimbledon|roland garros|golf|formula 1|f1|motogp|moto gp|grand prix|gran premio|gran premi|"
    r"\bgp\b|márquez|marquez|verstappen|olympic|olímpic|golf\w*|nhl|islanders|yamal|\bcf\b|\bfc\b|"
    r"playoff|derbi|derby|entrenador|coach|fitxatge|fichaje|transfer window|"
    r"world cup|mundial de futbol|copa del rey|copa del rei|rugby|cricket|boxing|ufc|cycling|ciclismo|ciclisme|"
    r"ski|esquí|hockey|handball|handbol|basquet|bàsquet|basketball|marathon|marató|"
    r"celebrity|celebrit|kardashian|royal family|família reial|familia real|príncipe|prince harry|meghan|"
    r"oscar|grammy|emmy|eurovision|eurovisión|eurovisió|netflix|hbo|disney\+|taylor swift|beyonc|reality|"
    r"horóscopo|horòscop|horoscope|recipe|recepta|receta|gossip|cotilleo|"
    r"bilder der woche|imatges de la setmana|pictures of the week|in pictures|en imágenes|en imatges|fotogaler|"
    r"en directe|en directo|live blog|live updates|minuto a minuto|tech now|les portades|las portadas|front pages|"
    r"millor valorats|mejor valorados|los mejores|les millors|best .{0,20} to buy|ofertas|ofertes|black friday|"
    r"jubilar|retire abroad|mascotes|mascotas|\bpets?\b|"
    r"you won'?t believe|shocking|impactante|impactant|brutal|viral|escalofriante|esgarrifós)\b",
    re.IGNORECASE,
)

# Per a la categoria UBS només volem coses que la mencionin de debò.
UBS_RE = re.compile(r"\bUBS\b(?!\s+Arena)")
# Notes d'analistes ("X maintained at Buy by UBS", objectius de preu...): no són notícies sobre el banc.
UBS_JUNK = re.compile(
    r"price target|maintain|reiterat|\brating|upgrade|downgrade|\bbuy\b|\bsell\b|\bhold\b|neutral|"
    r"outperform|underperform|overweight|underweight|analyst|moomoo|marketbeat|stock forecast|"
    r"says UBS|according to UBS|UBS says|UBS hike|UBS cut|UBS lift|UBS raise|UBS lower|UBS trim|UBS sees|"
    r"timothysykes|marketscreener|seekingalpha|tipranks|benzinga|investing\.com|stocktitan|insidermonkey",
    re.IGNORECASE,
)


# ---------------------------------------------------------------- utilitats
def strip_html(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def similar(a: str, b: str) -> bool:
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    jacc = len(ta & tb) / max(1, len(ta | tb))
    return jacc >= 0.6 or difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def entry_time(e) -> datetime:
    for k in ("published_parsed", "updated_parsed", "created_parsed"):
        tp = e.get(k)
        if tp:
            try:
                return datetime.fromtimestamp(calendar.timegm(tp), tz=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def fetch(source):
    name, url, lang, cat = source
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        d = feedparser.parse(r.content)
    except Exception as ex:  # una font caiguda no ha d'aturar la resta
        print(f"  ! {name}: {ex}", file=sys.stderr)
        return []
    is_gnews = "news.google.com" in url
    items = []
    for e in d.entries:
        title = strip_html(e.get("title"))
        title = re.sub(r"^\s*(\[[^\]]{1,25}\]|(V[IÍ]DEOS?|FOTOS?|DIRECT[EO]|LIVE)\s*[|:–-])\s*", "", title, flags=re.I).strip()
        link = e.get("link") or ""
        if not title or not link:
            continue
        publisher = name
        summary = strip_html(e.get("summary") or e.get("description"))
        if is_gnews:
            # Google News: "Titular - Mitjà" i el resum només conté enllaços.
            src = e.get("source")
            if src and src.get("title"):
                publisher = src["title"]
                if title.endswith(" - " + publisher):
                    title = title[: -len(publisher) - 3].strip()
            else:
                title = re.sub(r"\s+-\s+[^-]{2,40}$", "", title)
            summary = ""
        if len(summary) > 600:
            summary = summary[:597].rsplit(" ", 1)[0] + "…"
        items.append({
            "title_orig": title,
            "summary_orig": summary,
            "url": link,
            "source": publisher,
            "feed": name,
            "lang": lang,
            "category": cat,
            "published": entry_time(e),
        })
    print(f"  · {name}: {len(items)}", file=sys.stderr)
    return items


def load_previous() -> list[dict]:
    if not OUT.exists():
        return []
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data.get("items", [])
    except Exception:
        return []


# ---------------------------------------------------------------- candidats
def collect_candidates(previous: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    print("Llegint fonts…", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as ex:
        raw = [it for items in ex.map(fetch, SOURCES) for it in items]

    prev_urls = {p["url"] for p in previous}
    prev_titles = [p.get("title_orig") or p["title"] for p in previous]

    cands: list[dict] = []
    for it in sorted(raw, key=lambda x: x["published"], reverse=True):
        max_age = MAX_AGE_BY_CATEGORY.get(it["category"], MAX_AGE_CANDIDATES)
        if now - it["published"] > max_age or it["published"] > now + timedelta(hours=2):
            continue
        text = it["title_orig"] + " " + it["summary_orig"]
        if EXCLUDE.search(text):
            continue
        if it["category"] == "ubs" and (not UBS_RE.search(text) or UBS_JUNK.search(text + " " + it["source"])):
            continue
        if it["url"] in prev_urls or any(similar(it["title_orig"], t) for t in prev_titles):
            continue  # ja publicada
        if any(similar(it["title_orig"], c["title_orig"]) for c in cands):
            continue  # duplicat d'una altra font
        cands.append(it)

    # Limita per categoria amb rotació de fonts perquè no en domini cap.
    limited: list[dict] = []
    for cat in CATEGORIES:
        pool = [c for c in cands if c["category"] == cat]
        by_feed: dict[str, list[dict]] = {}
        for c in pool:
            by_feed.setdefault(c["feed"], []).append(c)
        picked: list[dict] = []
        cap = CATEGORIES[cat]["max"] * 4
        while len(picked) < cap and any(by_feed.values()):
            for feed in list(by_feed):
                if by_feed[feed]:
                    picked.append(by_feed[feed].pop(0))
                if len(picked) >= cap:
                    break
        limited.extend(picked)
    print(f"Candidates: {len(limited)} (de {len(raw)} entrades)", file=sys.stderr)
    return limited


# ---------------------------------------------------------------- Claude
SYSTEM_PROMPT = """Ets l'editor d'un butlletí personal de notícies en català per a una persona catalana que viu a Suïssa i treballa a UBS.

Rebràs una llista de notícies candidates (titular, resum i font originals, en diversos idiomes). La teva feina:

1. SELECCIONAR només les que compleixin aquests criteris:
   - Fets rellevants i objectius: política general (tractats, acords, decisions de governs i institucions, eleccions, conflictes), economia i regulació, tecnologia i desenvolupament d'aplicacions, recerca i ciència (publicacions noves, avenços).
   - Prioritat a: coses que afecten UBS o la banca suïssa; Suïssa; Catalunya; una mica d'Espanya; grans esdeveniments mundials.
   - DESCARTA: esports, famosos, entreteniment, successos locals menors, opinió, articles promocionals, llistes ("10 coses..."), i tot allò sensacionalista o especulatiu.
   - Si dues candidates parlen del mateix fet, queda-te'n només una (la font més fiable o completa).
   - Respecta els màxims per categoria que t'indicaré. Si una categoria no té res prou rellevant, en pots triar menys o cap.

2. Per a cada notícia triada, REDACTAR en català:
   - "title": un titular DESCRIPTIU i neutre de màxim 90 caràcters. Ha de dir què ha passat, qui i on, perquè s'entengui d'un cop d'ull. Sense adjectius valoratius, sense majúscules d'èmfasi, sense signes d'exclamació, sense preguntes retòriques, sense clickbait.
   - "summary": un resum factual de 2 o 3 frases (entre 200 i 380 caràcters) amb el context mínim per entendre la notícia: què, qui, quan, per què importa. No afegeixis informació que no sigui a la candidata; si el resum original és buit, basa't només en el titular i no inventis detalls.
   - "category": una de: ubs, suissa, catalunya, espanya, mon, tecnologia, recerca. Reassigna-la si cal (p. ex. una notícia del Govern suís trobada en una font mundial va a "suissa"; una notícia que menciona UBS va a "ubs").
   - "importance": enter de 1 (menor) a 5 (molt rellevant per a aquesta persona).

Escriu en català normatiu (no en castellà ni en anglès), amb noms propis i sigles tal com es coneixen. Retorna només el JSON demanat."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "importance": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["id", "title", "summary", "category", "importance"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def select_with_claude(cands: list[dict]) -> list[dict] | None:
    import anthropic

    client = anthropic.Anthropic()
    limits = ", ".join(f"{k}: màx. {v['max']}" for k, v in CATEGORIES.items())
    lines = []
    for i, c in enumerate(cands):
        lines.append(
            f"[{i}] ({c['category']}, {c['lang']}, {c['source']}, {c['published'].strftime('%Y-%m-%d %H:%M')} UTC)\n"
            f"Titular: {c['title_orig']}\n"
            + (f"Resum: {c['summary_orig']}\n" if c["summary_orig"] else "")
        )
    user = (
        f"Data i hora actual: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC.\n"
        f"Màxims per categoria: {limits}.\n\n"
        "Candidates:\n\n" + "\n".join(lines)
    )
    try:
        response = client.messages.create(
            model="claude-opus-5-5",
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
        )
    except anthropic.APIError as ex:
        print(f"  ! Claude: {ex}", file=sys.stderr)
        return None
    if response.stop_reason not in ("end_turn", "stop_sequence"):
        print(f"  ! Claude s'ha aturat per: {response.stop_reason}", file=sys.stderr)
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as ex:
        print(f"  ! JSON invàlid de Claude: {ex}", file=sys.stderr)
        return None

    out = []
    seen = set()
    for row in data.get("items", []):
        i = row.get("id")
        if not isinstance(i, int) or not (0 <= i < len(cands)) or i in seen:
            continue
        seen.add(i)
        c = cands[i]
        out.append({**c, "title": row["title"].strip(), "summary": row["summary"].strip(),
                    "category": row["category"], "importance": int(row["importance"])})
    print(f"Claude ha triat {len(out)} notícies "
          f"(tokens: {response.usage.input_tokens} entrada, {response.usage.output_tokens} sortida)",
          file=sys.stderr)
    return out


# ---------------------------------------------------------------- reserva sense clau
def translate_ca(text: str, src: str) -> str:
    if not text or src == "ca":
        return text
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": src, "tl": "ca", "dt": "t", "q": text},
            timeout=15, headers={"User-Agent": USER_AGENT},
        )
        r.raise_for_status()
        return "".join(seg[0] for seg in r.json()[0] if seg and seg[0]).strip() or text
    except Exception as ex:
        print(f"  ! traducció: {ex}", file=sys.stderr)
        return text


def select_by_rules(cands: list[dict]) -> list[dict]:
    out = []
    for cat, cfg in CATEGORIES.items():
        pool = [c for c in cands if c["category"] == cat]
        # Rotació de fonts, després les més recents.
        by_feed: dict[str, list[dict]] = {}
        for c in pool:
            by_feed.setdefault(c["feed"], []).append(c)
        picked: list[dict] = []
        while len(picked) < cfg["max"] and any(by_feed.values()):
            for feed in list(by_feed):
                if by_feed[feed]:
                    picked.append(by_feed[feed].pop(0))
                if len(picked) >= cfg["max"]:
                    break
        out.extend(picked)
    for c in out:
        c["title"] = translate_ca(c["title_orig"], c["lang"])
        summ = c["summary_orig"]
        if len(summ) > 380:
            summ = summ[:377].rsplit(" ", 1)[0] + "…"
        c["summary"] = translate_ca(summ, c["lang"]) if summ else ""
        c["importance"] = 4 if c["category"] in ("ubs", "suissa", "catalunya") else 3
        time.sleep(0.2)
    print(f"Selecció per regles: {len(out)} notícies (traducció automàtica)", file=sys.stderr)
    return out


# ---------------------------------------------------------------- principal
def dump_candidates(cands: list[dict], path: Path) -> None:
    """Desa les candidates perquè una sessió de Claude (sense clau d'API) les triï i redacti."""
    rows = [{k: (v.isoformat(timespec="minutes") if k == "published" else v) for k, v in c.items()} for c in cands]
    path.write_text(json.dumps({
        "instructions": SYSTEM_PROMPT,
        "limits": {k: v["max"] for k, v in CATEGORIES.items()},
        "output_schema": OUTPUT_SCHEMA,
        "candidates": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Desades {len(rows)} candidates a {path}", file=sys.stderr)


def apply_selection(cands: list[dict], path: Path) -> list[dict]:
    """Llegeix una selecció amb el format d'OUTPUT_SCHEMA (id, title, summary, category, importance)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out, seen = [], set()
    for row in data.get("items", []):
        i = row.get("id")
        if not isinstance(i, int) or not (0 <= i < len(cands)) or i in seen:
            continue
        if row.get("category") not in CATEGORIES:
            continue
        seen.add(i)
        out.append({**cands[i], "title": str(row["title"]).strip(), "summary": str(row.get("summary", "")).strip(),
                    "category": row["category"], "importance": max(1, min(5, int(row.get("importance", 3))))})
    print(f"Selecció aplicada: {len(out)} notícies", file=sys.stderr)
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=Path, help="desa les candidates en aquest fitxer i surt")
    ap.add_argument("--selection", type=Path, help="selecció redactada (JSON) per generar news.json")
    args = ap.parse_args()

    previous = load_previous()
    if args.selection:
        cand_file = args.selection.with_name("candidates.json")
        if not cand_file.exists():
            print(f"Cal {cand_file} (generat amb --candidates)", file=sys.stderr)
            return 1
        raw = json.loads(cand_file.read_text(encoding="utf-8"))["candidates"]
        cands = [{**c, "published": datetime.fromisoformat(c["published"])} for c in raw]
        chosen, mode = apply_selection(cands, args.selection), "claude"
    else:
        cands = collect_candidates(previous)
        if args.candidates:
            dump_candidates(cands, args.candidates)
            return 0
        chosen = None
        if cands and os.environ.get("ANTHROPIC_API_KEY"):
            chosen = select_with_claude(cands)
            mode = "claude"
        if chosen is None:
            chosen = select_by_rules(cands) if cands else []
            mode = "traduccio"

    now = datetime.now(timezone.utc)
    new_items = []
    for c in chosen:
        new_items.append({
            "id": re.sub(r"[^a-z0-9]+", "-", c["url"].lower())[-80:].strip("-"),
            "title": c["title"],
            "summary": c["summary"],
            "title_orig": c["title_orig"],
            "url": c["url"],
            "source": c["source"],
            "lang": c["lang"],
            "category": c["category"],
            "importance": c["importance"],
            "published": c["published"].isoformat(timespec="minutes"),
            "added": now.isoformat(timespec="minutes"),
        })

    kept = []
    for p in previous:
        try:
            pub = datetime.fromisoformat(p["published"])
        except Exception:
            continue
        if now - pub <= KEEP_PUBLISHED and p.get("category") in CATEGORIES:
            kept.append(p)

    items = new_items + kept
    items.sort(key=lambda x: (x["published"]), reverse=True)
    items = items[:MAX_TOTAL]

    OUT.write_text(json.dumps({
        "generated_at": now.isoformat(timespec="minutes"),
        "mode": mode,
        "categories": {k: v["label"] for k, v in CATEGORIES.items()},
        "items": items,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Desat {OUT.relative_to(HERE.parent)}: {len(new_items)} noves, {len(items)} en total ({mode})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
