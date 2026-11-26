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
from render import Renderer, HtmlRenderer, plain

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
    # blocks inside closed toggles (and other deep children) are not always in the first load: fetch them too
    for _ in range(6):
        want = [c for v in list(rm.get("block", {}).values()) for c in (v.get("content") or [])
                if c not in rm["block"] and v.get("type") not in ("page", "collection_view_page", "collection_view")]
        if not want: break
        notion.fill_missing(rm, want)
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
        from media import fetch, fetch_file
        os.makedirs(self.folder, exist_ok=True)
        self.n += 1
        if kind == "file":
            out = fetch_file(src, block["id"], block.get("space_id"), os.path.join(self.folder, "%02d" % self.n))
            return "%s/%s" % (self.web, os.path.basename(out)) if out else None
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
        if f.endswith(".md") and f[:-3] not in keep and not f.startswith("seminar-"):
            os.remove(os.path.join(out_dir, f)); log("  removed", f)
            d = os.path.join(img_dir, f[:-3])
            if os.path.isdir(d): shutil.rmtree(d)
            for g in os.listdir(img_dir):
                if g.startswith(f[:-3] + "."): os.remove(os.path.join(img_dir, g))
    log("board: %d cards, %d re-rendered" % (len(cards), changed))


# ---------------- members ----------------
MEMBER_URLS = {}


# member pages are written as HTML (HtmlRenderer); bump this to re-render every member page once
MEMBER_FMT = 4


def sync_members():
    rows, rm = load_db(FAMILY_DB, "family")
    coll = rm["block"][FAMILY_DB]["collection_id"]
    rows_b = [rm["block"][i] for i in rows if i in rm["block"]]
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
        md = os.path.join(out_dir, (slug or "_") + ".html")
        fresh = args.full or state.get("members_fmt") != MEMBER_FMT or not slug or prev.get("edited") != p["edited"] or not os.path.exists(md) or p["id"] in (args.only or "")
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
        md = os.path.join(out_dir, p["slug"] + ".html")
        if "rm" in p:
            media = Media(p["rm"], os.path.join(img_dir, p["slug"]), "/images/members/pages/" + p["slug"])
            body = HtmlRenderer(p["rm"], media, lambda pid: MEMBER_URLS.get(pid) or BOARD_URLS.get(pid)).page(p["id"])
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
        stem, ext = os.path.splitext(f)
        if ext == ".md" or (ext == ".html" and stem not in keep):   # .md = the old Markdown format
            os.remove(os.path.join(out_dir, f)); log("  removed member file", f)
            d = os.path.join(img_dir, stem)
            if stem not in keep and os.path.isdir(d): shutil.rmtree(d)
    state["members_fmt"] = MEMBER_FMT
    log("members: %d pages, %d re-rendered" % (len(people), changed))
    sync_member_list(rows_b, rm, get)


GROUPS = [("Professor", "Professor"), ("Postdoctoral researcher", "Postdoctoral Researcher"), ("Ph.D. Course", "Ph.D. Course"),
          ("M.S. Course", "M.S. Course"), ("M.S. Researcher", "M.S. Researcher"), ("Integrated B.S./M.S. Course", "Integrated B.S.–M.S. Course"),
          ("Research Intern", "Research Intern"), ("Alumni", "Alumni")]
HIDDEN_STATUS = {"", "n/a", "alumni_old"}   # statuses that are not shown on the Members page


