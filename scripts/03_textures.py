"""段階3a: 柄テクスチャを numpy で描いて textures/ に保存し、Blender 画像として読み込む。
Blender 内で exec する。配列は行0=画像の下端（Blender のピクセル順）。"""
import bpy, os, math
import numpy as np

ROOT = os.path.dirname(bpy.data.filepath)
TEX = os.path.join(ROOT, "textures")
os.makedirs(TEX, exist_ok=True)
rng = np.random.default_rng(3)


def C(*rgb):
    return np.array(rgb, dtype=np.float32)


def canvas(w, h, col):
    a = np.zeros((h, w, 3), np.float32)
    a[:] = col
    return a


def grid(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return x / w, y / h  # 0..1、y は下から上


def smooth_noise(w, h, cells, seed=0):
    r = np.random.default_rng(seed)
    g = r.random((cells[1] + 3, cells[0] + 3)).astype(np.float32)
    x, y = grid(w, h)
    gx = x * cells[0] + 1
    gy = y * cells[1] + 1
    x0 = np.floor(gx).astype(int)
    y0 = np.floor(gy).astype(int)
    fx = gx - x0
    fy = gy - y0
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = g[y0, x0] * (1 - fx) + g[y0, x0 + 1] * fx
    b = g[y0 + 1, x0] * (1 - fx) + g[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def fbm(w, h, base, octaves=4, seed=0):
    out = np.zeros((h, w), np.float32)
    amp = 1.0
    tot = 0
    for o in range(octaves):
        out += amp * smooth_noise(w, h, (base[0] * 2 ** o, base[1] * 2 ** o), seed + o)
        tot += amp
        amp *= 0.5
    return out / tot


def paint(a, mask, col, alpha=1.0):
    m = np.clip(mask, 0, 1)[..., None] * alpha
    a[:] = a * (1 - m) + col * m


def aa(d, px):
    """符号付き距離(内側が負) → 0..1 のマスク"""
    return np.clip(0.5 - d / px, 0, 1)


def save(name, a):
    h, w, _ = a.shape
    img = bpy.data.images.get(name)
    if img and (img.size[0] != w or img.size[1] != h):
        bpy.data.images.remove(img)
        img = None
    if not img:
        img = bpy.data.images.new(name, w, h, alpha=False)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.clip(a, 0, 1)  # バイト画像は sRGB のまま書き込む
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(TEX, name + ".png")
    img.file_format = 'PNG'
    img.save()
    img.colorspace_settings.name = 'sRGB'
    img.reload()
    return img


# ---------------- ラグ (2.8m x 3.8m) ----------------
def rug():
    w, h = 1120, 1520
    x, y = grid(w, h)
    X = x * 2.8
    Y = y * 3.8  # メートル
    cream = C(0.80, 0.72, 0.58)
    a = canvas(w, h, cream)
    rust = C(0.62, 0.27, 0.13)
    olive = C(0.27, 0.27, 0.17)
    char = C(0.22, 0.18, 0.14)
    sand = C(0.70, 0.58, 0.42)
    px = 2.8 / w
    # 横縞
    for y0, t, col in [(0.55, 0.05, char), (0.70, 0.02, char), (1.62, 0.12, sand), (2.35, 0.03, char), (2.45, 0.03, char), (3.05, 0.10, sand)]:
        paint(a, aa(np.abs(Y - y0) - t / 2, px), col)
    # 大きな半円: 錆色(平らな辺が上)と暗いオリーブ(平らな辺が下)
    d = np.sqrt((X - 0.95) ** 2 + (Y - 1.55) ** 2) - 0.75
    paint(a, aa(np.maximum(d, Y - 1.55), px), rust)
    d = np.sqrt((X - 2.15) ** 2 + (Y - 0.30) ** 2) - 0.62
    paint(a, aa(np.maximum(d, 0.30 - Y), px), olive)
    d = np.sqrt((X - 1.70) ** 2 + (Y - 2.95) ** 2) - 0.45
    paint(a, aa(np.maximum(d, Y - 2.95), px), rust * 0.85 + sand * 0.15)
    # 矩形ブロック
    paint(a, aa(np.maximum(np.abs(X - 2.25) - 0.40, np.abs(Y - 1.95) - 0.22), px), olive)
    paint(a, aa(np.maximum(np.abs(X - 0.55) - 0.30, np.abs(Y - 2.85) - 0.18), px), sand * 0.8)
    # 縁取り
    edge = np.minimum.reduce([X, 2.8 - X, Y, 3.8 - Y])
    paint(a, aa(edge - 0.06, px) * (1 - aa(edge - 0.035, px)), char, 0.8)
    # ウールのむら
    n = fbm(w, h, (28, 38), 4, 5)
    a *= (0.93 + 0.12 * n)[..., None]
    mid = fbm(w, h, (140, 190), 2, 13)
    a *= (0.90 + 0.18 * mid)[..., None]
    fine = rng.random((h, w)).astype(np.float32)
    a *= (0.92 + 0.10 * fine)[..., None]
    gray = a.mean(2, keepdims=True)
    a[:] = a * 0.85 + gray * 0.15
    save("tex_rug", a)
    # 毛足のバンプ用
    hb = np.repeat((0.2 * n + 0.4 * mid + 0.4 * fine)[..., None], 3, 2)
    img = save("tex_rug_bump", hb)
    img.colorspace_settings.name = 'Non-Color'


# ---------------- 左壁ポスター: 縦線と大きな円 ----------------
def poster_circle():
    w, h = 620, 900
    x, y = grid(w, h)
    a = canvas(w, h, C(0.86, 0.80, 0.68))
    px = 1 / w
    lines = (np.abs(((x * 38) % 1) - 0.5) < 0.07) & (x < 0.62) & (y > 0.08)
    paint(a, lines.astype(np.float32), C(0.35, 0.30, 0.25), 0.8)
    d = np.sqrt((x - 0.60) ** 2 + ((y - 0.66) * h / w) ** 2) - 0.30
    paint(a, aa(d, px), C(0.58, 0.20, 0.10))
    paint(a, aa(np.maximum(np.abs(x - 0.62) - 0.30, np.abs(y - 0.20) - 0.12), px), C(0.30, 0.33, 0.22))
    a *= (0.95 + 0.05 * fbm(w, h, (8, 12), 3, 9))[..., None]
    save("tex_poster_circle", a)


# ---------------- 奥壁ポスター: 積み重なる丸い形 ----------------
def poster_shapes():
    w, h = 620, 1000
    x, y = grid(w, h)
    Y = y * h / w
    a = canvas(w, h, C(0.88, 0.82, 0.70))
    px = 1 / w
    ochre = C(0.72, 0.48, 0.22)
    rust = C(0.55, 0.22, 0.11)
    dark = C(0.10, 0.10, 0.09)
    olive = C(0.32, 0.33, 0.22)
    paint(a, aa(np.maximum(np.abs(x - 0.40) - 0.32, np.abs(Y - 1.10) - 0.36), px), ochre)
    paint(a, aa(np.maximum(np.abs(x - 0.62) - 0.30, np.abs(Y - 0.58) - 0.28), px), rust)
    # 上: 黒いアーチ
    d = np.sqrt((x - 0.50) ** 2 + (Y - 1.30) ** 2) - 0.26
    paint(a, aa(np.maximum(d, 1.30 - Y), px), dark)
    paint(a, aa(np.maximum(np.abs(x - 0.50) - 0.26, np.abs(Y - 1.24) - 0.06), px), dark)
    # 中: 黒い楕円
    d = np.sqrt(((x - 0.47) / 1.25) ** 2 + (Y - 0.92) ** 2) - 0.13
    paint(a, aa(d, px), dark)
    # 下: 黒いアーチ
    d = np.sqrt((x - 0.50) ** 2 + (Y - 0.30) ** 2) - 0.27
    paint(a, aa(np.maximum(d, 0.30 - Y), px), dark)
    paint(a, aa(np.maximum(np.abs(x - 0.50) - 0.27, np.abs(Y - 0.20) - 0.10), px), olive)
    a *= (0.95 + 0.05 * fbm(w, h, (8, 12), 3, 11))[..., None]
    save("tex_poster_shapes", a)


# ---------------- 写真: 空・建物・木 ----------------
def scene_photo(name, w, h, seed, night=False):
    r = np.random.default_rng(seed)
    x, y = grid(w, h)
    top = C(*r.uniform([0.35, 0.45, 0.6], [0.6, 0.7, 0.85])) if not night else C(0.05, 0.07, 0.15)
    bot = C(*r.uniform([0.75, 0.65, 0.55], [0.95, 0.85, 0.7])) if not night else C(0.15, 0.13, 0.2)
    a = top * y[..., None] + bot * (1 - y[..., None])
    px = 1 / w
    stone = C(*r.uniform([0.35, 0.28, 0.22], [0.6, 0.45, 0.35]))
    # 建物
    cx = r.uniform(0.3, 0.7)
    bw = r.uniform(0.25, 0.45)
    bh = r.uniform(0.35, 0.55)
    body = np.maximum(np.abs(x - cx) - bw / 2, y - bh)
    paint(a, aa(body, px), stone)
    # 塔と尖塔
    tx = cx + r.uniform(-0.15, 0.15)
    th = bh + r.uniform(0.12, 0.25)
    paint(a, aa(np.maximum(np.abs(x - tx) - 0.05, y - th), px), stone * 0.9)
    spire = np.maximum(y - (th + 0.15 - np.abs(x - tx) * 3.0), th - y - 0.01)
    paint(a, aa(spire, px), stone * 0.8)
    # 窓
    win = (np.abs(((x - cx) * 14) % 1 - 0.5) < 0.18) & (np.abs((y * 12) % 1 - 0.5) < 0.22) & (body < -0.01) & (y > 0.12)
    paint(a, win.astype(np.float32), C(0.95, 0.8, 0.5) if night else stone * 0.45, 0.9)
    # 木と地面
    for k in range(5):
        tcx = r.uniform(0, 1)
        d = np.sqrt((x - tcx) ** 2 + ((y - r.uniform(0.12, 0.25)) * 1.3) ** 2) - r.uniform(0.08, 0.15)
        paint(a, aa(d, px), C(*r.uniform([0.1, 0.18, 0.06], [0.3, 0.35, 0.12])))
    paint(a, aa(y - 0.1, px), C(0.25, 0.3, 0.15))
    a *= (0.92 + 0.08 * fbm(w, h, (6, 6), 3, seed))[..., None]
    # 白い縁
    edge = np.minimum.reduce([x, 1 - x, y, 1 - y])
    paint(a, (edge < 0.05).astype(np.float32), C(0.92, 0.9, 0.86))
    save(name, a)


# ---------------- モニターの壁紙 ----------------
def wallpaper():
    w, h = 1600, 900
    x, y = grid(w, h)
    a = canvas(w, h, C(0.20, 0.33, 0.42))
    layers = [(0.80, C(0.33, 0.48, 0.55), 0.10, 1.2, 0.0), (0.62, C(0.85, 0.80, 0.72), 0.14, 0.9, 1.4),
              (0.50, C(0.55, 0.60, 0.62), 0.12, 1.5, 2.2), (0.36, C(0.62, 0.45, 0.32), 0.16, 0.8, 0.6),
              (0.22, C(0.40, 0.30, 0.24), 0.10, 1.3, 3.0)]
    for base, col, amp, f, ph in layers:
        curve = base + amp * np.sin(x * math.pi * 2 * f + ph) * (0.6 + 0.4 * np.cos(x * 3 + ph))
        paint(a, aa((y - curve) * h, 1.5), col)
    save("tex_wallpaper", a)


# ---------------- 窓の外: 夜のキャンパス ----------------
def night_campus():
    w, h = 3000, 1500
    x, y = grid(w, h)
    X = x * 2.0
    a = (C(0.03, 0.05, 0.13) * y[..., None] + C(0.13, 0.15, 0.27) * (1 - y[..., None]))
    px = 1 / w
    stone = C(0.20, 0.11, 0.08)
    r = np.random.default_rng(8)
    # 遠景の丘
    hill = 0.42 + 0.05 * np.sin(X * 3.1) + 0.03 * fbm(w, h, (6, 1), 3, 2)
    paint(a, aa((y - hill) * h, 2), C(0.07, 0.08, 0.11))
    bodies = []
    # ゴシック風の建物群 (x0, x1, 高さ)
    for x0, x1, top in [(0.15, 0.75, 0.62), (0.70, 1.05, 0.55), (1.05, 1.60, 0.66), (1.60, 1.95, 0.52)]:
        body = np.maximum(np.maximum(x0 - X, X - x1) * w / 2, (y - top) * h)
        roof = np.maximum(np.maximum(x0 - X, X - x1) * w / 2, (y - (top + 0.06 - np.abs(X - (x0 + x1) / 2) * 0.3)) * h)
        paint(a, aa(np.minimum(body, roof), 1.5), stone)
        bodies.append((x0, x1, top))
        # 窓明かり
        cols = int((x1 - x0) / 0.022)
        rows = int((top - 0.25) / 0.045)
        for i in range(cols):
            for j in range(rows):
                if r.random() < 0.28:
                    wx = x0 + 0.012 + i * 0.022
                    wy = 0.27 + j * 0.045
                    m = aa(np.maximum(np.abs(X - wx) * w / 2 - 6, np.abs(y - wy) * h - 9), 1.5)
                    paint(a, m, C(1.0, 0.72, 0.38) * r.uniform(0.7, 1.0))
    # 塔と尖塔
    for tx, tt, sw in [(0.42, 0.80, 0.035), (1.30, 0.86, 0.04), (1.78, 0.70, 0.03)]:
        tower = np.maximum(np.abs(X - tx) * w / 2 - sw * w / 2, (y - tt) * h)
        paint(a, aa(tower, 1.5), stone)
        sp = np.maximum((y - (tt + 0.14 - np.abs(X - tx) * 3.8)) * h, (tt - 0.01 - y) * h)
        paint(a, aa(sp, 1.5), stone)
        for k in range(3):
            if r.random() < 0.7:
                m = aa(np.maximum(np.abs(X - tx) * w / 2 - 5, np.abs(y - (tt - 0.06 - k * 0.07)) * h - 10), 1.5)
                paint(a, m, C(1.0, 0.75, 0.4))
    # 手前の木立(秋)
    trees = np.zeros((h, w), np.float32)
    n = fbm(w, h, (40, 20), 4, 21)
    for k in range(18):
        cx = r.uniform(0, 2.0)
        cy = r.uniform(0.18, 0.40)
        rad = r.uniform(0.06, 0.14)
        d = np.sqrt(((X - cx) / 1.0) ** 2 + ((y - cy) * 0.5 / 0.5) ** 2) - rad - 0.04 * (n - 0.5)
        trees = np.maximum(trees, aa(d * w / 2, 2))
    leafcol = (C(0.08, 0.06, 0.03) * (1 - n[..., None]) + C(0.28, 0.14, 0.05) * n[..., None])
    a = a * (1 - trees[..., None]) + leafcol * trees[..., None]
    paint(a, aa((y - 0.16) * h, 2), C(0.02, 0.02, 0.02))
    # 街灯
    for k in range(7):
        lx = r.uniform(0.05, 1.95)
        ly = r.uniform(0.17, 0.26)
        d = np.sqrt(((X - lx) * w / 2) ** 2 + ((y - ly) * h) ** 2)
        a += C(1.0, 0.7, 0.35)[None, None, :] * (np.exp(-d / 6) * 0.9 + np.exp(-d / 40) * 0.12)[..., None]
    save("tex_night_campus", a)


if __name__ == "__main__" or not globals().get("ONLY"):
    rug()
    poster_circle()
    poster_shapes()
    scene_photo("tex_photo_campus1", 400, 480, 1)
    scene_photo("tex_photo_campus2", 400, 480, 2)
    for i in range(8):
        scene_photo(f"tex_pinned_{i}", 200, 250, 10 + i)
    wallpaper()
    night_campus()
else:
    for f in ONLY:
        globals()[f]()
print("textures:", sorted(f for f in os.listdir(TEX)))
