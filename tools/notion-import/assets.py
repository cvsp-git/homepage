"""Convert one Notion asset into a web file. Returns (kind, ext) kind in img|video."""
import os, re, base64, io, hashlib, shutil, subprocess
from PIL import Image, ImageOps
import pillow_heif; pillow_heif.register_heif_opener()
Image.MAX_IMAGE_PIXELS = None
from PIL import ImageFile; ImageFile.LOAD_TRUNCATED_IMAGES = True
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache'); os.makedirs(CACHE, exist_ok=True)
MAXPX = 1600

def _save_jpg(im, dst):
    im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA'); bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3]); im = bg
    im = im.convert('RGB'); im.thumbnail((MAXPX, MAXPX), Image.LANCZOS)
    im.save(dst, 'JPEG', quality=82, optimize=True, progressive=True)

def _svg(src):
    t = open(src, encoding='utf-8', errors='replace').read()
    W, H = [float(x) for x in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', t).groups()]
    el = re.search(r'<image\b[^>]*>', t, re.S).group(0)
    data = re.search(r'href="data:image/[a-z+]+;base64,([^"]+)"', el, re.S).group(1)
    im = Image.open(io.BytesIO(base64.b64decode(re.sub(r'\s', '', data))))
    iw = float(re.search(r'\bwidth="([\d.]+)"', el).group(1))
    tm = re.search(r'matrix\(([-\d.e]+) 0 0 ([-\d.e]+) ([-\d.e]+) ([-\d.e]+)\)', t)
    if tm:  # pattern in objectBoundingBox units: image occupies iw*sx x ih*sy of the rect, offset tx,ty
        sx, sy, tx, ty = map(float, tm.groups())
        # rect pixel (u,v) <- image pixel ((u/W - tx)/sx, (v/H - ty)/sy)
        x0, y0 = (-tx) / sx, (-ty) / sy; x1, y1 = (1 - tx) / sx, (1 - ty) / sy
        k = im.size[0] / iw
        im = im.crop((round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k)))
    return im

def convert(src, dst_noext):
    """Writes dst_noext + ext. Returns (kind, path)."""
    ext = os.path.splitext(src)[1].lower()
    h = hashlib.sha1((src + str(os.path.getsize(src))).encode()).hexdigest()[:16]
    if ext == '.gif' and os.path.getsize(src) <= 3_000_000: kind, out = 'img', '.gif'
    elif ext in ('.gif', '.mp4', '.mov'): kind, out = 'video', '.mp4'
    else: kind, out = 'img', '.jpg'
    c = os.path.join(CACHE, h + out)
    if not os.path.exists(c):
        if out == '.gif':
            shutil.copy(src, c)
        elif out == '.mp4':
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-an' if ext == '.gif' else '-c:a', *([] if ext == '.gif' else ['aac']),
                            '-vf', "scale='min(1280,iw)':-2", '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '26', '-preset', 'medium',
                            '-movflags', '+faststart', c], check=True)
        elif ext == '.svg':
            tmp = c + '.png'; subprocess.run(['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'svg2png.js'), src, tmp], check=True)
            _save_jpg(Image.open(tmp), c); os.remove(tmp)
        else:
            _save_jpg(Image.open(src), c)
    shutil.copy(c, dst_noext + out)
    return kind, dst_noext + out
