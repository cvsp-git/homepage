"""산지니(또는 다른 캐릭터) PNG를 메인 화면용 입체 가우시안 데이터로 바꿉니다.

사용법:  python3 tools/make_mascot_points.py images/logo/sanjini.png [결과 파일]
결과:    tools/mascot-points.js (또는 지정한 파일)  (학습용 정답 점 구름. 다음에 train_mascot_gaussians.py 실행)
필요:    pip install pillow numpy scipy

평면 그림을 '부풀려' 앞면, 뒷면, 옆면이 있는 입체로 만듭니다.
가장자리에서 멀수록 두껍게 만들어서 머리와 몸통은 둥글고 날개 끝은 얇게 됩니다.
그림을 바꾸면 이 스크립트를 한 번 실행하세요.
"""
import base64, sys
import numpy as np
from PIL import Image
from scipy import ndimage

src = sys.argv[1] if len(sys.argv) > 1 else "images/logo/sanjini.png"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tools/mascot-points.js"
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
SANJINI = blue.sum() > 0.3 * mask.sum()
if SANJINI:
    body = np.median(rgb[blue], axis=0)
    yellow = (rgb[..., 0] > 190) & (rgb[..., 1] > 160) & (rgb[..., 2] < 140)
    feet = yellow & (np.arange(H)[:, None] > H * 0.75)  # only the feet show from behind, not the beak
    back = None
else:
    # friends: body = the most common colour (coarse 16-level bins); from behind, the face details
    # (eyes, cheeks, belly, very light or dark bits that differ from the body) become body colour,
    # everything else (tail, arms, leaf, outline) keeps its own colour
    q = (rgb[mask] // 16).astype(int); keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    top = np.bincount(keys).argmax()
    body = np.median(rgb[mask][keys == top], axis=0)
    lum0 = rgb.mean(-1); far = np.linalg.norm(rgb - body, axis=-1) > 60
    r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    inner = dist > 5                                     # leave the outline alone
    face = mask & inner & far & ((lum0 > 185) | (lum0 < 75)
                                 | ((r_ > 200) & (g_ < 190) & (b_ > 140))   # pink cheeks
                                 | ((r_ > 150) & (g_ < 110) & (b_ < 110)))  # red (glasses)
    # also any other blob that differs from the body and sits fully inside it (beak, cheeks): it is on the front only.
    # blobs that reach the outline (arms, tail, ears) keep their colour on the back
    lab, nl = ndimage.label(mask & (np.linalg.norm(rgb - body, axis=-1) > 30))
    if nl:
        touch = np.unique(lab[(lab > 0) & (dist <= 2.5)])
        enclosed = np.isin(lab, [i for i in range(1, nl + 1) if i not in set(touch.tolist())])
        face |= enclosed & mask
    face = ndimage.binary_dilation(face, iterations=3) & mask
    # fill the face with the nearest colour around it, so the back has no patches
    idx = ndimage.distance_transform_edt(face, return_distances=False, return_indices=True)
    back = rgb[idx[0], idx[1]]
    feet = np.zeros_like(mask)

# outline fringe pixels are half white (leftover from the removed background): paint them body blue
fringe = mask & ((alpha < 250) | ndimage.binary_erosion(mask, iterations=1) == False) & (rgb.mean(-1) > 150)
rgb[fringe] = body

# detail pixels (eyes, beak, outlines): sample them more densely
lum = rgb.mean(-1)
edge = (np.abs(ndimage.sobel(lum, 0)) + np.abs(ndimage.sobel(lum, 1))) > 90

pts = []
def add(x, y, z, c, f=1.0):
    c = np.clip(np.asarray(c) * f, 0, 255)
    pts.append((x, y, z, int(c[0]), int(c[1]), int(c[2])))

# the side wall: along the outline the surface rises steeply, so close the gap between the front and
# the back with a full wall up to the depth found a few pixels inward (otherwise the sides look hollow)
zwall = ndimage.maximum_filter(zpx, size=9) * mask
# the wall takes its colour from a few pixels inward (the outline itself is a dark line / light fringe)
inner_px = dist >= 4
_, (iy, ix) = ndimage.distance_transform_edt(~inner_px, return_indices=True)
cx = W / 2
for y in range(H):
    for x in range(W):
        if not mask[y, x]:
            continue
        X = (x - cx) * unit; Y = 0.1 + (H - y) * unit; Z = zpx[y, x] * unit
        bc = back[y, x] if back is not None else (rgb[y, x] if feet[y, x] else body)
        near_edge = dist[y, x] < 6          # steep part of the surface: sample every pixel there
        grid = y % 2 == 0 and x % 2 == 0
        if grid or edge[y, x] or near_edge:
            add(X, Y, Z, rgb[y, x], shade[y, x])
        if grid or near_edge:  # back side
            add(X, Y, -Z, bc, 0.7 * shade[y, x])
        if grid and zpx[y, x] > 3:
            # opaque inner layers just under each surface, so the face never shows through the back (and the back
            # never through the face) when the gaussians are a little sparse
            add(X, Y, 0.55 * Z, rgb[y, x], shade[y, x])
            add(X, Y, -0.55 * Z, bc, 0.7 * shade[y, x])
        if dist[y, x] < 1.5:  # side wall along the outline, about one pixel apart in depth
            zw = max(zwall[y, x], zpx[y, x])
            k = max(2, int(np.ceil(2 * zw / 1.2)))
            for t in np.linspace(-1, 1, k + 1)[1:-1]:
                yy, xx = iy[y, x], ix[y, x]
                wb = back[yy, xx] if back is not None else (rgb[y, x] if feet[y, x] else body)
                add(X, Y, zw * t * unit, rgb[yy, xx] if t > 0 else wb, 0.82 if t > 0 else 0.72)

arr = np.array(pts, dtype=np.float64)
xyz = np.round(arr[:, :3] * 10000).astype("<i2")
col = arr[:, 3:].astype(np.uint8)
blob = np.concatenate([xyz.view(np.uint8).reshape(-1, 6), col], axis=1).tobytes()
with open(OUT, "w") as f:
    f.write("/* generated by tools/make_mascot_points.py from %s. Each point: int16 x,y,z (x1e-4) + rgb */\n" % src)
    f.write('window.CVSP_MASCOT = {n: %d, data: "%s"};\n' % (len(pts), base64.b64encode(blob).decode()))
print("points", len(pts), "bytes", len(blob))