def sync_member_list(rows, rm, get):
    """Members page: who is in which group comes from Notion; extra details from _data/member_extras.yml."""
    import yaml
    extras_path = os.path.join(ROOT, "_data/member_extras.yml")
    extras, order = {}, {}
    if os.path.exists(extras_path):
        for g in yaml.safe_load(open(extras_path, encoding="utf-8")) or []:
            for k, p in enumerate(g.get("people") or []):
                extras[N(p["name"]).lower()] = p; order[N(p["name"]).lower()] = k
    photo_dir = os.path.join(ROOT, "images/members/notion"); os.makedirs(photo_dir, exist_ok=True)
    keep_photos = set()
    groups = {}
    for n, b in enumerate(rows):
        if not b.get("alive", True) or plain(get(b, "id_hidden")) == "Yes": continue
        status = plain(get(b, "status")).strip()
        g = next((label for key, label in GROUPS if key.lower() == status.lower()), None)
        if not g:
            if status.lower() in HIDDEN_STATUS: continue
            g = status   # a new status added in Notion gets its own group (shown before Alumni)
        name = N(plain(get(b, "name")))
        x = dict(extras.get(name.lower(), {}))
        x.pop("group", None)
        person = {"name": name, "name_ko": x.pop("name_ko", "")}
        person.update(x)
        if b["id"] in MEMBER_URLS: person["page"] = MEMBER_URLS[b["id"]]
        hp = plain(get(b, "Homepage"))
        if hp.startswith("http") and "homepage" not in person: person["homepage"] = hp
        if not person.get("photo"):
            att = [a[1] for seg in (get(b, "Profile image") or []) for a in (seg[1] if len(seg) > 1 else []) if a[0] == "a"]
            if att:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                fn = None
                for f in os.listdir(photo_dir):
                    if f.startswith(slug + ".") and state.get("member_photos", {}).get(slug) == att[0]: fn = f
                if not fn and not args.dump:
                    from media import fetch
                    out = fetch(att[0], b["id"], b.get("space_id"), os.path.join(photo_dir, slug), first_frame=True)
                    if out: fn = os.path.basename(out); state.setdefault("member_photos", {})[slug] = att[0]
                if fn: person["photo"] = "notion/" + fn; keep_photos.add(fn)
        groups.setdefault(g, []).append((n, person))  # same order as the Notion MEMBERS table
    labels = [label for _, label in GROUPS]
    labels[-1:-1] = sorted(g for g in groups if g not in labels)
    out = [{"group": label, "people": [p for _, p in sorted(groups[label], key=lambda t: t[0])]} for label in labels if label in groups]
    for f in os.listdir(photo_dir):
        if f not in keep_photos and not args.dump: os.remove(os.path.join(photo_dir, f))
    if sum(len(g["people"]) for g in out) >= 3:
        write_json(os.path.join(ROOT, "_data/members.json"), out)
    log("member list: " + ", ".join("%s %d" % (g["group"], len(g["people"])) for g in out))


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


# ---------------- projects ----------------
PROJECTS_DB = "a84b8302-1d81-4972-92b6-5a74f5569f60"   # LABDB_projects (shown on the Projects page)


def db_rows(page, block, dumpname):
    """Rows of the database shown by `block` on Notion page `page`: (rows, recordMap, getter)."""
    if args.dump:
        d = json.load(open(os.path.join(args.dump, dumpname + ".json")))
        rm = d["recordMap"]; ids = d["collections"].get(block) or next(iter(d["collections"].values()))
    else:
        rm = notion.load_page(page)
        b = rm["block"][block]
        ids, rm = notion.query(b["collection_id"], b["view_ids"][0], b["space_id"], rm)
    rows = [rm["block"][i] for i in ids if i in rm["block"] and rm["block"][i].get("alive", True)]
    get = prop(rm, rows[0]["parent_id"]) if rows else None
    return rows, rm, get


def ym(d):
    return d[:7].replace("-", ".") if d else ""


def sync_projects():
    rows, rm, get = db_rows(PROJECTS_DB, PROJECTS_DB, "projects")
    today = datetime.date.today().isoformat()
    out = []
    for b in rows:
        title = N(plain(get(b, "project_name"))).replace("\xa0", " ")
        if not title: continue
        d = {}
        for seg in get(b, "date") or []:
            for a in (seg[1] if len(seg) > 1 else []):
                if a[0] == "d": d = a[1]
        start, end = d.get("start_date", ""), d.get("end_date", "")
        st = plain(get(b, "status")).lower()
        status = "ongoing" if "going" in st or "progress" in st else "complete" if st else ("ongoing" if not end or end >= today else "complete")
        rec = {"title": title, "funder": ", ".join(x.strip() for x in plain(get(b, "site_name")).split(",") if x.strip()),
               "start": ym(start), "end": ym(end) if (end and status == "complete") or (end and end > today) else "", "status": status}
        note = N(plain(get(b, "postscript")))
        if note and not note.startswith("["): rec["note"] = note
        out.append(rec)
    out.sort(key=lambda r: r["start"], reverse=True)
    if len(out) >= 3:
        write_json(os.path.join(ROOT, "_data/projects.json"), out)
    log("projects: %d" % len(out))


