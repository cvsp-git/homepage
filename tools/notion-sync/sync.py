"""Pull News / Gallery / LAB Life cards and member pages from the lab's public Notion
into the Jekyll site.

  python3 tools/notion-sync/sync.py            # only pages edited since the last run
  python3 tools/notion-sync/sync.py --full     # re-render every page
  python3 tools/notion-sync/sync.py --dump D   # offline: read a dump made by dump.py (no media)

Notion stays the place to edit. Files this script writes (_board/, _members/,
images/gallery/board/, images/members/pages/) are overwritten on every sync.
"""
import argparse, datetime, json, os, re, shutil, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notion
from render import Renderer, plain

BOARD_DB = "c6158afa-34c1-4fbf-bf5e-3af211773d19"    # Website CMS / LABDB_images
FAMILY_DB = "07237418-f973-4512-b2e6-d9339488a79d"   # MEMBERS / LABDB_family
CONF = {"Conference", "Journals", "Forum", "Workshop/Seminar"}   # Gallery vs LAB Life split used on the old site

ap = argparse.ArgumentParser()
ap.add_argument("--full", action="store_true")
ap.add_argument("--dump")
ap.add_argument("--root", default=".")
ap.add_argument("--only", help="comma separated notion ids to re-render")
args = ap.parse_args()
ROOT = os.path.abspath(args.root)
STATE = os.path.join(ROOT, "tools/notion-sync/state.json")
state = json.load(open(STATE)) if os.path.exists(STATE) else {"board": {}, "members": {}}
N = lambda s: unicodedata.normalize("NFC", s or "").strip()
log = lambda *a: print(*a, flush=True)


# ---------------- data access (live or dump) ----------------
def load_db(page, dumpname):
    if args.dump:
        d = json.load(open(os.path.join(args.dump, dumpname + ".json")))
        return d["rows"], d["recordMap"]
    rm = notion.load_page(page)
    b = rm["block"][page]
    return notion.query(b["collection_id"], b["view_ids"][0], b["space_id"], rm)


def load_page(pid, dumpname):
    if args.dump and dumpname:
        p = os.path.join(args.dump, dumpname, pid + ".json")
        return json.load(open(p)) if os.path.exists(p) else None
    rm = notion.load_page(pid)
    # synced blocks: load the originals and their children
    for _ in range(3):
        want = []
        for v in list(rm.get("block", {}).values()):
            ptr = ((v.get("format") or {}).get("transclusion_reference_pointer") or {}).get("id")
            if ptr: want.append(ptr)
            want += [c for c in (v.get("content") or []) if v.get("type", "").startswith("transclusion")]
        want = [w for w in want if w not in rm.get("block", {})]
        if not want: break
        notion.fill_missing(rm, want)
        kids = [c for w in want for c in (rm["block"].get(w, {}).get("content") or [])]
        notion.fill_missing(rm, kids)
    return rm


def prop(rm, coll_id):
    schema = rm["collection"][coll_id]["schema"]
    names = {v["name"]: k for k, v in schema.items()}
    def get(block, name):
        return (block.get("properties") or {}).get(names.get(name, "\0"))
    return get


def date_of(v):
    for seg in v or []:
        for a in (seg[1] if len(seg) > 1 else []):
            if a[0] == "d": return a[1].get("start_date")
    return None


