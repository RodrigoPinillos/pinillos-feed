#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera el feed de Google Merchant Center para pinillos.com.ar
Scrapea el catálogo en vivo (no depende de archivos previos) y escribe un TSV.

Uso:  python3 build_feed.py [salida.tsv]
Salida por defecto: google_merchant_feed_pinillos.tsv (en el directorio actual)
"""
import re, html, os, sys, csv, time, ssl, urllib.request

# Contextos SSL: normal y, como fallback, sin verificar (algunos entornos hacen MITM/self-signed)
_CTX = ssl.create_default_context()
_CTX_NOVERIFY = ssl._create_unverified_context()

BASE = "https://www.pinillos.com.ar"
IMG_HOST = "https://plataforma.iduo.com.ar/"
IVA = 1.21  # +21% -> precio final al consumidor

# --- Marcas: override manual (gana sobre lo que diga la web) ---
BRAND_OVERRIDE = {
    "Pantalon-gabardina-pinzado": "Polo Men's",
    "Buzo-de-algodon-frisado-negro": "Humberto Chietti",
    "Buzo-de-algodon-frisado-azul": "Humberto Chietti",
}
# Marcas conocidas para inferir desde el título cuando la ficha no la trae
KNOWN_BRANDS = ["Rica Lewis","Aire Libre","Umberto Chietti","Polo Men's","Eyelit","Bravo",
    "Ombu","Pampero","Primus","Snipe","Cotar","Dufour","Aero","Warrior","Confortable",
    "Arciel","Pisfer","Floyd","Buffalo","Ritmo","Monaco","Elemento","Everlast","Esquel","Dior"]

UA = {"User-Agent": "Mozilla/5.0 (feed-builder Pinillos)"}

_ACTIVE_CTX = None  # se decide una vez en la 1ª llamada

def _pick_ctx(url):
    """Elige contexto SSL una sola vez: verificado si funciona; si no, sin verificar
    (algunos entornos hacen MITM con cert self-signed)."""
    global _ACTIVE_CTX
    for ctx in (_CTX, _CTX_NOVERIFY):
        try:
            req = urllib.request.Request(url, headers=UA)
            urllib.request.urlopen(req, timeout=45, context=ctx).read(64)
            _ACTIVE_CTX = ctx
            return
        except Exception:
            continue
    _ACTIVE_CTX = _CTX_NOVERIFY  # último recurso

def fetch(url, tries=3):
    if _ACTIVE_CTX is None:
        _pick_ctx(url)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=_ACTIVE_CTX) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            if i < tries-1: time.sleep(2)
    print(f"  ! error {url}: {last}", file=sys.stderr)
    return ""

def clean(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()

def _dedup(vals):
    seen=set(); out=[]
    for v in vals:
        if v and v not in seen:
            seen.add(v); out.append(v)
    return out

def enumerate_slugs():
    """Recorre las páginas del catálogo (PAGSINHTML) hasta que no haya más productos."""
    slugs = []
    np = 1
    empty = 0
    while np <= 30 and empty < 2:
        url = (f"{BASE}/Productos.html?PAGSINHTML=Mostrarproductos&buscado=&preciomin="
               f"&preciomax=&orden=0&rubro=&marca=&tipoaviso=&talle=&np={np}")
        h = fetch(url)
        found = re.findall(r'href="([A-Za-z0-9][^"]*\.html)"', h)
        # filtrar utilitarios
        found = [s for s in found if not re.match(
            r'(Inicio|Productos|Contacto|Nosotros|Blog|Clientes|Carrito|Login|Micuenta|Mi-cuenta)\.html', s)]
        found = _dedup(found)
        if not found:
            empty += 1
        else:
            empty = 0
            slugs += found
        np += 1
    return _dedup(slugs)

def get_marca_field(t):
    m = re.search(r'>Marca:?(?:&nbsp;|\s)*</label>\s*([^<\n]+)', t, re.I)
    return clean(m.group(1)) if m else ""

def get_colors(t):
    return _dedup([clean(c) for c in re.findall(r"nombrecolor\s*=\s*'([^']+)'", t)])

def get_talles(t):
    m = re.search(r'data-attribute_name="attribute_pa_size".*?</ul>', t, re.S|re.I)
    if not m: return []
    return _dedup([clean(x) for x in re.findall(r'__name">(.*?)</span>', m.group(0), re.S|re.I)])

def infer_brand(title):
    low = title.lower()
    for b in KNOWN_BRANDS:
        if b.lower() in low:
            return b
    return ""

def google_category(title, leaf):
    s = (title + " " + leaf).lower()
    def has(*ws): return any(w in s for w in ws)
    if has('boxer','slip','calzoncillo'):
        return "Apparel & Accessories > Clothing > Underwear & Socks > Underwear"
    if has('media','medias'):
        return "Apparel & Accessories > Clothing > Underwear & Socks > Socks"
    if has('faja'):
        return "Health & Beauty > Health Care > Supports & Braces"
    if has('campera','chaleco','trucker'):
        return "Apparel & Accessories > Clothing > Outerwear > Coats & Jackets"
    if has('bermuda'):
        return "Apparel & Accessories > Clothing > Shorts"
    if has('jean','pantalon','bombacha','cargo','gabardina'):
        return "Apparel & Accessories > Clothing > Pants"
    if has('bota','botin','zapato','zapatilla','alpargata'):
        return "Apparel & Accessories > Shoes"
    if has('ambo','arciel'):
        return "Apparel & Accessories > Clothing > Uniforms"
    if has('remera','chomba','camiseta','camisa','pullover','buzo','sweater'):
        return "Apparel & Accessories > Clothing > Shirts & Tops"
    return "Apparel & Accessories > Clothing"

def parse_ficha(slug, t):
    name = re.search(r"'item_name'\s*:\s*'([^']*)'", t)
    pid  = re.search(r"'item_id'\s*:\s*'([^']*)'", t)
    price = re.search(r"'price'\s*:\s*'([^']*)'", t)
    if not (name and pid and price): return None
    name = clean(name.group(1)); pid = pid.group(1).strip()
    try:
        base = float(price.group(1).strip())
    except: return None
    if not (name and pid and base > 0): return None
    final = round(base * IVA, 2)

    ogurl = re.search(r"og:url'\s*content='([^']+)'", t)
    link = ogurl.group(1).rstrip('?') if ogurl else f"{BASE}/{slug}"

    ogimg = re.search(r"og:image'\s*content='([^']+)'", t)
    img = ogimg.group(1).replace('/iPlataformamultiempresa/', '/') if ogimg else ""
    addl = []
    if img:
        m = re.match(r'(.+-\d+)-0-0\.(webp|jpg|jpeg|png)', os.path.basename(img), re.I)
        if m:
            prefix = m.group(1)
            for u in _dedup(re.findall(
                    r'Panelcontenidos/Contenidos/'+re.escape(prefix)+r'-0-\d+\.(?:webp|jpg|jpeg|png)', t)):
                full = IMG_HOST + u
                if not re.search(r'-0-0\.(webp|jpg|jpeg|png)$', full, re.I):
                    addl.append(full)
            addl = addl[:10]

    # marca: override -> ficha -> inferida -> Pinillos
    stem = slug[:-5] if slug.endswith('.html') else slug
    stem = re.sub(r'_\d+$', '', stem)
    brand = BRAND_OVERRIDE.get(stem) or get_marca_field(t) or infer_brand(name) or "Pinillos"

    colors = get_colors(t); talles = get_talles(t)
    h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', t, re.S)
    leaf = clean(h2s[0]) if h2s else ""

    md = re.search(r'id="pd_description"[^>]*>(.*?)</div>', t, re.S|re.I)
    desc = clean(md.group(1)) if md else ""
    desc = re.sub(r'^Descripci[oó]n\s*', '', desc, flags=re.I).strip()
    if len(desc) < 30:
        extra = []
        if colors: extra.append("Colores: "+", ".join(colors))
        if talles: extra.append("Talles: "+", ".join(talles))
        desc = f"{name}. Marca {brand}. " + ". ".join(extra) + ". Indumentaria y calzado de trabajo Pinillos."
    desc = desc[:4900]

    return {
        'id': pid, 'title': name[:150], 'description': desc, 'link': link,
        'image_link': img, 'additional_image_link': ",".join(addl),
        'availability': 'in_stock', 'price': f"{final:.2f} ARS", 'condition': 'new',
        'brand': brand, 'google_product_category': google_category(name, leaf),
        'product_type': leaf, 'identifier_exists': 'no',
    }

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "google_merchant_feed_pinillos.tsv"
    print("Enumerando catálogo...")
    slugs = enumerate_slugs()
    print(f"  {len(slugs)} productos encontrados")
    rows = []
    for i, slug in enumerate(slugs, 1):
        t = fetch(f"{BASE}/{slug}")
        r = parse_ficha(slug, t)
        if r: rows.append(r)
        if i % 20 == 0: print(f"  ...{i}/{len(slugs)}")
    cols = ['id','title','description','link','image_link','additional_image_link',
            'availability','price','condition','brand','google_product_category',
            'product_type','identifier_exists']
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter='\t', extrasaction='ignore')
        w.writeheader()
        for r in rows: w.writerow(r)
    print(f"OK -> {out}  ({len(rows)} productos)")
    return 0 if rows else 1

if __name__ == "__main__":
    sys.exit(main())