# ---------------- resources (old "Lab" pages) ----------------
INFRA = ("3fcabcc9-0e34-80b5-9b49-ce0842425db8", "3fcabcc9-0e34-80a8-86a8-f56fb283bbd2")
SEMINAR = ("481c5dbf-1b79-4ccc-8651-35e35c822dae", "0a9d8a9a-ca2c-4d5b-b4aa-d2082cb9356b")
COURSE = "ecd04e3a-7d2c-478c-9df0-c9213eb21bb2"
CATEGORY = {"robots": "Robot", "computeplatform": "Compute platform", "sensor/depth": "Depth sensor", "sensors": "Sensor", "depth": "Depth sensor"}


def file_attachment(v):
    return next((a[1] for seg in (v or []) for a in (seg[1] if len(seg) > 1 else []) if a[0] == "a"), None)


def sync_lab():
    lab = {"compute": [], "robots": [], "seminars": [], "courses": []}
    st = state.setdefault("lab", {})
    # infrastructure
    rows, rm, get = db_rows(*INFRA, "infrastructure")
    img_dir = os.path.join(ROOT, "images/infra"); os.makedirs(img_dir, exist_ok=True)
    keep = set()
    for b in rows:
        name = N(plain(get(b, "EquipmentsName"))); sec = plain(get(b, "Section")).lower()
        amount = N(plain(get(b, "Amount")))
        if not name: continue
        if "comput" in sec:
            lab["compute"].append({"label": name, "value": re.sub(r"\s*장$", "", amount)})
        else:
            cats = [c.strip() for c in plain(get(b, "Category")).split(",") if c.strip()]
            r = {"name": name, "count": amount or "1", "category": CATEGORY.get(cats[0].lower(), cats[0]) if cats else "", "image": ""}
            att = file_attachment(get(b, "Image"))
            if att:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                have = [f for f in os.listdir(img_dir) if f.startswith(slug + ".")]
                if have and st.get("img:" + slug) == att: r["image"] = have[0]
                elif not args.dump:
                    from media import fetch
                    for f in have: os.remove(os.path.join(img_dir, f))
                    out = fetch(att, b["id"], b.get("space_id"), os.path.join(img_dir, slug), first_frame=True)
                    if out: r["image"] = os.path.basename(out); st["img:" + slug] = att
                if r["image"]: keep.add(r["image"])
            lab["robots"].append(r)
    for f in os.listdir(img_dir):
        if f not in keep and not args.dump: os.remove(os.path.join(img_dir, f))
    # seminars: each one gets its own page under /board/seminar-.../
    rows, rm, get = db_rows(*SEMINAR, "seminar")
    sem = []
    for b in rows:
        if plain(get(b, "is_hidden")) == "Yes": continue
        title = N(plain(get(b, "name")))
        d = date_of(get(b, "date")) or ""
        nice = " ".join(w.capitalize() if w.isupper() and len(w) > 2 else w for w in title.split())
        sem.append((d, nice, b))
    sem.sort(key=lambda x: x[0], reverse=True)
    out_dir = os.path.join(ROOT, "_board"); simg = os.path.join(ROOT, "images/gallery/board")
    made = set()
    for d, title, b in sem:
        slug = "seminar-" + (d or "x") + "-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
        made.add(slug)
        md = os.path.join(out_dir, slug + ".md")
        if not args.full and os.path.exists(md) and st.get("sem:" + slug) == b.get("last_edited_time"):
            body = read_body(md)
        else:
            prm = load_page(b["id"], None) if not args.dump else (json.load(open(os.path.join(args.dump, "seminar.json")))["rows"].get(b["id"]))
            if prm is None: continue
            if b["id"] not in prm.get("block", {}): prm.setdefault("block", {})[b["id"]] = b
            media = Media(prm, os.path.join(simg, slug), "/images/gallery/board/" + slug)
            body = Renderer(prm, media, lambda pid: BOARD_URLS.get(pid) or MEMBER_URLS.get(pid)).page(b["id"])
            body = body + "\n" if body else ""
            st["sem:" + slug] = None if media.failed else b.get("last_edited_time")
            log("  rendered", slug)
        fm = ["---", "title: " + yq(title), "date: " + (d or "2000-01-01"), "kind: seminar", "tag: \"Seminar\"",
              "badges: [\"Seminar\"]", "image: \"\"", "show_cover: false", "notion_id: " + b["id"], "---", ""]
        open(md, "w", encoding="utf-8").write("\n".join(fm) + (body or ""))
        lab["seminars"].append({"title": title, "date": d.replace("-", "."), "link": "/board/%s/" % slug})
    for f in os.listdir(out_dir):
        if f.startswith("seminar-") and f[:-3] not in made:
            os.remove(os.path.join(out_dir, f))
            if os.path.isdir(os.path.join(simg, f[:-3])): shutil.rmtree(os.path.join(simg, f[:-3]))
    # courses: '## 2026 Spring' headings followed by 'CODE  Name' lines
    crm = load_full(COURSE, "course")
    if crm:
        from pubs import Flat
        fl = Flat(crm); term = None
        for b in fl.walk(fl.b[COURSE]):
            txt = re.sub(r"\s+", " ", plain((b.get("properties") or {}).get("title"))).strip()
            if b["type"] in ("sub_header", "header", "sub_sub_header"):
                if re.search(r"\d{4}", txt):
                    term = {"term": txt, "list": []}; lab["courses"].append(term)
            elif term is not None and txt:
                term["list"].append(re.sub(r"(\S)\(", r"\1 (", txt))
        lab["courses"] = [t for t in lab["courses"] if t["list"]]
    if lab["compute"] or lab["robots"]:
        write_json(os.path.join(ROOT, "_data/lab.json"), lab)
    log("resources: %d compute, %d robots, %d seminars, %d terms" % (len(lab["compute"]), len(lab["robots"]), len(lab["seminars"]), len(lab["courses"])))


