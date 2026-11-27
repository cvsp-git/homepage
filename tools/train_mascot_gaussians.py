"""산지니 3D 가우시안 학습 (3D Gaussian Splatting 방식).

정답(GT): 처음 버전의 '동그란 점' 산지니(assets/js/mascot-data.js 의 옛 형식, 점 약 1만 2천 개)를
여러 각도에서 렌더링한 이미지들. 이 이미지들과 똑같이 보이도록 타원체 가우시안의
위치, 크기(3축), 회전, 색, 투명도를 경사하강법으로 학습합니다.

사용법:
    pip install torch numpy pillow
    python3 tools/train_mascot_gaussians.py <옛 형식 mascot-data.js> [가우시안 개수=5000]
결과:  assets/js/mascot-data.js  (fmt: "gs3")

학습은 한 번만 미리 돌리는 것이고, 홈페이지 방문자는 결과만 그립니다.
"""
import base64, math, re, sys, time
import numpy as np
import torch

torch.manual_seed(0); np.random.seed(0)
torch.set_num_threads(4)
SRC = sys.argv[1]
N_OUT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
ITERS = int(sys.argv[3]) if len(sys.argv) > 3 else 2500
OUT = sys.argv[4] if len(sys.argv) > 4 else "assets/js/mascot-data.js"
VAR = sys.argv[5] if len(sys.argv) > 5 else "CVSP_MASCOT"   # friends: CVSP_FRIEND_<name>

# ---------------------------------------------------------------- GT cloud
txt = open(SRC).read()
n = int(re.search(r"n:\s*(\d+)", txt).group(1))
raw = base64.b64decode(re.search(r'data:\s*"([^"]+)"', txt).group(1))
a = np.frombuffer(raw, dtype=np.uint8).reshape(n, 9)
xyz = a[:, :6].copy().view("<i2").astype(np.float32) / 10000
xyz[:, 2] *= -1                       # same flip as main.js: +z is away from the camera
rgb = a[:, 6:9].astype(np.float32) / 255
# the old cloud has a light seam where front and back meet (left-over white fringe): paint it body blue
body = np.median(rgb[(rgb[:, 2] > rgb[:, 0] + 0.15)], axis=0)
yellow = (rgb[:, 0] > .75) & (rgb[:, 1] > .6) & (rgb[:, 2] < .55)
rim = (np.abs(xyz[:, 2]) < 0.045) & (rgb.mean(1) > body.mean() + 0.12) & ~yellow
rgb[rim] = body * 0.85
P = torch.tensor(xyz); C = torch.tensor(rgb)
import os
RES = float(os.environ.get("RES", "1"))        # training resolution multiplier (2 = sharper, ~4x slower)
GT_R = 9 / 640 / float(os.environ.get("GT_SHARP", "1"))   # world radius of one GT splat (smaller = crisper edges; cloud spacing is ~0.0047)

# ---------------------------------------------------------------- camera (same math as main.js)
IMG_W, IMG_H, F = int(128 * RES), int(160 * RES), 150.0 * RES     # RES=1: ~ the on-screen size at devicePixelRatio 1.3
def view_mats(yaw, pitch):
    cy_, sy_, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    # X = x cy - z sy ; Zt = x sy + z cy ; Y = y cp - Zt sp ; Z2 = y sp + Zt cp
    return torch.tensor([[cy_, 0, -sy_], [-sy_ * sp, cp, -cy_ * sp], [sy_ * cp, sp, cy_ * cp]], dtype=torch.float32)

def project(means, V, off):
    v = means @ V.T
    k = 2.6 / (2.6 + v[:, 2])
    u = IMG_W / 2 + v[:, 0] * F * k - off[0]
    w = IMG_H / 2 - v[:, 1] * F * k - off[1]
    return v, k, torch.stack([u, w], 1)

views = []
for i in range(72):
    yaw = (i / 72) * 2 * math.pi + np.random.uniform(-0.04, 0.04)
    pitch = float(np.random.uniform(-0.15, 1.1)) if i % 4 else 0.2
    V = view_mats(yaw, pitch)
    v, k, uv = project(P, V, (0.0, 0.0))
    off = (uv.mean(0) - torch.tensor([IMG_W / 2, IMG_H / 2])).tolist()
    views.append((V, off))

ys, xs = torch.meshgrid(torch.arange(IMG_H, dtype=torch.float32) + .5, torch.arange(IMG_W, dtype=torch.float32) + .5, indexing="ij")
TILE = 16
tiles = [(ty, tx) for ty in range(0, IMG_H, TILE) for tx in range(0, IMG_W, TILE)]

