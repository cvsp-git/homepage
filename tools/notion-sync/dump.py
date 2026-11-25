"""Dump the lab's public Notion data to JSON (for developing the sync)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from notion import load_page, query, fill_missing

MAIN = "8929fd4e-b99b-4c4e-9301-9c294dbcbc24"
BOARD = "c6158afa-34c1-4fbf-bf5e-3af211773d19"     # LABDB_images
FAMILY = "07237418-f973-4512-b2e6-d9339488a79d"    # LABDB_family
out = sys.argv[1]
os.makedirs(out, exist_ok=True)

def dbdump(name, page):
    rm = load_page(page)
    b = rm["block"][page]
    ids, rm = query(b["collection_id"], b["view_ids"][0], b["space_id"], rm)
    print(name, "rows:", len(ids))
    json.dump({"page": page, "rows": ids, "recordMap": rm}, open(f"{out}/{name}.json", "w"), ensure_ascii=False)
    return ids, rm

json.dump(load_page(MAIN), open(f"{out}/main.json", "w"), ensure_ascii=False)
for name, page in [("board", BOARD), ("family", FAMILY)]:
    ids, rm = dbdump(name, page)
    os.makedirs(f"{out}/{name}", exist_ok=True)
    for i in ids:
        try:
            prm = load_page(i)
            # pull in referenced blocks (synced blocks etc.)
            refs = []
            for v in prm.get("block", {}).values():
                refs += v.get("content", []) or []
                ptr = (v.get("format") or {}).get("transclusion_reference_pointer")
                if ptr: refs.append(ptr["id"])
            fill_missing(prm, refs)
            json.dump(prm, open(f"{out}/{name}/{i}.json", "w"), ensure_ascii=False)
        except Exception as e:
            print("  fail", i, e)
print("done")
