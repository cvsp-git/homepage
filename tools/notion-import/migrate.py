"""Notion LABDB export -> Jekyll _board (front matter + body + per-card media).
usage: migrate2.py EX OUT IMG_OUT FULL_MD_ROOT OLD_IMG_ROOTS..."""
import csv, os, re, sys, datetime, collections, html, urllib.parse, unicodedata, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assets import convert
from mdindex import load, norm
EX, OUT, IMG_OUT, FULL = sys.argv[1:5]; IMG_ROOTS = sys.argv[5:]
N = lambda t: unicodedata.normalize('NFC', t)
report = collections.defaultdict(list)

# ---------- old cover folders (fallback for cards without md) ----------
folders = {}
for r0 in IMG_ROOTS:
    for name in os.listdir(r0):
        p = os.path.join(r0, name)
        if os.path.isdir(p):
            imgs = sorted(f for f in os.listdir(p) if not f.startswith('.'))
            if imgs: folders[N(name)] = os.path.join(p, imgs[0])

# ---------- all extracted files, for resolving refs whose folder landed in another zip ----------
bytail = collections.defaultdict(list); bylow = collections.defaultdict(list); byname = collections.defaultdict(list); allfiles = []
for dp, _, fs in os.walk(FULL):
    for f in fs:
        p = os.path.join(dp, f); t = '/'.join(N(p).split('/')[-2:]); allfiles.append((N(p), p))
        bytail[t].append(p); bylow[t.lower()].append(p); byname[N(f)].append(p)
GENERIC = re.compile(r'^image( \d+)?\.png$')
def resolve(mddir, ref):
    ref = N(urllib.parse.unquote(ref))
    p = os.path.join(mddir, ref)
    if os.path.exists(p): return p
    t = '/'.join(ref.split('/')[-2:]); fn = ref.split('/')[-1]
    if bytail.get(t): return bytail[t][0]
    if GENERIC.match(fn): return None
    if len(bylow.get(t.lower(), [])) == 1: return bylow[t.lower()][0]   # mac merged "Birthday party!" into "Birthday Party!"
    folder = ref.split('/')[-2] if '/' in ref else ''
    c = [q for np_, q in allfiles if np_.endswith('/' + fn) and folder and np_.split('/')[-2].startswith(folder)]
    if len(c) == 1: return c[0]                                          # "ECCV 2026 in Sweden 복사본/"
    if len(byname.get(fn, [])) == 1: return byname[fn][0]                # stray file at zip top level
    return None

mds = load(FULL)
bykey = {}
for m in mds:
    bykey[(norm(m['props'].get('date')), norm(m['props'].get('display_string')))] = m
byid = {m['id']: m for m in mds if m['id']}

