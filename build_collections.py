#!/usr/bin/env python3
"""Generate the browsable collections for the Gold Country Markers Catalogue.

Reads the 8 staged county JSON files and writes, into this repo:
  <county-slug>/index.html        - the county's marker list (search + family filter)
  <county-slug>/<marker-slug>.html - one detail page per marker (1,305)

It also makes three surgical additions to the summary page (index.html),
each guarded so re-running is safe:
  1. county names in the §6 ledger table link to their list pages
  2. a "§9 Browse the collections" section with one card per county
  3. a "Details ->" link in each summary-map popup (only if every map
     point matches exactly one record on (coords, name); otherwise skipped)

Run:  python3 build_collections.py
"""
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent
DATA = Path.home() / "workspace/goals/event-manager/hidden_files/event-buddy/staged-locations"

# First (marker/plaque) photo per marker, harvested from HMdb by
# harvest_photos.py: {hmdbId: {photoUrl, credit, caption}}. The photos
# are hotlinked from HMdb, never copied; the credit prints underneath.
PHOTOS_FILE = REPO / "photos.json"
PHOTOS = {}
if PHOTOS_FILE.exists():
    PHOTOS = {str(k): v for k, v in json.loads(PHOTOS_FILE.read_text()).items()}


def photo_for(r):
    return PHOTOS.get(str(r["hmdbId"]))

COUNTY_ORDER = ["El Dorado", "Nevada", "Placer", "Amador",
                "Tuolumne", "Calaveras", "Mariposa", "Sierra"]

# markerType value in the records -> (display label, colour, filter key)
FAMILIES = {
    "California Historical Landmark": ("State landmark (CHL)", "#b8860b", "chl"),
    "E Clampus Vitus":                ("E Clampus Vitus", "#9a3b26", "ecv"),
    "Native Sons/Daughters":          ("Native Sons/Daughters", "#2e5e4e", "ns"),
    "County/Local":                   ("County / Local", "#31597f", "county"),
    "Other organization":             ("Other organizations", "#8a8378", "other"),
}

