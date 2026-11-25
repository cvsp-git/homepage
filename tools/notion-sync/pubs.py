"""Parse the Notion 'International Papers' / 'Domestic Papers' pages into publication records.

Layout on the Notion page (kept by the lab since the old site):
  # 2026                     (header: year; '~2018' means 'this year or before')
  ## Journals / Conferences  (sub_header)
  ### [C57] Title            (sub_sub_header or header_4)
  venue line                 (grey text; '(Top-tier ..., Acceptance Rate ...)' at the end becomes the note)
  author line                (grey text; * first author, † corresponding author)
  tag line                   (blue = area, teal = topic)
  links                      ([Paper], [Project Page], [Code] ... anywhere in the entry)
  divider
"""
import re

TITLE_RE = re.compile(r"^\s*\[\s*([A-Za-z]+\s*\d+)\s*\]\s*(.+?)\s*$", re.S)
NOTE_RE = re.compile(r"\(([^()]*(?:top-tier|acceptance|oral|spotlight|highlight|award|presentation|if:|jcr|impact factor|best)[^()]*)\)\s*\.?\s*$", re.I)


TAG_COLORS = ("blue", "teal", "purple", "green", "orange", "pink", "red", "brown", "yellow")


def plain(t):
    return "".join(seg[0] for seg in (t or []) if seg[0] != "‣")


def segs(t):
    for seg in t or []:
        anns = seg[1] if len(seg) > 1 else []
        yield seg[0], {a[0]: (a[1] if len(a) > 1 else True) for a in anns}


class Flat:
    def __init__(self, rm):
        self.b = rm.get("block", {})

    def kids(self, b):
        return [self.b[c] for c in (b.get("content") or []) if c in self.b and "type" in self.b[c] and self.b[c].get("alive", True)]

    def walk(self, b, skip_toggles=True):
        for k in self.kids(b):
            t = k["type"]
            if t == "transclusion_reference":
                ptr = ((k.get("format") or {}).get("transclusion_reference_pointer") or {}).get("id")
                if ptr in self.b: yield from self.walk(self.b[ptr], skip_toggles)
            elif t in ("transclusion_container", "column_list", "column"):
                yield from self.walk(k, skip_toggles)
            elif t in ("callout", "code") or (t == "toggle" and skip_toggles):
                continue
            else:
                yield k
                if t in ("text", "bulleted_list", "numbered_list"):
                    yield from self.walk(k, skip_toggles)


def split_authors(s):
    s = re.sub(r"\s+", " ", s).strip().rstrip(".")
    parts = re.split(r",\s*|\s+and\s+", s)
    return [p.strip() for p in parts if p.strip()]


def parse(rm, page_id, kind):
    """kind: 'intl' or 'dom'. Returns a list of dicts in page order."""
    f = Flat(rm)
    out, year, ptype, cur = [], None, None, None
    for b in f.walk(f.b[page_id]):
        t = b["type"]
        title = (b.get("properties") or {}).get("title")
        txt = plain(title).strip()
        if t == "header":
            m = re.search(r"(\d{4})", txt)
            year = (int(m.group(1)) if not txt.strip().startswith("~") else None) if m else year
            cur = None; continue
        if t == "sub_header":
            low = txt.lower()
            ptype = "journal" if "journal" in low else "conference" if "conference" in low else ptype
            cur = None; continue
        if t in ("sub_sub_header", "header_4"):
            m = TITLE_RE.match(txt)
            if not m: cur = None; continue
            pid = m.group(1).replace(" ", "").upper()
            cur = dict(id=pid, type=("journal" if pid.startswith("J") else "conference" if pid.startswith("C") else ptype or "conference"),
                       year=year, title=re.sub(r"\s+", " ", m.group(2)).strip(), lines=[], links=[], tagsegs=[])
            out.append(cur); continue
        if t == "divider":
            cur = None; continue
        if cur is None or t not in ("text", "bulleted_list"):
            continue
        bcolor = (b.get("format") or {}).get("block_color")
        # split the block into visual lines (Notion soft line breaks)
        lines, curl = [], []
        for seg in title or []:
            parts = seg[0].split("\n")
            for i, part in enumerate(parts):
                if i: lines.append(curl); curl = []
                if part: curl.append([part] + seg[1:])
        lines.append(curl)
        for ln in lines:
            tagline, textlen = [], 0
            for s, a in segs(ln):
                if "a" in a and isinstance(a["a"], str) and a["a"].startswith("http") and "pnu-cvsp.com/research" not in a["a"]:
                    cur["links"].append((s.strip(" []"), a["a"])); continue
                if not s.strip() or s == "‣": continue
                textlen += len(s.strip())
                if (a.get("h") or bcolor) in TAG_COLORS:
                    tagline.append(s.strip())
            line = re.sub(r"\s+", " ", plain([seg for seg in ln if not (len(seg) > 1 and any(x[0] == "a" and str(x[1]).startswith("http") and "pnu-cvsp.com/research" not in str(x[1]) for x in seg[1]))])).strip()
            if tagline and sum(len(x) for x in tagline) >= textlen - 2:
                cur["tagsegs"] += tagline
            elif line and re.sub(r"[\[\]\s|·,/()]", "", line):
                cur["lines"].append(line)
    res = []
    for e in out:
        lines = e.pop("lines"); links = e.pop("links"); tags = e.pop("tagsegs")
        also = [l for l in lines[1:] if re.match(r"(also|presented|invited)\b", l, re.I)]
        lines = [l for l in lines if l not in also]
        venue = lines[0] if lines else ""
        authors = split_authors(lines[1]) if len(lines) > 1 else []
        rec = {"id": e["id"], "type": e["type"]}
        note = ""
        m = NOTE_RE.search(venue)
        if m:
            note = m.group(1).strip(); venue = venue[:m.start()].strip()
        y = re.findall(r"(?:19|20)\d{2}", venue)
        rec["year"] = e["year"] or (int(y[-1]) if y else None)
        rec["title"] = e["title"]
        rec["venue"] = venue.rstrip(" .") + "".join(" · " + a.rstrip(" .") for a in also)
        rec["authors"] = authors
        if tags: rec["tags"] = tags
        if note: rec["note"] = note
        extra = []
        for label, url in links:
            l = label.lower()
            if "project" in l and "project" not in rec: rec["project"] = url
            elif ("code" in l or "github" in l) and "code" not in rec: rec["code"] = url
            elif ("paper" in l or "pdf" in l or "arxiv" in l) and "paper" not in rec: rec["paper"] = url
            else: extra.append({"label": label or "Link", "url": url})
        if extra: rec["links"] = extra
        res.append(rec)
    return res