os.makedirs(OUT, exist_ok=True); os.makedirs(IMG_OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith('.md'): os.remove(os.path.join(OUT, f))

allrows = list(csv.DictReader(open(EX + '/Website CMS/LABDB_images c6158afa34c14fbfbf5e3af211773d19_all.csv', encoding='utf-8-sig')))
D = EX + '/Computer Vision & Signal Processing Lab (CVSP)/'
views = {'news': 'Untitled b04173178f08424587e900da90a3b3c8.csv',
         'gallery': 'Untitled dcffee436e8941b28b64d9a3bb2c2643.csv',
         'life': 'Untitled 363abcc90e34808cb2a4f4c4e55fe820.csv'}
pool = collections.defaultdict(list)
for r in allrows: pool[(norm(r['post_title']), norm(r['display_string']))].append(r)

def parse_date(s):
    s = (s or '').split('→')[0].strip()
    for fmt in ('%B %d, %Y', '%Y/%m/%d', '%Y-%m-%d'):
        try: return datetime.datetime.strptime(s, fmt).date()
        except ValueError: pass
def yq(s): return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

# old suffix-based folder assignment (only used when a card has no md)
SUF = re.compile(r' ([0-9a-f]{4}-[0-9a-f]{4})$')
def split(name):
    m = SUF.search(name); return (name[:m.start()], m.group(1)) if m else (name, None)
groups = collections.defaultdict(list)
for r in allrows:
    if r['image'] and r['image'].count('/') >= 2:
        f = N(urllib.parse.unquote(r['image']).split('/')[2]); groups[split(f)[0]].append((r, split(f)[1]))
user = collections.defaultdict(dict)
for k in folders: b, sf = split(k); user[b][sf] = k
assign = {}
for b, rs in groups.items():
    U = dict(user.get(b, {})); used = set(); known = {sf for _, sf in rs if sf}
    for r, sf in rs:
        if sf and sf in U: assign[id(r)] = U[sf]; used.add(sf)
    for r, sf in rs:
        if sf and id(r) not in assign and None in U and None not in used: assign[id(r)] = U[None]; used.add(None)
    for r, sf in rs:
        if sf is None:
            extra = [x for x in U if x and x not in known and x not in used]
            if len(extra) == 1: assign[id(r)] = U[extra[0]]; used.add(extra[0])
            elif None in U and None not in used: assign[id(r)] = U[None]; used.add(None)

# ---------- pass 1: decide slugs ----------
cards = []; count = collections.Counter()
for kind, fn in views.items():
    for order, v in enumerate(csv.DictReader(open(D + fn, encoding='utf-8-sig'))):
        key = (norm(v['post_title']), norm(v['display_string']))
        src = pool[key].pop(0) if pool[key] else None
        if src and src['is_hidden'] == 'Yes': continue
        lines = [l.strip() for l in v['display_string'].split('\n') if l.strip()]
        tag = lines[0].lstrip('#') if lines and lines[0].startswith('#') else ''
        mm = re.match(r'(\d+)월,\s*(\d{4})', lines[1] if len(lines) > 1 else '')
        d = parse_date(src['date']) if src else None
        if d is None and mm: d = datetime.date(int(mm.group(2)), int(mm.group(1)), 1)
        if d is None: print('NO DATE', kind, v['post_title']); continue
        badges = [b.strip() for b in (src['badges'] if src else tag).split(',') if b.strip()]
        count[(kind, d.isoformat())] += 1
        slug = '%s-%s-%d' % (kind, d.isoformat(), count[(kind, d.isoformat())])
        md = bykey.get((norm(src['date']) if src else '', norm(v['display_string'])))
        if md is None: report['no md'].append(slug + ' ' + norm(v['post_title']))
        cards.append(dict(kind=kind, order=order, slug=slug, title=norm(v['post_title']), d=d, tag=tag or (badges[0] if badges else ''),
                          badges=badges, src=src, md=md, dstr=lines[1] if len(lines) > 1 else ''))
id2url = {c['md']['id']: '/board/%s/' % c['slug'] for c in cards if c['md'] and c['md']['id']}

# ---------- body conversion ----------
IMG_RE = re.compile(r'^!\[(.*?)\]\((\S+?)\)\s*$')
VID_RE = re.compile(r'^\[([^\]]*\.(?:mp4|mov))\]\((\S+?)\)\s*$', re.I)
def fix_link(url, slug):
    u = url.strip()
    m = re.search(r'([0-9a-f]{32})(?:\.md)?(?:\?.*)?$', urllib.parse.unquote(u).split('#')[0])
    if m and (u.endswith('.md') or 'notion' in u or not u.startswith('http')):
        if m.group(1) in id2url: return id2url[m.group(1)]
        report['dead notion link'].append(slug + ' ' + u); return None
    if re.match(r'https?://(www\.)?pnu-cvsp\.com/members', u): return '/members.html'
    if re.match(r'https?://(www\.)?pnu-cvsp\.com/?$', u): return '/'
    return u
def links(l, slug):
    def rl(mo):
        u = fix_link(mo.group(2), slug)
        return mo.group(1) if u is None else '[%s](%s)' % (mo.group(1), u)
    return re.sub(r'(?<!!)\[([^\]]*)\]\(([^)\s]+(?:\([^)]*\)[^)\s]*)*)\)', rl, l)
def is_fileish(s): return bool(re.search(r'\.(png|jpe?g|gif|heic|svg|webp)$', s.strip(), re.I)) or s.strip() == ''

def convert_body(md, slug):
    lines = md['body'].split('\n'); out = []; n = 0; media = []
    mdir = md['dir']; dstdir = os.path.join(IMG_OUT, slug)
    i = 0; slide = None
    def media_html(ref, alt, cls=''):
        nonlocal n
        p = resolve(mdir, ref)
        if not p: report['missing image'].append('%s  %s' % (slug, N(urllib.parse.unquote(ref)))); return None
        os.makedirs(dstdir, exist_ok=True); n += 1
        kind, dst = convert(p, os.path.join(dstdir, '%02d' % n))
        web = '/images/gallery/board/%s/%s' % (slug, os.path.basename(dst)); media.append(web)
        if kind == 'video':
            return '<video src="%s" autoplay loop muted playsinline controls preload="metadata"></video>' % web
        return '<img src="%s" alt="%s" loading="lazy">' % (web, html.escape(alt if not is_fileish(alt) else '', quote=True))
    while i < len(lines):
        l = lines[i]; s = l.strip()
        # oopy / notion config code blocks
        if s.startswith('```'):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith('```'): j += 1
            block = '\n'.join(lines[i + 1:j])
            if 'cleanUrl' in block or '<head>' in block or '<style' in block or 'oopy' in block or 'speed:' in block:
                i = j + 1; continue
            out.extend(lines[i:j + 1]); i = j + 1; continue
        if s == '<aside>':
            j = i + 1
            while j < len(lines) and lines[j].strip() != '</aside>': j += 1
            inner = lines[i + 1:j]
            if any('oopy:slide' in x for x in inner):
                imgs = [IMG_RE.match(x.strip()) for x in inner]
                tags = [media_html(m.group(2), m.group(1)) for m in imgs if m]
                tags = [t for t in tags if t]
                if tags:
                    out += ['', '<div class="board-slide" data-slide><div class="board-slide-track">' +
                            ''.join('<figure>%s</figure>' % t for t in tags) + '</div></div>', '']
            else:
                body = [x for x in inner if x.strip()]
                icon = ''
                if body and re.match(r'^\W\s', body[0]) and not body[0].startswith(('-', '*', '>')):
                    icon, body[0] = body[0][0], body[0][1:].lstrip()
                out += ['', '<div class="callout" markdown="1">', '']
                out += ['<span class="callout-icon">%s</span>' % icon if icon else ''] if False else []
                out += [links(x, slug) for x in ([(icon + ' ' if icon else '') + body[0]] + body[1:])] if body else []
                out += ['', '</div>', '']
            i = j + 1; continue
        if s.startswith('<img ') and 'notion.com/icons' in s:
            l = re.sub(r'<img [^>]*/>\s*', '', l); s = l.strip()
        if s in ('[](https://app.notion.com)', '[](https://www.notion.so)'): i += 1; continue
        m = IMG_RE.match(s)
        if m:
            alt, ref = m.group(1), m.group(2)
            if ref.startswith('http'):
                report['external image'].append(slug + ' ' + ref); media.append(ref)
                out += ['', '<figure class="board-fig"><img src="%s" alt="" loading="lazy"></figure>' % html.escape(ref, quote=True), '']
                i += 1; continue
            tag = media_html(ref, alt)
            # Notion repeats a real caption as the next paragraph
            cap = ''
            k = i + 1
            while k < len(lines) and not lines[k].strip(): k += 1
            if not is_fileish(alt) and k < len(lines) and norm(lines[k]) == norm(alt):
                cap = alt; i = k
            if tag:
                out += ['', '<figure class="board-fig">%s%s</figure>' % (tag, '<figcaption>%s</figcaption>' % html.escape(cap) if cap else ''), '']
            i += 1; continue
        m = VID_RE.match(s)
        if m:
            tag = media_html(m.group(2), '')
            if tag: out += ['', '<figure class="board-fig">%s</figure>' % tag, '']
            i += 1; continue
        out.append(links(l, slug)); i += 1
    # Notion soft line breaks -> hard breaks inside plain paragraphs
    res = []
    for k, l in enumerate(out):
        nxt = out[k + 1] if k + 1 < len(out) else ''
        plain = lambda x: x.strip() and not re.match(r'^\s*(#|[-*+] |\d+\. |<|\||```|> ?$)', x)
        if plain(l) and plain(nxt) and not l.endswith('  '): l = l.rstrip() + '  '
        res.append(l)
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(res)).strip()
    if '{{' in text or '{%' in text: text = '{% raw %}\n' + text + '\n{% endraw %}'
    return text, media

