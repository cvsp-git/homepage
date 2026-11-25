"""Check whether the lab's public Notion pages can be read without a token."""
import json, re, urllib.request

API = "https://www.notion.so/api/v3/"
UA = {"content-type": "application/json", "user-agent": "Mozilla/5.0"}

def post(ep, body):
    req = urllib.request.Request(API + ep, json.dumps(body).encode(), UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def text(t):
    return "".join(x[0] for x in t) if t else ""

def chunk(pid):
    d = post("loadPageChunk", {"pageId": pid, "limit": 200, "cursor": {"stack": []},
                               "chunkNumber": 0, "verticalColumns": False})
    return d["recordMap"]

def show(name, pid):
    rm = chunk(pid)
    blocks = rm.get("block", {})
    print(f"== {name} {pid}: blocks={len(blocks)}")
    for bid, b in blocks.items():
        v = b.get("value", {})
        if "value" in v: v = v["value"]
        t = v.get("type")
        if t not in ("text", "image", "column", "column_list", "divider", None):
            print("   ", t, bid, text(v.get("properties", {}).get("title"))[:50],
                  v.get("collection_id", ""), (v.get("view_ids") or [""])[0])
    for cid, c in rm.get("collection", {}).items():
        v = c.get("value", {})
        if "value" in v: v = v["value"]
        print("    collection", cid, text(v.get("name")), "props:",
              [p.get("name") for p in v.get("schema", {}).values()][:20])
    return rm

show("main", "8929fd4e-b99b-4c4e-9301-9c294dbcbc24")

# find member page ids from the oopy site
for path in ["/members", "/members/woohyeong"]:
    try:
        req = urllib.request.Request("https://www.pnu-cvsp.com" + path, headers={"user-agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        m = re.search(r'"pageId"\s*:\s*"([^"]+)"', html) or re.search(r'notion\.(?:so|site)/[^"]*?([0-9a-f]{32})', html)
        print("   pageId hint:", m.group(1) if m else None, "| has __NEXT_DATA__:", "__NEXT_DATA__" in html, "| recordMap:", "recordMap" in html)
        ids = sorted(set(re.findall(r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}", html)))
        print(f"== oopy {path}: {len(html)} bytes, ids={ids[:8]}")
        if path.endswith("woohyeong") and ids:
            for i in ([m.group(1)] if m else ids[2:4]):
                try:
                    show("member?", i)
                except Exception as e:
                    print("   fail", i, e)
    except Exception as e:
        print("oopy", path, "FAILED", e)