BASE_CSS = """
  :root { --paper:#faf6ee; --ink:#2b2620; --muted:#6f6656; --rule:#d8cfba; --accent:#9a3b26; --gold:#b8860b; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink); font-family:Georgia,'Times New Roman',serif; line-height:1.55; }
  .wrap { max-width:860px; margin:0 auto; padding:0 18px 48px; }
  header { text-align:center; padding:34px 0 18px; border-bottom:3px double var(--ink); }
  .kicker { font-family:Helvetica,Arial,sans-serif; font-size:12px; letter-spacing:2.5px; text-transform:uppercase; color:var(--accent); margin:0 0 8px; }
  h1 { font-size:clamp(26px,6vw,40px); margin:0 0 8px; line-height:1.15; }
  .sub { color:var(--muted); font-style:italic; margin:0; font-size:clamp(15px,3.5vw,18px); }
  h2 { font-size:22px; margin:30px 0 4px; border-bottom:1px solid var(--rule); padding-bottom:6px; }
  a { color:var(--accent); }
  .crumbs { font-family:Helvetica,Arial,sans-serif; font-size:13.5px; padding:14px 0 0; }
  .crumbs a { text-decoration:none; }
  .crumbs a:hover { text-decoration:underline; }
  .badges { margin:12px 0 2px; display:flex; flex-wrap:wrap; gap:6px; justify-content:center; }
  .badge { font-family:Helvetica,Arial,sans-serif; font-size:12px; letter-spacing:.4px; border:1px solid var(--rule); background:#fffdf8; border-radius:20px; padding:3px 10px; }
  .badge .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; }
  .badge.chl { border-color:var(--gold); color:#7a5c06; font-weight:bold; }
  .note { background:#fffdf8; border:1px solid var(--rule); border-radius:6px; padding:14px 16px; margin:14px 0; }
  .note h3 { margin:0 0 4px; font-size:16px; }
  .note p { margin:0; }
  .flag { border-left:3px solid var(--accent); padding:2px 0 2px 14px; margin:14px 0; }
  .flag h3 { margin:0 0 2px; font-size:16px; }
  .flag p { margin:0; }
  .plaque { background:#fffdf8; border:1px solid var(--rule); border-radius:6px; padding:16px 18px; margin:12px 0; font-size:16.5px; }
  .plaque p { margin:0 0 10px; }
  .plaque p:last-child { margin-bottom:0; }
  .partial-tag { font-family:Helvetica,Arial,sans-serif; font-size:12px; letter-spacing:1px; text-transform:uppercase; color:var(--accent); margin:0 0 8px; }
  #minimap { height:280px; border:1px solid var(--rule); border-radius:6px; margin:12px 0 4px; z-index:0; }
  .coords { font-variant-numeric:tabular-nums; }
  footer { border-top:3px double var(--ink); margin-top:36px; padding-top:14px; color:var(--muted); font-size:14px; text-align:center; }
  /* county list pages */
  .fambreak { display:flex; flex-wrap:wrap; gap:6px 16px; font-family:Helvetica,Arial,sans-serif; font-size:13px; margin:14px 0 4px; }
  .fambreak .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }
  .filters { margin:16px 0 6px; }
  .filters input { width:100%; font-size:16px; font-family:Helvetica,Arial,sans-serif; padding:10px 12px; border:1px solid var(--rule); border-radius:6px; background:#fffdf8; color:var(--ink); }
  .fbtns { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
  .fbtn { font-family:Helvetica,Arial,sans-serif; font-size:13px; border:1px solid var(--rule); background:#fffdf8; color:var(--ink); border-radius:20px; padding:5px 12px; cursor:pointer; }
  .fbtn.on { background:var(--ink); color:var(--paper); border-color:var(--ink); }
  .showing { font-family:Helvetica,Arial,sans-serif; font-size:12.5px; color:var(--muted); margin:8px 0 0; }
  a.mrow { display:block; text-decoration:none; color:var(--ink); border-bottom:1px solid var(--rule); padding:10px 4px; }
  a.mrow:hover { background:#fffdf8; }
  a.mrow .nm { font-size:17px; }
  a.mrow .meta { font-family:Helvetica,Arial,sans-serif; font-size:12.5px; color:var(--muted); margin-top:2px; }
  a.mrow .meta .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }
  .chltag { color:#7a5c06; font-weight:bold; }
  .hidden { display:none; }
  /* must out-specify a.mrow's display (0,1,1) or filtered rows never hide */
  a.mrow.hidden { display:none; }
  /* plaque photos (hotlinked from HMdb, credit underneath) */
  .plaque-photo { margin:18px 0 4px; text-align:center; }
  .plaque-photo img { max-width:100%; height:auto; max-height:540px; border:1px solid var(--rule); border-radius:6px; background:#fffdf8; }
  .plaque-photo figcaption { font-family:Helvetica,Arial,sans-serif; font-size:12.5px; color:var(--muted); margin-top:6px; }
  a.mrow { display:flex; align-items:center; gap:12px; }
  a.mrow img.thumb { width:56px; height:56px; object-fit:cover; border-radius:6px; border:1px solid var(--rule); flex:0 0 auto; background:#fffdf8; }
  a.mrow .txt { flex:1; min-width:0; }
"""


def esc(s):
    return html.escape(str(s), quote=True)


def county_slug(name):
    return name.lower().replace(" ", "-")


def load_records():
    counties = {}
    for county in COUNTY_ORDER:
        f = DATA / f"markers-{county.lower().replace(' ', '-')}-county-staged.json"
        recs = json.loads(f.read_text())
        # browsable list: alphabetical by name
        recs.sort(key=lambda r: r["name"].lower())
        counties[county] = recs
    return counties


def head(title, desc, leaflet=False):
    leaf = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">\n' if leaflet else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{leaf}<style>{BASE_CSS}</style>