# ---------- pass 2: write ----------
made_dirs = set(); made_covers = set()
for c in cards:
    slug, md, src = c['slug'], c['md'], c['src']
    body, media = convert_body(md, slug) if md else ('', [])
    if media: made_dirs.add(slug)
    cover = ''
    cpath = None
    if md and md['props'].get('image'):
        cpath = resolve(md['dir'], md['props']['image'])
        if not cpath: report['cover not in export'].append(slug + ' ' + md['props']['image'])
    if not cpath and src and id(src) in assign: cpath = folders[assign[id(src)]]
    if cpath:
        _, dst = convert(cpath, os.path.join(IMG_OUT, slug))
        if dst.endswith('.mp4'):  # animated cover too large: use first frame
            os.remove(dst); from PIL import Image; im = Image.open(cpath); im.seek(0)
            from assets import _save_jpg; dst = os.path.join(IMG_OUT, slug + '.jpg'); _save_jpg(im, dst)
        cover = 'board/' + os.path.basename(dst)
    elif media:
        first = [x for x in media if not x.endswith('.mp4')]
        if first: cover = first[0].replace('/images/gallery/', '', 1) if first[0].startswith('/images/gallery/') else first[0]
    if cover.startswith('board/' + slug + '.'): made_covers.add(os.path.basename(cover))
    if not cover: report['no cover'].append(slug + ' ' + c['title'])
    fm = ['---', 'title: ' + yq(c['title']), 'date: ' + c['d'].isoformat(), 'kind: ' + c['kind'],
          'tag: ' + yq(c['tag']), 'badges: [' + ', '.join(yq(b) for b in c['badges']) + ']',
          'image: ' + yq(cover), 'show_cover: %s' % ('false' if media else 'true'), 'order: %d' % c['order'], '---', '']
    open(os.path.join(OUT, slug + '.md'), 'w').write('\n'.join(fm) + (body + '\n' if body else ''))

for f in os.listdir(IMG_OUT):
    p = os.path.join(IMG_OUT, f)
    if os.path.isfile(p) and f not in made_covers: os.remove(p); report['removed stale'].append(f)
    if os.path.isdir(p) and f not in made_dirs:
        for g in os.listdir(p): os.remove(os.path.join(p, g))
        os.rmdir(p)
print(collections.Counter(c['kind'] for c in cards))
for k, v in report.items():
    print('==', k, len(v))
    for x in v[:60]: print('  ', x)