def composite(uv, depth, inv_cov, opac, col, radius, profile):
    """front-to-back alpha compositing, tile by tile (only gaussians touching a tile)."""
    order = torch.argsort(depth)
    uv, inv_cov, opac, col, radius = uv[order], inv_cov[order], opac[order], col[order], radius[order]
    out = torch.zeros(IMG_H, IMG_W, 4)
    rows = []
    for ty in range(0, IMG_H, TILE):
        row = []
        for tx in range(0, IMG_W, TILE):
            m = (uv[:, 0] + radius > tx) & (uv[:, 0] - radius < tx + TILE) & (uv[:, 1] + radius > ty) & (uv[:, 1] - radius < ty + TILE)
            idx = m.nonzero().squeeze(1)
            if idx.numel() == 0:
                row.append(torch.zeros(TILE, TILE, 4)); continue
            px = torch.stack([xs[ty:ty + TILE, tx:tx + TILE].reshape(-1), ys[ty:ty + TILE, tx:tx + TILE].reshape(-1)], 1)
            d = px[None] - uv[idx][:, None]                                   # n,p,2
            ic = inv_cov[idx]
            q = ic[:, None, 0] * d[..., 0] ** 2 + 2 * ic[:, None, 1] * d[..., 0] * d[..., 1] + ic[:, None, 2] * d[..., 1] ** 2
            al = (opac[idx][:, None] * profile(q)).clamp(max=0.99)
            T = torch.cumprod(torch.cat([torch.ones(1, al.shape[1]), 1 - al[:-1]], 0), 0)
            wgt = al * T
            c = wgt.T @ col[idx]
            acc = wgt.sum(0, keepdim=True).T
            row.append(torch.cat([c, acc], 1).reshape(TILE, TILE, 4))
        rows.append(torch.cat(row, 1))
    return torch.cat(rows, 0)

def old_profile(q):  # radial falloff of the old sprite: 1 at 0, .85 at .45, 0 at 1 (q = r^2/R^2)
    r = q.clamp(min=0).sqrt()
    return torch.where(r < .45, 1 - r / .45 * .15, (.85 * (1 - (r - .45) / .55)).clamp(min=0))

def render_gt(V, off):
    v, k, uv = project(P, V, off)
    rpx = GT_R * F * k
    inv = torch.stack([1 / rpx ** 2, torch.zeros_like(rpx), 1 / rpx ** 2], 1)
    return composite(uv, v[:, 2], inv, torch.full_like(rpx, .95), C, rpx, old_profile)

print("rendering GT", len(views), "views"); t0 = time.time()
with torch.no_grad():
    GT = [render_gt(V, off) for V, off in views]
print("GT done %.1fs" % (time.time() - t0))

# ---------------------------------------------------------------- gaussians
def quat_to_R(q):
    q = q / q.norm(dim=1, keepdim=True)
    w, x, y, z = q.unbind(1)
    return torch.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y),
                        2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x),
                        2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], 1).reshape(-1, 3, 3)

init = torch.randperm(n)[:7000]
params = {
    "mean": P[init].clone() + torch.randn(len(init), 3) * 0.002,
    "lscale": torch.full((len(init), 3), math.log(0.009)),
    "quat": torch.cat([torch.ones(len(init), 1), torch.zeros(len(init), 3)], 1) + torch.randn(len(init), 4) * 0.1,
    "col": torch.logit(C[init].clamp(.02, .98)),
    "lop": torch.full((len(init),), 1.5),
}
for p_ in params.values(): p_.requires_grad_(True)
LR = {"mean": 6e-4, "lscale": 8e-3, "quat": 4e-3, "col": 2e-2, "lop": 4e-2}
def make_opt():
    return torch.optim.Adam([{"params": [params[k_]], "lr": LR[k_], "name": k_} for k_ in params], eps=1e-15)
opt = make_opt()

def gauss_profile(q):
    return torch.exp(-0.5 * q)

def render(V, off):
    mean = params["mean"]
    v, k, uv = project(mean, V, off)
    R = quat_to_R(params["quat"]); S = torch.exp(params["lscale"]).clamp(max=0.06)
    M = R * S[:, None, :]                                   # columns = axis vectors (world)
    Mv = V[None] @ M                                        # view space
    # jacobian of the perspective projection (pixels per view unit)
    z = 2.6 + v[:, 2]
    J = torch.zeros(len(mean), 2, 3)
    J[:, 0, 0] = F * k; J[:, 0, 2] = -F * v[:, 0] * k / z
    J[:, 1, 1] = -F * k; J[:, 1, 2] = F * v[:, 1] * k / z
    U = J @ Mv
    cov = U @ U.transpose(1, 2) + 0.3 * torch.eye(2)[None]
    a_, b_, c_ = cov[:, 0, 0], cov[:, 0, 1], cov[:, 1, 1]
    det = a_ * c_ - b_ * b_
    inv = torch.stack([c_ / det, -b_ / det, a_ / det], 1)
    radius = 3 * torch.sqrt(torch.maximum(a_, c_)).detach()
    return composite(uv, v[:, 2], inv, torch.sigmoid(params["lop"]), torch.sigmoid(params["col"]), radius, gauss_profile)

def prune(keep):
    global opt
    for k_ in params:
        params[k_] = params[k_].detach()[keep].clone().requires_grad_(True)
    opt = make_opt()