# ---------------- home intro + contact ----------------
MAIN_PAGE = "8929fd4e-b99b-4c4e-9301-9c294dbcbc24"
CONTACT_PAGE = "830f30e4-23ef-4e49-b329-2afe04656597"


def tree(rm, root):
    """Every block under root in reading order, with the callout it sits in (if any)."""
    B = rm.get("block", {})
    def kids(b):
        return [B[c] for c in (b.get("content") or []) if c in B and "type" in B[c] and B[c].get("alive", True)]
    def walk(b, callout):
        for k in kids(b):
            t = k["type"]
            if t == "transclusion_reference":
                ptr = ((k.get("format") or {}).get("transclusion_reference_pointer") or {}).get("id")
                if ptr in B: yield from walk(B[ptr], callout)
                continue
            if t in ("code",): continue
            yield k, callout
            yield from walk(k, k if t == "callout" else callout)
    yield from walk(B[root], None)


def text(b):
    return re.sub(r"\s+", " ", plain((b.get("properties") or {}).get("title"))).strip()


def trim_white_edges(path):
    """Cut plain white strips off the edges of a slide photo (e.g. a white line left under an exported image)."""
    from PIL import Image, ImageStat
    im = Image.open(path).convert("RGB"); w, h = im.size
    def white(box):
        st = ImageStat.Stat(im.crop(box).convert("L"))
        return st.mean[0] > 240 and st.stddev[0] < 12
    t, b, l, r = 0, h, 0, w
    while b - t > h * 0.8 and white((0, b - 1, w, b)): b -= 1
    while b - t > h * 0.8 and white((0, t, w, t + 1)): t += 1
    while r - l > w * 0.8 and white((r - 1, 0, r, h)): r -= 1
    while r - l > w * 0.8 and white((l, 0, l + 1, h)): l += 1
    if (t, b, l, r) != (0, h, 0, w):
        im.crop((l, t, r, b)).save(path, quality=85)


def home_slides(rm):
    """Photos of the 'oopy:slide' callout on the main page -> images/home/slides/, in Notion order."""
    B = rm.get("block", {})
    box = next((b for b in B.values() if b.get("type") == "callout" and b.get("alive", True)
                and "oopy:slide" in "".join(x[0] for x in (b.get("properties") or {}).get("title", []))), None)
    cache = state.setdefault("home_slides", {})
    if not box: return []
    folder = os.path.join(ROOT, "images/home/slides"); os.makedirs(folder, exist_ok=True)
    out, keep = [], set()
    for cid in box.get("content") or []:
        b = B.get(cid)
        if not b or b.get("type") != "image" or not b.get("alive", True): continue
        key = "%s@%s" % (b["id"], b.get("last_edited_time"))
        path = cache.get(b["id"], {}).get("path")
        if cache.get(b["id"], {}).get("key") != key or not path or not os.path.exists(os.path.join(ROOT, path)):
            if args.dump:
                if path: out.append(path); keep.add(b["id"])
                continue
            src = Renderer.source(b)
            from media import fetch
            got = fetch(src, b["id"], b.get("space_id"), os.path.join(folder, b["id"].replace("-", "")))
            if not got:
                if path: out.append(path); keep.add(b["id"])
                continue
            if got.lower().endswith((".jpg", ".jpeg", ".png")): trim_white_edges(got)
            path = os.path.relpath(got, ROOT).replace(os.sep, "/")
            cache[b["id"]] = {"key": key, "path": path}
        out.append(path); keep.add(b["id"])
    if not args.dump:
        for bid in list(cache):
            if bid not in keep:
                p = os.path.join(ROOT, cache.pop(bid)["path"])
                if os.path.exists(p): os.remove(p)
    log("home: %d slides" % len(out))
    return out


