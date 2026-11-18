"""산지니(또는 다른 캐릭터) PNG를 메인 화면용 입체 가우시안 데이터로 바꿉니다.

사용법:  python3 tools/make_mascot_data.py images/logo/sanjini.png
결과:    assets/js/mascot-data.js
필요:    pip install pillow numpy scipy

평면 그림을 '부풀려' 앞면, 뒷면, 옆면이 있는 입체로 만들고,
표면을 방향과 크기가 다른 타원체(가우시안)들로 덮습니다.
가장자리에서 멀수록 두껍게 만들어서 머리와 몸통은 둥글고 날개 끝은 얇게 됩니다.
그림을 바꾸면 이 스크립트를 한 번 실행하세요.
"""
import base64, sys
import numpy as np
from PIL import Image
from scipy import ndimage

src = sys.argv[1] if len(sys.argv) > 1 else "images/logo/sanjini.png"
TARGET_H = 180           # 샘플링 해상도 (세로 픽셀)
HEIGHT = 0.8             # 화면 속 키 (main.js 좌표 단위)
FLAT = 0.8              # 1이면 공처럼, 작을수록 납작

im = Image.open(src).convert("RGBA")
w = round(im.width / im.height * TARGET_H)
im = im.resize((w, TARGET_H), Image.LANCZOS)
a = np.asarray(im).astype(np.float32)
rgb, alpha = a[..., :3], a[..., 3]
mask = alpha > 128
H, W = mask.shape
unit = HEIGHT / H

# depth from distance to the silhouette edge (circular profile = "inflated" look)
dist = ndimage.distance_transform_edt(mask)
dist = ndimage.gaussian_filter(dist, 1.2) * mask
R = dist.max()
zpx = FLAT * np.sqrt(np.clip(2 * R * dist - dist ** 2, 0, None))
zpx = ndimage.gaussian_filter(zpx, 2.0) * mask

# soft shading from the depth map normal (light from front-top-left)
gy, gx = np.gradient(zpx)
n = np.stack([-gx, -gy, np.ones_like(zpx)], -1)
n /= np.linalg.norm(n, axis=-1, keepdims=True)
L = np.array([-0.35, -0.45, 0.82]); L /= np.linalg.norm(L)
shade = np.clip(0.72 + 0.38 * (n @ L), 0.55, 1.12)

# body color for the back side: most common saturated blue in the picture
blue = (rgb[..., 2] > rgb[..., 0] + 40) & mask
body = np.median(rgb[blue], axis=0) if blue.any() else np.array([60, 120, 200])
yellow = (rgb[..., 0] > 190) & (rgb[..., 1] > 160) & (rgb[..., 2] < 140)
feet = yellow & (np.arange(H)[:, None] > H * 0.75)  # only the feet show from behind, not the beak

# outline fringe pixels are half white (leftover from the removed background): paint them body blue
fringe = mask & ((alpha < 250) | ndimage.binary_erosion(mask, iterations=1) == False) & (rgb.mean(-1) > 150)
rgb[fringe] = body

# detail pixels (eyes, beak, outlines): sample them more densely
lum = rgb.mean(-1)
edge = (np.abs(ndimage.sobel(lum, 0)) + np.abs(ndimage.sobel(lum, 1))) > 90

# ---- anisotropic gaussians -------------------------------------------------
# Each gaussian is a flat ellipsoid lying on the surface: two axes (long, short)
# in the tangent plane. Flat colour areas get a few large ellipses, details
# (eyes, beak, outlines) get many small ones that follow the edge direction.
rng = np.random.default_rng(7)

# direction of least colour change (structure tensor) = along edges
lum_s = ndimage.gaussian_filter(lum, 1.0)
ix, iy = ndimage.sobel(lum_s, 1), ndimage.sobel(lum_s, 0)
jxx = ndimage.gaussian_filter(ix * ix, 2.0); jyy = ndimage.gaussian_filter(iy * iy, 2.0); jxy = ndimage.gaussian_filter(ix * iy, 2.0)
edge_ang = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2          # perpendicular to the gradient
coher = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-6)
# in flat areas follow the silhouette (parallel to the outline)
dy_, dx_ = np.gradient(ndimage.gaussian_filter(dist, 2.0))
out_ang = np.arctan2(dy_, dx_) + np.pi / 2
strong = (jxx + jyy) > 3000
ang = np.where(strong & (coher > 0.3), edge_ang, out_ang)
near = ndimage.binary_dilation(edge, iterations=3)

