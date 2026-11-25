"""Download Notion-hosted / external media and convert to web-friendly files."""
import os, re, shutil, subprocess, tempfile, urllib.parse, urllib.request
from notion import post

try:
    from PIL import Image, ImageOps, ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    Image.MAX_IMAGE_PIXELS = None
    try:
        import pillow_heif; pillow_heif.register_heif_opener()
    except ImportError:
        pass
except ImportError:  # offline render tests
    Image = None

MAXPX = 1600
UA = {"user-agent": "Mozilla/5.0 (cvsp-homepage-sync)"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff"}


def notion_hosted(src):
    return src.startswith("attachment:") or "amazonaws.com" in src or "notion-static.com" in src or "file.notion.so" in src


def signed_url(src, block_id, space_id):
    try:
        d = post("getSignedFileUrls", {"urls": [{"url": src, "permissionRecord": {"table": "block", "id": block_id, "spaceId": space_id}}]})
        u = (d.get("signedUrls") or [None])[0]
        if u: return u
    except Exception as e:
        print("   signed url failed:", e)
    return "https://www.notion.so/image/%s?table=block&id=%s&spaceId=%s&cache=v2" % (urllib.parse.quote(src, safe=""), block_id, space_id)


def name_of(src):
    if src.startswith("attachment:"):
        return src.split(":", 2)[-1]
    return urllib.parse.unquote(urllib.parse.urlparse(src).path.rsplit("/", 1)[-1])


def download(url, dst):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)
        return r.headers.get("content-type", "")


def _save_jpg(im, dst):
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3]); im = bg
    im = im.convert("RGB"); im.thumbnail((MAXPX, MAXPX), Image.LANCZOS)
    im.save(dst, "JPEG", quality=82, optimize=True, progressive=True)


def convert(src, ext, dst_noext, first_frame=False):
    """Returns the written path, or None."""
    ext = ext.lower()
    if ext == ".svg":
        shutil.copy(src, dst_noext + ".svg"); return dst_noext + ".svg"
    if ext == ".gif" and (first_frame or os.path.getsize(src) > 3_000_000):
        if first_frame:
            im = Image.open(src); im.seek(0); _save_jpg(im, dst_noext + ".jpg"); return dst_noext + ".jpg"
        ext = ".mp4"
    if ext == ".gif":
        shutil.copy(src, dst_noext + ".gif"); return dst_noext + ".gif"
    if ext in (".mp4", ".mov", ".webm", ".m4v"):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c:a", "aac", "-vf", "scale='min(1280,iw)':-2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", "-preset", "medium",
                        "-movflags", "+faststart", dst_noext + ".mp4"], check=True)
        return dst_noext + ".mp4"
    _save_jpg(Image.open(src), dst_noext + ".jpg")
    return dst_noext + ".jpg"


def fetch(src, block_id, space_id, dst_noext, first_frame=False):
    """Download + convert. Returns written path or None (caller may keep remote URL)."""
    if not src: return None
    url = signed_url(src, block_id, space_id) if notion_hosted(src) else src
    ext = os.path.splitext(name_of(src))[1].lower()
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "f")
        try:
            ctype = download(url, tmp)
        except Exception as e:
            print("   download failed:", src[:80], e); return None
        if ext not in IMG_EXT | {".gif", ".svg", ".mp4", ".mov", ".webm", ".m4v"}:
            ext = {"image/gif": ".gif", "image/svg+xml": ".svg", "video/mp4": ".mp4", "video/quicktime": ".mov",
                   "image/png": ".png", "image/webp": ".webp"}.get(ctype.split(";")[0], ".jpg")
        try:
            if ext == ".gif" and not first_frame and os.path.getsize(tmp) > 3_000_000:
                return convert(tmp, ".mp4", dst_noext)
            return convert(tmp, ext, dst_noext, first_frame)
        except Exception as e:
            print("   convert failed:", src[:80], e); return None