def densify(grad_acc, cnt):
    """3DGS-style: split gaussians whose position gradient is large (under-fitted detail)."""
    global opt
    g = grad_acc / cnt.clamp(min=1)
    thr = torch.quantile(g, 0.85)
    sel = g > thr
    with torch.no_grad():
        S = torch.exp(params["lscale"][sel])
        R = quat_to_R(params["quat"][sel])
        samp = (R @ (torch.randn(int(sel.sum()), 3, 1) * S[..., None])).squeeze(-1)
        new = {"mean": params["mean"][sel] + samp, "lscale": params["lscale"][sel] - math.log(1.6),
               "quat": params["quat"][sel], "col": params["col"][sel], "lop": params["lop"][sel]}
        params["lscale"][sel] -= math.log(1.6)
    for k_ in params:
        params[k_] = torch.cat([params[k_].detach(), new[k_]], 0).requires_grad_(True)
    opt = make_opt()

grad_acc = torch.zeros(len(params["mean"])); cnt = torch.zeros(len(params["mean"]))
t0 = time.time()
for it in range(1, ITERS + 1):
    vi = np.random.randint(len(views)); V, off = views[vi]
    img = render(V, off)
    gt = GT[vi]
    loss = (img - gt).abs().mean() + 0.5 * ((img - gt) ** 2).mean()
    opt.zero_grad(); loss.backward()
    with torch.no_grad():
        gm = params["mean"].grad.norm(dim=1)
        grad_acc += gm; cnt += (gm > 0).float()
    opt.step()
    for g_ in opt.param_groups:
        if g_["name"] == "mean": g_["lr"] = LR["mean"] * (0.02 ** (it / ITERS))
    if it % 100 == 0:
        print("it %d loss %.4f n %d  %.1fs" % (it, loss.item(), len(params["mean"]), time.time() - t0), flush=True)
    if it in (400, 800, 1200):
        densify(grad_acc, cnt)
        keep = torch.sigmoid(params["lop"]).detach() > 0.02
        prune(keep)
        grad_acc = torch.zeros(len(params["mean"])); cnt = torch.zeros(len(params["mean"]))
    if it == 1600 or it == ITERS:
        # keep the most useful gaussians (opacity x size), up to N_OUT
        with torch.no_grad():
            # rank by opacity: keeps small opaque detail (eyes, mouths); faint wide gaussians (edge haze) go first
            imp = torch.sigmoid(params["lop"]) * (torch.exp(params["lscale"]).prod(1) ** (1 / 3)) ** float(os.environ.get("IMP_SIZE_POW", "1"))
        keep = torch.zeros(len(imp), dtype=torch.bool)
        keep[torch.argsort(imp, descending=True)[:N_OUT]] = True
        keep &= torch.sigmoid(params["lop"]).detach() > 0.03
        prune(keep)
        grad_acc = torch.zeros(len(params["mean"])); cnt = torch.zeros(len(params["mean"]))

# ---------------------------------------------------------------- report + export
with torch.no_grad():
    errs = [((render(V, off) - GT[i]).abs().mean().item()) for i, (V, off) in enumerate(views[::9])]
    print("final mean L1 over sample views: %.4f  gaussians: %d" % (np.mean(errs), len(params["mean"])))
    from PIL import Image
    for j, i in enumerate((0, 18, 36)):
        V, off = views[i]
        both = torch.cat([GT[i], render(V, off)], 1)[..., :3].clamp(0, 1).numpy()
        Image.fromarray((both * 255).astype(np.uint8)).resize((512, 320), Image.NEAREST).save(OUT + ".cmp%d.png" % j)

    mean = params["mean"].numpy()
    S = torch.exp(params["lscale"]).clamp(max=0.06).numpy()
    q = params["quat"]; q = (q / q.norm(dim=1, keepdim=True)).numpy()
    q[q[:, 0] < 0] *= -1
    col = (torch.sigmoid(params["col"]).numpy() * 255).round().astype(np.uint8)
    op = (torch.sigmoid(params["lop"]).numpy() * 255).round().astype(np.uint8)
    # log-scale stored as uint8: s = exp(LMIN + b/255*(LMAX-LMIN))
    LMIN, LMAX = math.log(2e-4), math.log(0.06)
    sb = np.clip(np.round((np.log(np.clip(S, 2e-4, 0.06)) - LMIN) / (LMAX - LMIN) * 255), 0, 255).astype(np.uint8)
    qb = np.clip(np.round(q * 127), -127, 127).astype(np.int8)
    xyzb = np.round(mean * 10000).astype("<i2")
    blob = np.concatenate([xyzb.view(np.uint8).reshape(-1, 6), col, op[:, None], sb, qb.view(np.uint8)], 1).tobytes()
    with open(OUT, "w") as f:
        f.write("/* generated by tools/train_mascot_gaussians.py: trained 3D gaussians. Each (17 bytes): int16 x,y,z (x1e-4, view-ready, +z away), rgb, opacity, "
                "log-scale x3 (uint8, %.4f..%.4f), quaternion wxyz (int8/127) */\n" % (LMIN, LMAX))
        f.write('window.%s = {n: %d, fmt: "gs3", lmin: %.6f, lmax: %.6f, data: "%s"};\n' % (VAR, len(mean), LMIN, LMAX, base64.b64encode(blob).decode()))
    print("wrote", len(mean), "gaussians,", len(blob), "bytes")