AX = 3000.0  # axis vectors stored as int8 / AX
pts = []
def tangent_axes(x, y, a_img, long_, short_, back=False):
    gx_, gy_ = gx[y, x], gy[y, x]
    nrm = np.array([-gx_, gy_, 1.0]); nrm /= np.linalg.norm(nrm)
    d = np.array([np.cos(a_img), -np.sin(a_img), 0.0])
    t1 = d - d.dot(nrm) * nrm; t1 /= np.linalg.norm(t1) + 1e-9
    t2 = np.cross(nrm, t1)
    t1, t2 = t1 * long_, t2 * short_
    if back:
        t1 = t1 * [1, 1, -1]; t2 = t2 * [1, 1, -1]
    return t1, t2

def add(X, Y, Z, c, f, t1, t2):
    c = np.clip(np.asarray(c) * f, 0, 255)
    pts.append((X, Y, Z, int(c[0]), int(c[1]), int(c[2]), *t1, *t2))

cx = W / 2
for y in range(H):
    for x in range(W):
        if not mask[y, x]:
            continue
        X = (x - cx) * unit; Y = 0.1 + (H - y) * unit; Z = zpx[y, x] * unit
        if edge[y, x]:
            size = 1.4 if (x % 2 == 0 and y % 2 == 0) else 0
        elif near[y, x]:
            size = 2.5 if (x % 3 == 0 and y % 3 == 0) else 0
        else:
            size = 6 if (x % 5 == 0 and y % 5 == 0) else 0
        if size:
            jx = rng.uniform(-.5, .5) * size * 0.6; jy = rng.uniform(-.5, .5) * size * 0.6
            # blobs: moderate elongation, loosely oriented (fine details still follow the edge)
            a_img = ang[y, x] + (rng.normal(0, 0.15) if size < 2 else rng.uniform(-0.9, 0.9))
            L = size * unit * rng.uniform(0.9, 1.5); S = L * rng.uniform(0.4, 0.75)
            t1, t2 = tangent_axes(x, y, a_img, L, S)
            c = rgb[y, x] if (dist[y, x] >= 2 or feet[y, x]) else body  # rim: no light halo
            # slight per-gaussian brightness variation so individual ellipses read
            add(X + jx * unit, Y - jy * unit, Z, c, shade[y, x] * (rng.uniform(0.88, 1.12) if size > 2 else 1.0), t1, t2)
        if x % 5 == 2 and y % 5 == 2:  # back side: large body-blue ellipses
            a_img = rng.uniform(0, np.pi)
            Lb = 6 * unit * rng.uniform(0.9, 1.5)
            t1, t2 = tangent_axes(x, y, a_img, Lb, Lb * rng.uniform(0.4, 0.75), back=True)
            add(X, Y, -Z, rgb[y, x] if feet[y, x] else body, 0.7 * shade[y, x], t1, t2)
        if dist[y, x] < 1.5 and (x + y) % 4 == 0:  # side wall: ellipses stretched front-to-back
            a_img = out_ang[y, x]
            tw = np.array([np.cos(a_img), -np.sin(a_img), 0.0]) * unit * 2.2
            for t in (-0.5, 0.0, 0.5):
                tz = np.array([0, 0, max(abs(Z) * 0.32, unit)])
                add(X, Y, Z * t, rgb[y, x] if feet[y, x] else body, 0.75, tw, tz)

arr = np.array(pts, dtype=np.float64)
xyz = np.round(arr[:, :3] * 10000).astype("<i2")
col = arr[:, 3:6].astype(np.uint8)
axes = np.clip(np.round(arr[:, 6:12] * AX), -127, 127).astype(np.int8)
blob = np.concatenate([xyz.view(np.uint8).reshape(-1, 6), col, axes.view(np.uint8)], axis=1).tobytes()
with open("assets/js/mascot-data.js", "w") as f:
    f.write("/* generated by tools/make_mascot_data.py from %s. Each gaussian (15 bytes): int16 x,y,z (x1e-4), rgb, int8 axis1 xyz, int8 axis2 xyz (/%d) */\n" % (src, AX))
    f.write('window.CVSP_MASCOT = {n: %d, stride: 15, ax: %d, data: "%s"};\n' % (len(pts), AX, base64.b64encode(blob).decode()))
print("points", len(pts), "bytes", len(blob))
