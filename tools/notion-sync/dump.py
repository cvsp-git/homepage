"""Dump the lab's public Notion pages to JSON (for developing the sync)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from notion import load_page, query, fill_missing

PAGES = {
    "main": "8929fd4e-b99b-4c4e-9301-9c294dbcbc24",
    "intl": "d9c4ac58-eaed-42a2-935d-e1c83397e1dd",
    "domestic": "00312390-10c3-4807-a64a-f3cef4306fdf",
    "projects": "ec11e112-7fdd-46a8-9d83-3f48bb54eb6b",
    "members": "270ea83e-d9e0-461f-9051-1195c9bd31fb",
    "contact": "830f30e4-23ef-4e49-b329-2afe04656597",
    "course": "ecd04e3a-7d2c-478c-9df0-c9213eb21bb2",
    "infrastructure": "3fcabcc9-0e34-80b5-9b49-ce0842425db8",
    "seminar": "481c5dbf-1b79-4ccc-8651-35e35c822dae",
}
out = sys.argv[1]
os.makedirs(out, exist_ok=True)

def refs(rm):
    r = []
    for v in rm.get("block", {}).values():
        ptr = ((v.get("format") or {}).get("transclusion_reference_pointer") or {}).get("id")
        if ptr: r.append(ptr)
        if v.get("type", "").startswith("transclusion"): r += v.get("content") or []
    return r

for name, pid in PAGES.items():
    rm = load_page(pid)
    for _ in range(3):
        want = [x for x in refs(rm) if x not in rm.get("block", {})]
        if not want: break
        fill_missing(rm, want)
        fill_missing(rm, [c for w in want for c in (rm["block"].get(w, {}).get("content") or [])])
    colls = {}
    for bid, b in list(rm["block"].items()):
        if b.get("type") in ("collection_view", "collection_view_page") and b.get("collection_id") and b.get("view_ids"):
            try:
                ids, rm = query(b["collection_id"], b["view_ids"][0], b["space_id"], rm)
                colls[bid] = ids
            except Exception as e:
                print(name, "query fail", bid, e)
    rows = {}
    for bid, ids in colls.items():
        if len(ids) > 120: continue
        for i in ids:
            try:
                rows[i] = load_page(i)
            except Exception as e:
                print("  row fail", i, e)
    json.dump({"page": pid, "recordMap": rm, "collections": colls, "rows": rows}, open(f"{out}/{name}.json", "w"), ensure_ascii=False)
    print(name, "blocks", len(rm.get("block", {})), "collections", {k: len(v) for k, v in colls.items()}, "row pages", len(rows))
print("done")
