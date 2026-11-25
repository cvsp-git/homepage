"""Minimal reader for public Notion pages (no token needed)."""
import json, time, urllib.request, urllib.error

API = "https://www.notion.so/api/v3/"
HDR = {"content-type": "application/json", "user-agent": "Mozilla/5.0 (cvsp-homepage-sync)"}


def post(ep, body, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + ep, json.dumps(body).encode(), HDR)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError) as e:
            if i == tries - 1 or (isinstance(e, urllib.error.HTTPError) and e.code < 500 and e.code != 429):
                raise
            time.sleep(2 ** i * 2)


def unwrap(rec):
    v = (rec or {}).get("value", {})
    return v.get("value", v) if isinstance(v, dict) and "value" in v and isinstance(v["value"], dict) else v


def merge(dst, rm):
    for table, recs in (rm or {}).items():
        if not isinstance(recs, dict):
            continue
        t = dst.setdefault(table, {})
        for k, rec in recs.items():
            v = unwrap(rec)
            if v:
                t[k] = v


def load_page(pid, rm=None):
    """Load every block of a page into rm (table -> id -> value)."""
    rm = {} if rm is None else rm
    cursor, n = {"stack": []}, 0
    while True:
        d = post("loadPageChunk", {"pageId": pid, "limit": 100, "cursor": cursor,
                                   "chunkNumber": n, "verticalColumns": False})
        merge(rm, d.get("recordMap"))
        cursor = d.get("cursor") or {"stack": []}
        n += 1
        if not cursor.get("stack") or n > 50:
            return rm


def query(collection_id, view_id, space_id, rm=None):
    rm = {} if rm is None else rm
    d = post("queryCollection", {
        "collection": {"id": collection_id, "spaceId": space_id},
        "collectionView": {"id": view_id, "spaceId": space_id},
        "loader": {"type": "reducer", "reducers": {"collection_group_results": {"type": "results", "limit": 5000}},
                   "searchQuery": "", "userTimeZone": "Asia/Seoul"},
    })
    merge(rm, d.get("recordMap"))
    ids = d["result"]["reducerResults"]["collection_group_results"]["blockIds"]
    return ids, rm


def fill_missing(rm, ids):
    """Fetch blocks referenced but not loaded."""
    ids = [i for i in ids if i not in rm.get("block", {})]
    for k in range(0, len(ids), 100):
        d = post("syncRecordValues", {"requests": [{"pointer": {"table": "block", "id": i}, "version": -1} for i in ids[k:k + 100]]})
        merge(rm, d.get("recordMap"))
    return rm