<script async src="https://visitor-counter.dave-5d7.workers.dev/beacon.js" data-site="gold-country-markers"></script>
</head>
<body>
<div class="wrap">
"""


def badges_html(r):
    label, color, _ = FAMILIES[r["markerType"]]
    out = [f'<span class="badge"><span class="dot" style="background:{color}"></span>{esc(label)}</span>']
    if r.get("chlNumber") not in (None, ""):
        out.append(f'<span class="badge chl">California Historical Landmark No. {esc(r["chlNumber"])}</span>')
    out.append(f'<span class="badge">{esc(r["county"])} County</span>')
    return '<div class="badges">' + "".join(out) + "</div>"


def detail_page(r, cslug):
    label, color, _ = FAMILIES[r["markerType"]]
    lat, lon = r["latitude"], r["longitude"]
    art = "an" if label[0].lower() in "aeiou" else "a"
    parts = [head(f'{r["name"]} — {r["county"]} County · Reading the Roadside',
                  f'{r["name"]}: {art} {label} marker in {r["city"]}, {r["county"]} County — its location and the words on its face.',
                  leaflet=True)]
    parts.append(f"""<p class="crumbs"><a href="../index.html">&larr; The catalogue</a> &nbsp;·&nbsp; <a href="index.html">&larr; {esc(r['county'])} County markers</a></p>
<header>
  <p class="kicker">Gold Country · {esc(r['county'])} County</p>
  <h1>{esc(r['name'])}</h1>
  {badges_html(r)}
</header>
""")
    photo = photo_for(r)
    if photo and photo.get("photoUrl"):
        credit = (photo.get("credit") or "").strip()
        credit_html = f"{esc(credit)} · " if credit else ""
        alt = r["name"]
        parts.append(f"""
<figure class="plaque-photo">
  <a href="{esc(r['hmdbUrl'])}"><img src="{esc(photo['photoUrl'])}" alt="Photograph of the {esc(alt)} marker" loading="lazy"></a>
  <figcaption>{credit_html}Photo via the <a href="{esc(r['hmdbUrl'])}">Historical Marker Database</a></figcaption>
</figure>""")
    parts.append(f"""
<h2>Where it stands</h2>
<p>{esc(r['address'])}</p>
<p class="coords"><strong>Coordinates:</strong> {lat:.6f}, {lon:.6f} &nbsp;·&nbsp; <a href="https://www.google.com/maps?q={lat},{lon}">View on map &rarr;</a></p>""")
    if not r.get("coordinatesVerified"):
        parts.append("""<div class="flag"><h3>Coordinates approximate</h3>
<p>These coordinates stand approximate, exactly as the contributor published them — the one record in the
catalogue whose position could not be page-verified. Treat the pin as close, not exact.</p></div>""")
    if r.get("ecvChapter"):
        parts.append(f"<p><strong>Erected by:</strong> {esc(r['ecvChapter'])}</p>")
    parts.append('<div id="minimap"></div>')

    # plaque text
    txt = (r.get("short_description") or "").strip()
    paras = [p.replace("\n", " ").strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]
    if not paras and txt:
        paras = [txt.replace("\n", " ")]
    if paras:
        partial = r.get("plaqueTextType") == "partial"
        tag = '<p class="partial-tag">Partial transcription — the catalogue holds only part of the inscription, kept as found</p>' if partial else ""
        body = "".join(f"<p>{esc(p)}</p>" for p in paras)
        parts.append(f"""
<h2>The words on the plaque</h2>
<div class="plaque">{tag}{body}</div>""")

    # catalogue note (possibleDuplicateOf)
    dup = r.get("possibleDuplicateOf")
    if dup:
        if len(dup) < 60 and "." not in dup:
            note = (f"This marker stands at the same spot as the &ldquo;{esc(dup)}&rdquo; point of interest "
                    "already staged in Dave&rsquo;s locations catalogue. The two are flagged to be merged "
                    "when the catalogue takes its permanent home &mdash; not listed twice.")
        else:
            note = esc(dup)
        parts.append(f"""
<div class="note"><h3>A note on this marker</h3><p>{note}</p></div>""")

    src = (f'Catalogued from the <a href="{esc(r["hmdbUrl"])}">Historical Marker Database</a> '
           f'(marker No. {esc(r["hmdbId"])})')
    if r.get("chlNumber") not in (None, "") or r["markerType"] == "California Historical Landmark":
        src += ", cross-checked against the California Office of Historic Preservation&rsquo;s landmark lists."
    else:
        src += "."
    parts.append(f"""
<h2>Source</h2>
<p>{src}</p>