def sync_home():
    rm = load_full(MAIN_PAGE, "main")
    if not rm: return
    home = {"lede": "", "research": [], "recruiting": ""}
    after_welcome, in_recruit = False, False
    for b, callout in tree(rm, MAIN_PAGE):
        t, x = b["type"], text(b)
        if t == "header" and x.lower().startswith("welcome"): after_welcome = True; continue
        if after_welcome and t == "text" and x and not home["lede"]: home["lede"] = x; continue
        if after_welcome and t == "bulleted_list" and x:
            m = re.match(r"(.+?)\s+[—–-]\s+(.+)", x)
            home["research"].append({"title": m.group(1), "summary": m.group(2)} if m else {"title": x, "summary": ""}); continue
        if t in ("sub_header", "header", "sub_sub_header") and "recruit" in x.lower(): in_recruit = True; continue
        if in_recruit and t == "text" and x and not home["recruiting"] and "join" not in x.lower(): home["recruiting"] = x
    home["slides"] = home_slides(rm)
    if home["lede"] and home["research"]:
        write_json(os.path.join(ROOT, "_data/home.json"), home)
    log("home: %d research lines" % len(home["research"]))


def sync_contact():
    rm = load_full(CONTACT_PAGE, "contact")
    if not rm: return
    j = {"notice": [], "intro": "", "principles": [], "offer": "", "tracks": [], "address": []}
    track, part = None, None
    for b, callout in tree(rm, CONTACT_PAGE):
        t, x = b["type"], text(b)
        if not x: continue
        if t == "sub_header":
            m = re.match(r"(?:for\s+)?(.+?)\s*(?:\((.+)\))?$", x, re.I)
            label, title = m.group(1), m.group(2) or m.group(1)
            short = "Undergraduate" if "intern" in label.lower() else "Graduate" if "graduate" in label.lower() else "Researcher" if "research" in label.lower() or "postdoc" in label.lower() else label
            track = {"label": short, "title": label}
            if m.group(2): track["dept"] = m.group(2)
            j["tracks"].append(track); part = None; continue
        if t == "sub_sub_header":
            low = x.lower(); part = "role" if "role" in low else "apply" if "appl" in low else "recommended" if "recommend" in low else None
            continue
        if t == "callout":
            continue
        if callout is not None and track is None and t == "bulleted_list":
            j["notice"].append(x); continue
        if callout is not None and track is not None and t == "bulleted_list" and part is None:
            track["notice"] = (track.get("notice", "") + " " + x).strip(); continue
        if callout is not None and t == "text" and track is not None and track is j["tracks"][-1] and part is not None and "address" in "".join(j["address"]).lower() or (callout is not None and t == "text" and re.search(r"phone|address|\(\+82\)|department|college|laboratory|lab\.", x, re.I) and track is not None and part is not None):
            if not re.fullmatch(r"\[.*\]", x): j["address"].append(x)
            continue
        if track is None:
            if t == "numbered_list": j["principles"].append(x)
            elif t == "text" and callout is None:
                if not j["intro"]: j["intro"] = x
                else: j["offer"] = x
            continue
        if part and t in ("bulleted_list", "numbered_list"):
            track.setdefault(part, []).append(x)
    if j["tracks"]:
        write_json(os.path.join(ROOT, "_data/join.json"), j)
    log("contact: %d notices, %d principles, %d tracks" % (len(j["notice"]), len(j["principles"]), len(j["tracks"])))


BOARD_URLS = {k: "/board/%s/" % v["slug"] for k, v in state.get("board", {}).items()}
sync_home()
sync_contact()
sync_publications()
sync_projects()
sync_members()
sync_board()
sync_lab()
json.dump(state, open(STATE, "w"), ensure_ascii=False, indent=1, sort_keys=True)
