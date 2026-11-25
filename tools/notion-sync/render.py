"""Render Notion blocks (public recordMap) to kramdown-flavoured Markdown for Jekyll."""
import html, json, re, urllib.parse

OOPY_CODE = re.compile(r'cleanUrl|<head>|<style|oopy|^\s*speed:|^\s*type:\s*"crossfade"', re.M)


def plain(t):
    return "".join(seg[0] for seg in (t or []))


def esc(s):
    s = s.replace("\\", "\\\\")
    s = re.sub(r'([*_`\[\]<>|])', r'\\\1', s)
    return s


class Renderer:
    """media(kind, source, block, caption) -> web path or None.  link(page_id) -> url or None."""

    def __init__(self, rm, media, link):
        self.rm, self.media, self.link = rm, media, link
        self.blocks = rm.get("block", {})
        self.has_media = False

    # ---------- inline ----------
    @staticmethod
    def _merge(t):
        """Join neighbouring segments that only differ in colour, so **a****b** becomes **ab**."""
        res = []
        for seg in t or []:
            anns = list(seg[1] if len(seg) > 1 else [])
            key = sorted(json.dumps(a) for a in anns)
            if res and seg[0] != "‣" and res[-1][0] != "‣" and res[-1][2] == key:
                res[-1][0] += seg[0]
            else:
                res.append([seg[0], anns, key])
        return [[x, a] for x, a, _ in res]

    def rich(self, t):
        out = []
        for seg in self._merge(t):
            txt = seg[0]
            anns = seg[1] if len(seg) > 1 else []
            if txt == "‣":
                out.append(self.mention(anns)); continue
            href = None
            for a in anns:
                if a[0] == "a": href = a[1]
            core_raw = txt.strip()
            lead = txt[:len(txt) - len(txt.lstrip())].replace("\n", "<br>")
            trail = txt[len(txt.rstrip()):].replace("\n", "<br>")
            if not core_raw:  # whitespace only: keep it once (a lone "\n" is one line break, not two)
                out.append(txt.replace("\n", "<br>")); continue
            core = esc(core_raw).replace("\n", "<br>")
            kinds = [a[0] for a in anns]
            if "c" in kinds: core = "<code>" + html.escape(core_raw).replace("\n", "<br>") + "</code>"
            if "b" in kinds: core = "**" + core + "**"
            if "i" in kinds: core = "*" + core + "*"
            if "s" in kinds: core = "~~" + core + "~~"
            if "_" in kinds: core = "<u>" + core + "</u>"
            if href: core = "[%s](%s)" % (core, self.fix_href(href))
            color = next((a[1] for a in anns if a[0] == "h" and isinstance(a[1], str)), None)
            if color and color != "default":
                core = '<span class="nc-%s">%s</span>' % (re.sub(r"[^a-z_]", "", color), core)
            s = lead + core + trail
            out.append(s)
        return "".join(out)

    def mention(self, anns):
        for a in anns:
            if a[0] == "d":
                d = a[1]
                return d.get("start_date", "") + (" → " + d["end_date"] if d.get("end_date") else "")
            if a[0] == "p":
                b = self.blocks.get(a[1], {})
                title = esc(plain((b.get("properties") or {}).get("title"))) or "link"
                url = self.link(a[1])
                return "[%s](%s)" % (title, url) if url else title
            if a[0] == "lm":
                m = a[1] if isinstance(a[1], dict) else {}
                return "[%s](%s)" % (esc(m.get("title") or m.get("href", "")), m.get("href", ""))
        return ""

    def fix_href(self, u):
        m = re.search(r'([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12})(?:[?#].*)?$', u)
        if m and ("notion" in u or "pnu-cvsp.com" in u or u.startswith("/")):
            h = m.group(1).replace("-", "")
            pid = "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:])
            url = self.link(pid)
            if url: return url
        if re.match(r'https?://(www\.)?pnu-cvsp\.com/members/([\w-]+)', u):
            return "/members/" + re.match(r'https?://(www\.)?pnu-cvsp\.com/members/([\w-]+)', u).group(2) + "/"
        if re.match(r'https?://(www\.)?pnu-cvsp\.com/?$', u): return "/"
        if u.startswith("/") and not u.startswith("//"):
            return "https://www.notion.so" + u
        return u

    # ---------- blocks ----------
    def children(self, b):
        return [self.blocks[c] for c in (b.get("content") or []) if c in self.blocks and self.blocks[c].get("alive", True) and "type" in self.blocks[c]]

    def page(self, pid):
        out = self.render_list(self.children(self.blocks[pid]), 0)
        text = "\n".join(out)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        if "{{" in text or "{%" in text:
            text = "{% raw %}\n" + text + "\n{% endraw %}"
        return text

    def render_list(self, bs, ind):
        out, n = [], 0
        for b in bs:
            n = n + 1 if b["type"] == "numbered_list" else 0
            out += self.block(b, ind, n)
        return out

    def block(self, b, ind, n=0):
        t, p, f = b["type"], b.get("properties") or {}, b.get("format") or {}
        pad = " " * ind
        title = self.rich(p.get("title"))
        bc = re.sub(r"[^a-z_]", "", f.get("block_color") or "")
        if bc and bc != "default" and title.strip() and t in ("text", "bulleted_list", "numbered_list", "header", "sub_header", "sub_sub_header", "quote", "toggle"):
            title = '<span class="nc-%s">%s</span>' % (bc, title)
        kids = self.children(b)
        if t == "text":
            out = [pad + title if title.strip() else ""]
            if kids: out += self.render_list(kids, ind)
            if title.strip(): return [""] + out + [""]
            # an empty Notion line: kept as a blank gap (shown on member pages, like Notion)
            return ["", pad + '<p class="nb-gap"></p>', ""] if not kids else [""] + out + [""]
        if t in ("header", "sub_header", "sub_sub_header"):
            lvl = {"header": 1, "sub_header": 2, "sub_sub_header": 3}[t]
            return ["", pad + "#" * lvl + " " + title, ""] if title.strip() else []
        if t in ("bulleted_list", "numbered_list"):
            mark = "- " if t == "bulleted_list" else "%d. " % (n or 1)
            out = [pad + mark + title]
            out += self.render_list(kids, ind + len(mark))
            return out
        if t == "to_do":
            chk = "☑" if plain(p.get("checked")) == "Yes" else "☐"
            return [pad + "- " + chk + " " + title] + self.render_list(kids, ind + 2)
        if t == "quote":
            body = [title] + ["\n".join(self.render_list(kids, 0))] if kids else [title]
            return [""] + [pad + "> " + line for line in "\n".join(body).split("\n")] + [""]
        if t == "divider":
            return ["", pad + "<hr>", ""]
        if t == "code":
            code = plain(p.get("title"))
            if OOPY_CODE.search(code): return []
            lang = plain(p.get("language")).lower().replace("plain text", "")
            return ["", pad + "```" + lang] + [pad + l for l in code.split("\n")] + [pad + "```", ""]
        if t == "callout":
            if "oopy:slide" in plain(p.get("title")):
                imgs = []
                for k in self._flatten(kids):
                    if k["type"] == "image":
                        src = self.media("image", self.source(k), k, "")
                        if src: imgs.append('<figure><img src="%s" alt="" loading="lazy"></figure>' % src)
                return ["", '<div class="board-slide" data-slide><div class="board-slide-track">' + "".join(imgs) + "</div></div>", ""] if imgs else []
            icon = f.get("page_icon") or ""
            icon = icon if icon and not icon.startswith(("http", "/")) else ""
            out = ["", pad + '<div class="callout" markdown="1">', ""]
            out += [pad + ((icon + " ") if icon else "") + title, ""]
            out += self.render_list(kids, ind)
            return out + ["", pad + "</div>", ""]
        if t == "toggle":
            out = ["", pad + '<details markdown="1"><summary>%s</summary>' % title, ""]
            out += self.render_list(kids, ind)
            return out + ["", pad + "</details>", ""]
        if t == "image":
            src = self.media("image", self.source(b), b, "")
            if not src: return []
            cap = self.rich(p.get("caption"))
            return ["", pad + '<figure class="board-fig"><img src="%s" alt="" loading="lazy">%s</figure>' % (
                src, '<figcaption markdown="span">%s</figcaption>' % cap if cap.strip() else ""), ""]
        if t == "video":
            s = self.source(b)
            yt = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([\w-]{6,})', s or "")
            if yt:
                return ["", pad + '<div class="board-embed"><iframe src="https://www.youtube.com/embed/%s" allowfullscreen loading="lazy"></iframe></div>' % yt.group(1), ""]
            src = self.media("video", s, b, "")
            if not src: return []
            tag = ('<video src="%s" autoplay loop muted playsinline controls preload="metadata"></video>' % src
                   if src.endswith(".mp4") else '<img src="%s" alt="" loading="lazy">' % src)
            return ["", pad + '<figure class="board-fig">%s</figure>' % tag, ""]
        if t in ("bookmark", "embed", "file", "pdf"):
            link = self.source(b) or plain(p.get("link"))
            if not link: return []
            if t in ("file", "pdf"):
                src = self.media("file", link, b, "") or "https://www.notion.so/" + b["id"].replace("-", "")
                name = plain(p.get("title")) or "file"
                return ["", pad + "[📎 %s](%s)" % (esc(name), src), ""]
            name = plain(p.get("title")) or link
            return ["", pad + "[%s](%s)" % (esc(name), link), ""]
        if t == "column_list":
            cols = []
            for c in kids:
                inner = "\n".join(self.render_list(self.children(c), 0)).strip()
                cols.append('<div markdown="1">\n\n' + inner + '\n\n</div>')
            return ["", '<div class="board-cols">', ""] + cols + ["", "</div>", ""]
        if t == "column":
            return self.render_list(kids, ind)
        if t == "transclusion_container":
            return self.render_list(kids, ind)
        if t == "transclusion_reference":
            ptr = (f.get("transclusion_reference_pointer") or {}).get("id")
            src = self.blocks.get(ptr)
            return self.render_list(self.children(src), ind) if src else []
        if t == "table":
            order = f.get("table_block_column_order") or []
            rows = []
            for r in kids:
                rp = r.get("properties") or {}
                rows.append("<tr>" + "".join("<td>%s</td>" % self.rich(rp.get(c)) for c in order) + "</tr>")
            return ["", '<div class="board-table"><table>' + "".join(rows) + "</table></div>", ""]
        if t in ("page", "alias"):
            pid = b["id"] if t == "page" else (f.get("alias_pointer") or {}).get("id")
            url = self.link(pid) if pid else None
            tb = self.blocks.get(pid, b)
            name = esc(plain((tb.get("properties") or {}).get("title")))
            return ["", pad + ("[%s](%s)" % (name, url) if url else name), ""] if name else []
        if t == "equation":
            return ["", pad + "$$" + plain(p.get("title")) + "$$", ""]
        # copy_indicator, collection views, breadcrumb, table_of_contents, ...
        return self.render_list(kids, ind) if kids else []

    def _flatten(self, bs):
        for b in bs:
            yield b
            yield from self._flatten(self.children(b))

    @staticmethod
    def source(b):
        p = b.get("properties") or {}
        f = b.get("format") or {}
        return plain(p.get("source")) or f.get("display_source") or ""