<footer>Reading the Roadside · The Gold Country Markers Catalogue · Compiled Nov 16, 2026<br>
<a href="index.html">{esc(r['county'])} County markers</a> · <a href="../index.html">The catalogue</a></footer>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var m = L.map('minimap').setView([{lat}, {lon}], 13);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 18, attribution: '&copy; OpenStreetMap contributors' }}).addTo(m);
L.circleMarker([{lat}, {lon}], {{ radius: 7, weight: 2, color: '#2b2620', fillColor: '{color}', fillOpacity: 0.9 }}).addTo(m);
</script>
</body>
</html>""")
    return "".join(parts)


def county_page(county, recs, cslug):
    fam_counts = Counter(r["markerType"] for r in recs)
    chips = []
    for mtype in FAMILIES:
        if fam_counts.get(mtype):
            label, color, _ = FAMILIES[mtype]
            chips.append(f'<span><span class="dot" style="background:{color}"></span>{esc(label)} — <strong>{fam_counts[mtype]}</strong></span>')
    btns = ['<button class="fbtn on" data-fam="all">All families</button>']
    for mtype, (label, color, key) in FAMILIES.items():
        if fam_counts.get(mtype):
            btns.append(f'<button class="fbtn" data-fam="{key}">{esc(label)}</button>')
    rows = []
    for r in recs:
        label, color, key = FAMILIES[r["markerType"]]
        chl = f' · <span class="chltag">CHL No. {esc(r["chlNumber"])}</span>' if r.get("chlNumber") not in (None, "") else ""
        text = f'{r["name"]} {r["city"]}'.lower()
        photo = photo_for(r)
        thumb = (f'<img class="thumb" src="{esc(photo["photoUrl"])}" alt="" loading="lazy">'
                 if photo and photo.get("photoUrl") else "")
        rows.append(
            f'<a class="mrow" href="{esc(r["slug"])}.html" data-fam="{key}" data-text="{esc(text)}">'
            f'{thumb}<span class="txt"><span class="nm">{esc(r["name"])}</span>'
            f'<span class="meta" style="display:block"><span class="dot" style="background:{color}"></span>{esc(label)}{chl} · {esc(r["city"])}</span></span></a>')
    return f"""{head(f'{county} County markers — Reading the Roadside',
                     f'All {len(recs)} catalogued historical markers in {county} County, California — search the list and read each plaque.')}
<p class="crumbs"><a href="../index.html">&larr; The catalogue</a></p>
<header>
  <p class="kicker">Gold Country · California</p>
  <h1>{esc(county)} County</h1>
  <p class="sub">{len(recs)} markers catalogued — tap any marker to read the words on its face.</p>
</header>
<div class="fambreak">{''.join(chips)}</div>
<div class="filters">
  <input type="search" id="q" placeholder="Search by name or town…" aria-label="Search markers">
  <div class="fbtns">{''.join(btns)}</div>
  <p class="showing" id="showing">Showing {len(recs)} of {len(recs)} markers · listed A–Z by name</p>
</div>
<div id="list">
{''.join(rows)}
</div>
<footer>Reading the Roadside · The Gold Country Markers Catalogue · Compiled Nov 16, 2026<br>
<a href="../index.html">Back to the catalogue</a></footer>
</div>
<script>
var q = document.getElementById('q'), fam = 'all',
    rows = Array.prototype.slice.call(document.querySelectorAll('.mrow')),
    showing = document.getElementById('showing'), total = rows.length;
