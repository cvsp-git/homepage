"""Find which Notion pages the old oopy site serves for each menu item."""
import json, re, sys, os, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
import notion

def get(u):
    req = urllib.request.Request(u, headers={"user-agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

home = get("https://www.pnu-cvsp.com/")
paths = sorted(set(re.findall(r'(?:href="|"url":")(?:https?://www\.pnu-cvsp\.com)?(/[a-z][\w/-]*)"', home)) | {"/publications", "/projects", "/lab", "/members", "/contact", "/gallery", "/news", "/research", "/publication", "/project"})
print("links on home:", paths)
for path in paths:
    if path.startswith(("/_next", "/board", "/members/")): continue
    try:
        html = get("https://www.pnu-cvsp.com" + path)
    except Exception as e:
        print(path, "FAIL", e); continue
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m: print(path, "no next data"); continue
    d = json.loads(m.group(1))
    s = json.dumps(d)
    pid = None
    for key in ("pageId", "notionPageId", "blockId", "id"):
        mm = re.search(r'"%s"\s*:\s*"([0-9a-f-]{32,36})"' % key, s)
        if mm: pid = mm.group(1); break
    print("==", path, "page id:", pid)
    if pid:
        try:
            rm = notion.load_page(pid)
            b = rm["block"].get(pid) or {}
            t = "".join(x[0] for x in (b.get("properties") or {}).get("title", []))
            types = {}
            for v in rm["block"].values(): types[v.get("type")] = types.get(v.get("type"), 0) + 1
            print("   title:", t, "| blocks:", types)
            for cid, c in rm.get("collection", {}).items():
                print("   collection", cid, "".join(x[0] for x in c.get("name") or []), [p["name"] for p in c.get("schema", {}).values()][:15])
        except Exception as e:
            print("   load fail", e)
