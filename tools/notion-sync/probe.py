"""Check whether the lab's public Notion pages can be read without a token."""
import json, urllib.request

API = "https://www.notion.so/api/v3/"
PAGES = {
    "main": "8929fd4e-b99b-4c4e-9301-9c294dbcbc24",
    "LABDB_images": "c6158afa-34c1-4fbf-bf5e-3af211773d19",
}

def post(ep, body):
    req = urllib.request.Request(API + ep, json.dumps(body).encode(),
                                 {"content-type": "application/json", "user-agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def title(v):
    t = v.get("properties", {}).get("title")
    return "".join(x[0] for x in t) if t else v.get("name", "")

for name, pid in PAGES.items():
    try:
        d = post("loadPageChunk", {"pageId": pid, "limit": 100, "cursor": {"stack": []},
                                   "chunkNumber": 0, "verticalColumns": False})
        blocks = d.get("recordMap", {}).get("block", {})
        colls = d.get("recordMap", {}).get("collection", {})
        print(f"[{name}] blocks={len(blocks)} collections={len(colls)}")
        for bid, b in list(blocks.items())[:40]:
            v = b.get("value", {})
            if v.get("type") in ("page", "collection_view", "collection_view_page"):
                print("   ", v.get("type"), bid, title(v)[:60])
        for cid, c in colls.items():
            print("    collection", cid, title(c.get("value", {}))[:60])
    except Exception as e:
        print(f"[{name}] FAILED: {e}")