function apply() {{
  var needle = q.value.trim().toLowerCase(), n = 0;
  rows.forEach(function(row) {{
    var ok = (fam === 'all' || row.getAttribute('data-fam') === fam) &&
             (!needle || row.getAttribute('data-text').indexOf(needle) !== -1);
    row.classList.toggle('hidden', !ok);
    if (ok) n++;
  }});
  showing.textContent = 'Showing ' + n + ' of ' + total + ' markers · listed A–Z by name';
}}
q.addEventListener('input', apply);
document.querySelectorAll('.fbtn').forEach(function(b) {{
  b.addEventListener('click', function() {{
    document.querySelectorAll('.fbtn').forEach(function(x) {{ x.classList.remove('on'); }});
    b.classList.add('on'); fam = b.getAttribute('data-fam'); apply();
  }});
}});
</script>
</body>
</html>"""


def patch_summary(counties):
    """Surgical additions to index.html. Returns a dict of what was done."""
    p = REPO / "index.html"
    src = p.read_text()
    done = {"ledger_links": 0, "browse_section": False, "map_links": 0}

    # 1. ledger table county names -> links
    for county in COUNTY_ORDER:
        old = f"<td>{county}</td>"
        if old in src:
            src = src.replace(old, f'<td><a href="{county_slug(county)}/">{county}</a></td>', 1)
            done["ledger_links"] += 1

    # 2. Browse the collections section (new §9, before the footer)
    if "Browse the collections" not in src:
        cards = []
        for county in COUNTY_ORDER:
            n = len(counties[county])
            cards.append(
                f'<div class="tile"><a href="{county_slug(county)}/" style="text-decoration:none;color:inherit">'
                f'<span class="n">{n}</span><span class="l">{esc(county)} County &rarr;</span></a></div>')
        section = ('<h2><span class="no">§9</span>Browse the collections</h2>\n'
                   '<p>The whole catalogue, county by county. Open a county to search its markers, '
                   'filter them by family, and read the words on each plaque.</p>\n'
                   f'<div class="tiles">{"".join(cards)}</div>\n\n')
        src = src.replace("<footer>", section + "<footer>", 1)
        done["browse_section"] = True

    # 3. map popup Details links — only if every point matches exactly one record
    m = re.search(r"var PTS = (\[.*?\]);", src, re.S)
    if m and "var SLUGS" not in src:
        pts = json.loads(m.group(1))
        # the summary map's family indices, in its FAMS order
        fam_idx = {"California Historical Landmark": 0, "E Clampus Vitus": 1,
                   "Native Sons/Daughters": 2, "County/Local": 3, "Other organization": 4}
        lookup = {}
        for county, recs in counties.items():
            for r in recs:
                key = (round(r["latitude"], 5), round(r["longitude"], 5), r["name"], fam_idx[r["markerType"]])
                lookup.setdefault(key, []).append(f'{county_slug(county)}/{r["slug"]}')
        slugs, ok = [], True
        for pt in pts:
            hits = lookup.get((round(pt[0], 5), round(pt[1], 5), pt[3], pt[2]), [])
            if len(hits) != 1:
                ok = False
                break
            slugs.append(hits[0])
        if ok:
            src = src.replace(m.group(0), m.group(0) + "\nvar SLUGS = " + json.dumps(slugs) + ";", 1)
            src = src.replace("PTS.forEach(function(p) {", "PTS.forEach(function(p, i) {", 1)
            old_popup = "+ ' County')"
            new_popup = "+ ' County<br><a href=\"' + SLUGS[i] + '.html\">Details &rarr;</a>')"
            assert old_popup in src
            src = src.replace(old_popup, new_popup, 1)
            done["map_links"] = len(slugs)

    # 4. Map filter pills for the §5 map (Dave, Nov 16, 2026): TWO pill groups
    # with AND logic between them — group 1 marker families, group 2 counties.
    # A marker shows only when it matches the selected family AND the selected
    # county; within a group a single pill is selected ("All"/"All families"
    # by default). Markers are held in per-county layer groups and re-dealt on
    # every selection; the map fits to whatever remains visible.
    done["map_pills"] = False
    if "county-pills" not in src:
        pill_css = (
            "\n  /* map filter pills (§5): family group + county group, AND logic */\n"
            "  .county-pills { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:10px 0 4px; }\n"
            "  .county-pills .grouplabel { font-family:Helvetica,Arial,sans-serif; font-size:11.5px;\n"
            "    letter-spacing:.08em; text-transform:uppercase; color:#6d675c; margin-right:2px; }\n"
            "  .cpill, .fpill { font-family:Helvetica,Arial,sans-serif; font-size:13.5px; padding:6px 14px;\n"
            "    border-radius:999px; border:1.5px solid #2b2620; background:transparent; color:#2b2620;\n"
            "    cursor:pointer; }\n"
            "  .cpill:hover, .fpill:hover { background:#e9e2d0; }\n"
            "  .cpill.active, .fpill.active { background:#2b2620; color:#fffdf8; font-weight:bold; }\n")
        if "</style>" in src:
            src = src.replace("</style>", pill_css + "</style>", 1)
        fam_pills = ['<button class="fpill active" data-fam="all" onclick="setFam(\'all\')">All families</button>']
        for idx, label in [(0, "CHL"), (1, "E Clampus Vitus"), (2, "Native Sons/Daughters"),
                           (3, "County / Local"), (4, "Other")]:
            fam_pills.append(
                f'<button class="fpill" data-fam="{idx}" onclick="setFam(\'{idx}\')">{esc(label)}</button>')
        county_pills = ['<button class="cpill active" data-county="All" onclick="setCounty(\'All\')">All</button>']
        for county in sorted(counties):
            county_pills.append(
                f'<button class="cpill" data-county="{esc(county)}" '
                f'onclick="setCounty(\'{esc(county)}\')">{esc(county)}</button>')
        pills_html = (
            '<div class="county-pills" role="group" aria-label="Filter the map by marker family">'
            '<span class="grouplabel">Family</span>' + "".join(fam_pills) + "</div>\n"
            '<div class="county-pills" role="group" aria-label="Filter the map by county">'
            '<span class="grouplabel">County</span>' + "".join(county_pills) + "</div>\n")
        src = src.replace('<div id="map"></div>', pills_html + '<div id="map"></div>', 1)

        old_block = re.search(
            r"var bounds = \[\];.*?map\.fitBounds\(bounds, \{ padding: \[12, 12\] \}\);\n", src, re.S)
        if old_block:
            new_block = (
                "var ALLB = [];\n"
                "var GROUPS = {}, BOUNDS_BY = {}, MARKERS = [];\n"
                "PTS.forEach(function(p, i) {\n"
                "  ALLB.push([p[0], p[1]]);\n"
                "  var c = p[4];\n"
                "  if (!GROUPS[c]) { GROUPS[c] = L.layerGroup(); BOUNDS_BY[c] = []; }\n"
                "  BOUNDS_BY[c].push([p[0], p[1]]);\n"
                "  var mk = L.circleMarker([p[0], p[1]], { radius: 3.5, weight: 0, fillColor: COLORS[p[2]], fillOpacity: 0.85 })\n"
                "    .bindPopup('<strong>' + p[3].replace(/</g,'&lt;') + '</strong><br>' + FAMS[p[2]] + ' \\u00b7 ' + p[4] + ' County<br><a href=\"' + SLUGS[i] + '.html\">Details &rarr;</a>');\n"
                "  MARKERS.push({ m: mk, c: c, f: p[2], ll: [p[0], p[1]] });\n"
                "});\n"
                "var SELF = 'all', SELC = 'All';\n"
                "function applyFilter() {\n"
                "  var vis = [];\n"
                "  Object.keys(GROUPS).forEach(function(c) { GROUPS[c].clearLayers(); if (map.hasLayer(GROUPS[c])) map.removeLayer(GROUPS[c]); });\n"
                "  MARKERS.forEach(function(r) {\n"
                "    if ((SELC === 'All' || r.c === SELC) && (SELF === 'all' || r.f === SELF)) { r.m.addTo(GROUPS[r.c]); vis.push(r.ll); }\n"
                "  });\n"
                "  Object.keys(GROUPS).forEach(function(c) { if (GROUPS[c].getLayers().length) GROUPS[c].addTo(map); });\n"
                "  map.fitBounds(vis.length ? vis : (SELC !== 'All' && BOUNDS_BY[SELC] ? BOUNDS_BY[SELC] : ALLB), { padding: [24, 24] });\n"
                "}\n"
                "function markActive(sel, attr, val) {\n"
                "  var bs = document.querySelectorAll(sel);\n"
                "  for (var j = 0; j < bs.length; j++) bs[j].classList.toggle('active', bs[j].getAttribute(attr) === val);\n"
                "}\n"
                "function setFam(f) { SELF = (f === 'all') ? 'all' : parseInt(f, 10); markActive('.fpill', 'data-fam', f); applyFilter(); }\n"
                "function setCounty(c) { SELC = c; markActive('.cpill', 'data-county', c); applyFilter(); }\n"
                "applyFilter();\n"
                "var _q = new URLSearchParams(location.search);\n"
                "if (_q.get('fam') !== null && ['0','1','2','3','4'].indexOf(_q.get('fam')) >= 0) setFam(_q.get('fam'));\n"
                "if (_q.get('county') && BOUNDS_BY[_q.get('county')]) setCounty(_q.get('county'));\n")
            src = src.replace(old_block.group(0), new_block, 1)
            done["map_pills"] = True


    # 5. Clickable charts, Money Buddy style (Dave, Nov 16, 2026): a county
    # bar (§1 bars, §3 coverage rows) links to that county's list page; a
    # family element (§2 donut segment or legend row) jumps to the §5 map
    # with that family preselected in the pill filter. Whole elements are
    # the targets, with a pointer cursor + hover fade.
    done["chart_links"] = 0
    if "chartlink" not in src:
        chart_css = (
            "\n  /* clickable chart elements */\n"
            "  svg a.chartlink { cursor:pointer; }\n"
            "  svg a.chartlink:hover { opacity:.72; }\n"
            "  ul.legend a.chartlink { color:inherit; text-decoration:none; display:block; cursor:pointer; }\n"
            "  ul.legend li:hover { background:#f3eddc; }\n")
        if "</style>" in src:
            src = src.replace("</style>", chart_css + "</style>", 1)

        # §1 + §3 county rows: label + bar(s) + value, wrapped in one anchor
        row_re = re.compile(
            r'(<text x="102" y="[\d.]+" text-anchor="end" class="clabel">([A-Za-z ]+)</text>'
            r'(?:<rect[^/]*/>)+'
            r'<text x="[\d.]+" y="[\d.]+" class="cvalue">[^<]*</text>)')
        def _wrap_row(m):
            county = m.group(2)
            if county not in counties:
                return m.group(0)
            done["chart_links"] += 1
            return (f'<a class="chartlink" href="{county_slug(county)}/">'
                    f'<title>{esc(county)} County markers</title>{m.group(1)}</a>')
        src = row_re.sub(_wrap_row, src)

        # §2 donut segments: family identified by its stroke colour
        fam_by_color = {"#b8860b": 0, "#9a3b26": 1, "#2e5e4e": 2,
                        "#31597f": 3, "#8a8378": 4}
        seg_re = re.compile(r'<circle cx="130\.0" cy="130\.0" r="104\.0"[^>]*stroke="(#[0-9a-f]{6})"[^>]*/>')
        def _wrap_seg(m):
            idx = fam_by_color.get(m.group(1))
            if idx is None:
                return m.group(0)
            done["chart_links"] += 1
            return (f'<a class="chartlink" href="#map" onclick="setFam(\'{idx}\')">'
                    f'<title>Show this family on the map</title>{m.group(0)}</a>')
        src = seg_re.sub(_wrap_seg, src)

        # §2 legend rows: family identified by the dot's background colour
        leg_re = re.compile(
            r'<li>(<span class="dot" style="background:(#[0-9a-f]{6})"></span>.*?)</li>')
        def _wrap_leg(m):
            idx = fam_by_color.get(m.group(2))
            if idx is None:
                return m.group(0)
            done["chart_links"] += 1
            return (f'<li><a class="chartlink" href="#map" onclick="setFam(\'{idx}\')">'
                    f'{m.group(1)}</a></li>')
        src = leg_re.sub(_wrap_leg, src)
    # 6. Analytics Buddy visitor beacon on the front page (fleet counter;
    # added to the generator Nov 16, 2026 so rebuilds keep it — Analytics
    # Buddy's hand-insert is superseded by this guard: never duplicate it).
    done["beacon"] = "visitor-counter" in src
    if not done["beacon"] and "</body>" in src:
        src = src.replace(
            "</body>",
            '<script async src="https://visitor-counter.dave-5d7.workers.dev/beacon.js" '
            'data-site="gold-country-markers"></script>\n</body>', 1)
        done["beacon"] = True

    p.write_text(src)
    return done


def main():
    counties = load_records()
    total = 0
    for county in COUNTY_ORDER:
        recs = counties[county]
        cslug = county_slug(county)
        cdir = REPO / cslug
        cdir.mkdir(exist_ok=True)
        (cdir / "index.html").write_text(county_page(county, recs, cslug))
        for r in recs:
            (cdir / f'{r["slug"]}.html').write_text(detail_page(r, cslug))
            total += 1
        print(f"{county}: {len(recs)} detail pages + list page")
    print(f"detail pages total: {total}")
    done = patch_summary(counties)
    print("summary patch:", done)


if __name__ == "__main__":
    sys.exit(main())