def yq(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_body(path):
    if not os.path.exists(path): return None
    s = open(path, encoding="utf-8").read()
    m = re.match(r"---\n.*?\n---\n", s, re.S)
    return s[m.end():] if m else s


# ---------------- media ----------------
class Media:
    def __init__(self, rm, folder, web):
        self.rm, self.folder, self.web, self.n = rm, folder, web, 0
        self.paths = []
        self.failed = 0
        if os.path.isdir(folder): shutil.rmtree(folder)

    def __call__(self, kind, src, block, caption):
        if not src: return None
        if args.dump:
            self.n += 1; p = "%s/%02d.jpg" % (self.web, self.n); self.paths.append(p); return p
        from media import fetch
        os.makedirs(self.folder, exist_ok=True)
        self.n += 1
        out = fetch(src, block["id"], block.get("space_id"), os.path.join(self.folder, "%02d" % self.n))
        if out:
            p = "%s/%s" % (self.web, os.path.basename(out)); self.paths.append(p); return p
        self.failed += 1
        if src.startswith("http") and not __import__("media").notion_hosted(src):
            self.paths.append(src); return src          # keep external image as a remote link
        return None


# ---------------- board ----------------
def sync_board():
    rows, rm = load_db(BOARD_DB, "board")
    coll = rm["block"][BOARD_DB]["collection_id"]
    get = prop(rm, coll)
    opts = {o["value"] for o in rm["collection"][coll]["schema"]["oS@C"].get("options", [])}
    cards = []
    for i in rows:
        b = rm["block"].get(i)
        if not b or not b.get("alive", True): continue
        ptype = plain(get(b, "post_type"))
        badges = [x.strip() for x in plain(get(b, "badges")).split(",") if x.strip() in opts]
        kind = "news" if ptype == "news" else ("gallery" if set(badges) & CONF else "life") if ptype == "gallary" else None
        d = date_of(get(b, "date"))
        if not kind or not d or plain(get(b, "is_hidden")) == "Yes": continue
        cards.append(dict(id=i, kind=kind, date=d, title=N(plain(get(b, "post_title"))), badges=badges,
                          edited=b.get("last_edited_time"), block=b, cover=plain(get(b, "image")) and
                          [a[1] for seg in get(b, "image") for a in (seg[1] if len(seg) > 1 else []) if a[0] == "a"]))
    # order within each list = the old site's view sort
    for kind in ("news", "gallery", "life"):
        ks = [c for c in cards if c["kind"] == kind]
        ks.sort(key=lambda c: c["title"]) if kind == "news" else None
        ks.sort(key=lambda c: c["date"], reverse=True)
        for n, c in enumerate(ks): c["order"] = n
    # stable slugs
    st = state.setdefault("board", {})
    taken = {v["slug"] for k, v in st.items() if k in {c["id"] for c in cards}}
    for c in sorted(cards, key=lambda c: (c["kind"], c["date"], c["order"])):
        if c["id"] in st: c["slug"] = st[c["id"]]["slug"]; continue
        n = 1
        while "%s-%s-%d" % (c["kind"], c["date"], n) in taken: n += 1
        c["slug"] = "%s-%s-%d" % (c["kind"], c["date"], n); taken.add(c["slug"])
    id2url = {c["id"]: "/board/%s/" % c["slug"] for c in cards}
    id2url.update(MEMBER_URLS)
    only = set((args.only or "").split(","))
    out_dir = os.path.join(ROOT, "_board"); img_dir = os.path.join(ROOT, "images/gallery/board")
    os.makedirs(out_dir, exist_ok=True); os.makedirs(img_dir, exist_ok=True)
    changed = 0
    for c in cards:
        slug = c["slug"]; md = os.path.join(out_dir, slug + ".md")
        prev = st.get(c["id"], {})
        body = read_body(md)
        fresh = args.full or c["id"] in only or body is None or prev.get("edited") != c["edited"] or prev.get("slug") != slug
        cover = prev.get("cover", "")
        show_cover = prev.get("show_cover", True)
        if fresh:
            prm = load_page(c["id"], "board")
            if prm is None:
                log("  skip (not in dump)", slug); continue
            if c["id"] not in prm.get("block", {}): prm.setdefault("block", {})[c["id"]] = c["block"]
            media = Media(prm, os.path.join(img_dir, slug), "/images/gallery/board/" + slug)
            r = Renderer(prm, media, lambda pid: id2url.get(pid))
            body = r.page(c["id"])
            body = (body + "\n") if body else ""
            show_cover = not media.paths
            # cover
            for f in os.listdir(img_dir):
                if f.startswith(slug + ".") and os.path.isfile(os.path.join(img_dir, f)): os.remove(os.path.join(img_dir, f))
            cover = ""
            if c["cover"] and not args.dump:
                from media import fetch
                out = fetch(c["cover"][0], c["id"], c["block"].get("space_id"), os.path.join(img_dir, slug), first_frame=True)
                if out: cover = "board/" + os.path.basename(out)
                elif c["cover"][0].startswith("http"): cover = c["cover"][0]
            elif c["cover"] and args.dump:
                cover = "board/%s.jpg" % slug
            if not cover:
                first = [p for p in media.paths if not p.endswith(".mp4")]
                if first: cover = first[0].replace("/images/gallery/", "", 1) if first[0].startswith("/images/") else first[0]
            changed += 1
            log("  rendered", slug, "-", c["title"][:50])
        tag = c["badges"][0] if c["badges"] else ""
        fm = ["---", "title: " + yq(c["title"]), "date: " + c["date"], "kind: " + c["kind"], "tag: " + yq(tag),
              "badges: [" + ", ".join(yq(x) for x in c["badges"]) + "]", "image: " + yq(cover),
              "show_cover: " + ("true" if show_cover else "false"), "order: %d" % c["order"],
              "notion_id: " + c["id"], "---", ""]
        open(md, "w", encoding="utf-8").write("\n".join(fm) + body)
        retry = fresh and (media.failed or (c["cover"] and not cover))
        st[c["id"]] = {"slug": slug, "edited": None if retry else c["edited"], "cover": cover, "show_cover": show_cover}
    # remove cards that were hidden or deleted in Notion
    keep = {c["slug"] for c in cards}
    for k in [k for k in st if k not in {c["id"] for c in cards}]: del st[k]
    for f in os.listdir(out_dir):
        if f.endswith(".md") and f[:-3] not in keep:
            os.remove(os.path.join(out_dir, f)); log("  removed", f)
            d = os.path.join(img_dir, f[:-3])
            if os.path.isdir(d): shutil.rmtree(d)
            for g in os.listdir(img_dir):
                if g.startswith(f[:-3] + "."): os.remove(os.path.join(img_dir, g))
    log("board: %d cards, %d re-rendered" % (len(cards), changed))


# ---------------- members ----------------
MEMBER_URLS = {}


def sync_members():
    rows, rm = load_db(FAMILY_DB, "family")
    coll = rm["block"][FAMILY_DB]["collection_id"]
    get = prop(rm, coll)
    st = state.setdefault("members", {})
    out_dir = os.path.join(ROOT, "_members"); img_dir = os.path.join(ROOT, "images/members/pages")
    os.makedirs(out_dir, exist_ok=True)
    people = []
    for i in rows:
        b = rm["block"].get(i)
        if not b or not b.get("alive", True): continue
        if plain(get(b, "id_hidden")) == "Yes": continue
        people.append(dict(id=i, name=N(plain(get(b, "name"))), status=plain(get(b, "status")),
                           edited=b.get("last_edited_time"), block=b))
    changed = 0
    for p in people:
        prev = st.get(p["id"], {})
        slug = prev.get("slug")
        md = os.path.join(out_dir, (slug or "_") + ".md")
        fresh = args.full or not slug or prev.get("edited") != p["edited"] or not os.path.exists(md) or p["id"] in (args.only or "")
        if fresh:
            prm = load_page(p["id"], "family")
            if prm is None: continue
            if p["id"] not in prm.get("block", {}): prm.setdefault("block", {})[p["id"]] = p["block"]
            m = None
            for c in prm["block"][p["id"]].get("content") or []:   # only this page's own blocks
                v = prm["block"].get(c, {})
                if v.get("type") == "code":
                    m = m or re.search(r'cleanUrl:\s*"/members/([\w.-]+)"', plain((v.get("properties") or {}).get("title")))
            slug = m.group(1) if m else re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-")
            MEMBER_URLS[p["id"]] = "/members/%s/" % slug
            p.update(slug=slug, rm=prm)
        else:
            MEMBER_URLS[p["id"]] = "/members/%s/" % slug
            p["slug"] = slug
    # two Notion pages can carry the same cleanUrl (a copied template); the one whose name matches keeps it
    squash = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
    by = {}
    for p in people: by.setdefault(p["slug"], []).append(p)
    for slug, ps in by.items():
        if len(ps) < 2: continue
        ps.sort(key=lambda p: not squash(p["name"]).startswith(squash(slug)))
        for p in ps[1:]:
            p["slug"] = re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-")
            MEMBER_URLS[p["id"]] = "/members/%s/" % p["slug"]
            log("  duplicate cleanUrl /members/%s: %s -> /members/%s/" % (slug, p["name"], p["slug"]))
    for p in people:
        md = os.path.join(out_dir, p["slug"] + ".md")
        if "rm" in p:
            media = Media(p["rm"], os.path.join(img_dir, p["slug"]), "/images/members/pages/" + p["slug"])
            body = Renderer(p["rm"], media, lambda pid: MEMBER_URLS.get(pid) or BOARD_URLS.get(pid)).page(p["id"])
            changed += 1; log("  rendered member", p["slug"])
            if media.failed: p["edited"] = None   # try the missing media again next run
        else:
            body = (read_body(md) or "").strip()
        fm = ["---", "title: " + yq(p["name"]), "status: " + yq(p["status"]), "notion_id: " + p["id"], "---", ""]
        open(md, "w", encoding="utf-8").write("\n".join(fm) + (body + "\n" if body else ""))
        st[p["id"]] = {"slug": p["slug"], "edited": p["edited"]}
    keep = {p["slug"] for p in people}
    for k in [k for k in st if k not in {p["id"] for p in people}]: del st[k]
    for f in os.listdir(out_dir):
        if f.endswith(".md") and f[:-3] not in keep:
            os.remove(os.path.join(out_dir, f)); log("  removed member", f)
            d = os.path.join(img_dir, f[:-3])
            if os.path.isdir(d): shutil.rmtree(d)
    log("members: %d pages, %d re-rendered" % (len(people), changed))


# ---------------- publications ----------------
PUB_PAGES = {"international": "d9c4ac58-eaed-42a2-935d-e1c83397e1dd", "domestic": "00312390-10c3-4807-a64a-f3cef4306fdf"}


def load_full(pid, dumpname):
    if args.dump:
        p = os.path.join(args.dump, dumpname + ".json")
        return json.load(open(p))["recordMap"] if os.path.exists(p) else None
    return load_page(pid, None)


def write_json(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != text:
        open(path, "w", encoding="utf-8").write(text); log("  updated", os.path.relpath(path, ROOT))


def sync_publications():
    import pubs
    figs = json.load(open(os.path.join(ROOT, "tools/notion-sync/pub_figures.json")))
    norm = lambda t: re.sub(r"[^0-9a-z가-힣]", "", t.lower())
    for name, pid in PUB_PAGES.items():
        rm = load_full(pid, {"international": "intl", "domestic": "domestic"}[name])
        if rm is None: continue
        recs = pubs.parse(rm, pid, name)
        if len(recs) < 5:
            log("  publications/%s: only %d entries parsed, keeping the old list" % (name, len(recs))); continue
        figdir = os.path.join(ROOT, "images/publications", name)
        have = set(os.listdir(figdir)) if os.path.isdir(figdir) else set()
        for r in recs:
            f = figs.get(norm(r["title"]))
            if f and f in have: r["figure"] = f
        write_json(os.path.join(ROOT, "_data/publications_%s.json" % name), recs)
        log("publications/%s: %d" % (name, len(recs)))


BOARD_URLS = {k: "/board/%s/" % v["slug"] for k, v in state.get("board", {}).items()}
sync_publications()
sync_members()
sync_board()
json.dump(state, open(STATE, "w"), ensure_ascii=False, indent=1, sort_keys=True)
