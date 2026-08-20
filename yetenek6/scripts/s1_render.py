#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 1 / 步骤 1 : 3MF -> çok açılı şeffaf PNG (sprite) + baskı için yüksek çözünürlüklü poster
                  3MF -> 多视角透明 PNG（贴图素材）+ 打印用高分辨率海报图

Blender GEREKMEZ. Sadece numpy + Pillow + trimesh.
不需要 Blender，只用 numpy + Pillow + trimesh。

Kullanım / 用法:
    python s1_render.py --models_dir ../models_3mf --out ../out --views 160
    python s1_render.py --models_dir ../models_3mf --out ../out --poster_only

Dosya adı = sınıf adı.  Örn: models_3mf/F16.3mf  ->  sınıf "F16"
文件名即类别名。例：models_3mf/F16.3mf -> 类别 "F16"
"""
import argparse, math, os, sys, glob
import numpy as np
from PIL import Image, ImageDraw

try:
    import trimesh
except ImportError:
    sys.exit("trimesh yok / 未安装 trimesh:  pip install trimesh lxml networkx")

# --------------------------------------------------------------------------
# Mesh yükleme / 网格加载
# --------------------------------------------------------------------------
def decimate_vf(V, F, target):
    """Yüz sayısını gerçekten düşürür. / 真正减面（保持轮廓，不产生麻点）。"""
    if len(F) <= target:
        return V, F
    try:
        import fast_simplification
        v, f = fast_simplification.simplify(
            np.asarray(V, np.float32), np.asarray(F, np.int32),
            target_reduction=1.0 - target / len(F))
        return np.asarray(v, np.float64), np.asarray(f, np.int64)
    except Exception as e:
        print(f"   !! yuz azaltma basarisiz / 减面失败 ({e}); tam mesh kullaniliyor", flush=True)
        return V, F


def load_mesh(path, max_faces=120000):
    obj = trimesh.load(path, force='mesh')
    if isinstance(obj, trimesh.Scene):
        obj = trimesh.util.concatenate(tuple(obj.geometry.values()))
    if obj is None or len(obj.faces) == 0:
        raise ValueError(f"Bos mesh / 空网格: {path}")

    # merkeze al + birim küreye ölçekle  /  居中 + 归一化到单位尺度
    V = np.asarray(obj.vertices, dtype=np.float64)
    V -= (V.min(0) + V.max(0)) / 2.0
    V /= max(np.abs(V).max(), 1e-9)

    F = np.asarray(obj.faces, dtype=np.int64)

    # 3MF içinde renk varsa al  /  若 3MF 自带颜色则读取
    fc = None
    try:
        vis = obj.visual
        if hasattr(vis, "face_colors") and vis.face_colors is not None:
            c = np.asarray(vis.face_colors)[:, :3].astype(np.float64) / 255.0
            if len(c) == len(F) and c.std() > 0.01:
                fc = c
    except Exception:
        pass

    # yüz sayısını sınırla -> render hızlanır  /  限制面数以加速渲染
    if len(F) > max_faces:
        V, F = decimate_vf(V, F, max_faces)
        fc = None                       # indeksler değişti / 面索引已变，颜色作废
    return V, F, fc


# --------------------------------------------------------------------------
# Basit painter-algorithm rasterizer (GPU gerekmez) / 简易画家算法光栅化（无需 GPU）
# --------------------------------------------------------------------------
def rot_matrix(az_deg, el_deg, roll_deg):
    az, el, rl = map(math.radians, (az_deg, el_deg, roll_deg))
    Ry = np.array([[ math.cos(az), 0, math.sin(az)], [0, 1, 0], [-math.sin(az), 0, math.cos(az)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(el), -math.sin(el)], [0, math.sin(el), math.cos(el)]])
    Rz = np.array([[math.cos(rl), -math.sin(rl), 0], [math.sin(rl), math.cos(rl), 0], [0, 0, 1]])
    return Rz @ Rx @ Ry


def render_rgba(V, F, face_colors, az, el, roll, size=512, ss=3,
                base_color=(0.62, 0.66, 0.70), light=(0.4, 0.8, 0.5),
                ambient=0.42, margin=0.06):
    """Tek görüntü render eder, RGBA (şeffaf zemin) döner. / 渲染单张 RGBA（透明底）"""
    R = rot_matrix(az, el, roll)
    P = V @ R.T

    # ortografik projeksiyon, görüntüye sığdır  /  正交投影并适配画布
    xy = P[:, :2]
    lo, hi = xy.min(0), xy.max(0)
    span = max((hi - lo).max(), 1e-9) * (1.0 + margin * 2)
    ctr = (lo + hi) / 2.0
    S = size * ss
    scr = (xy - ctr) / span * S + S / 2.0
    scr[:, 1] = S - scr[:, 1]                      # y ekseni ters / y 轴翻转

    tri = P[F]                                     # (m,3,3)
    depth = tri[:, :, 2].mean(1)
    order = np.argsort(depth)                      # uzaktan yakına / 由远及近

    # Lambert gölgeleme / 朗伯着色
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True); ln[ln == 0] = 1
    n = n / ln
    L = np.array(light, dtype=np.float64); L /= np.linalg.norm(L)
    lam = np.clip(np.abs(n @ L), 0, 1)
    inten = np.clip(ambient + (1 - ambient) * lam, 0, 1)

    cols = (np.asarray(face_colors) if face_colors is not None
            else np.tile(np.asarray(base_color, dtype=np.float64), (len(F), 1)))
    rgb = np.clip(cols * inten[:, None], 0, 1)
    rgb8 = (rgb * 255).astype(np.uint8)

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    poly = scr[F]                                  # (m,3,2)
    for i in order:
        p = poly[i]
        dr.polygon([(p[0, 0], p[0, 1]), (p[1, 0], p[1, 1]), (p[2, 0], p[2, 1])],
                   fill=(int(rgb8[i, 0]), int(rgb8[i, 1]), int(rgb8[i, 2]), 255))
    img = img.resize((size, size), Image.LANCZOS)
    return crop_alpha(img)


def render_rgba_zbuf(V, F, face_colors, az, el, roll, size=1600, ss=2,
                     base_color=(0.68, 0.71, 0.74), light=(0.4, 0.8, 0.5),
                     ambient=0.42, margin=0.06):
    """Gercek z-buffer -> kesisen govde/kanat hatasi olmaz. Poster icin.
       真正的 z-buffer，机身与机翼相交处不会出错。用于海报打印。"""
    R = rot_matrix(az, el, roll)
    P = V @ R.T
    xy = P[:, :2]
    lo, hi = xy.min(0), xy.max(0)
    span = max((hi - lo).max(), 1e-9) * (1.0 + margin * 2)
    ctr = (lo + hi) / 2.0
    S = int(size * ss)
    scr = (xy - ctr) / span * S + S / 2.0
    scr[:, 1] = S - scr[:, 1]

    tri2 = scr[F]                       # (m,3,2)
    triz = P[F][:, :, 2]                # (m,3)
    n = np.cross(P[F][:, 1] - P[F][:, 0], P[F][:, 2] - P[F][:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True); ln[ln == 0] = 1
    n = n / ln
    L = np.array(light, float); L /= np.linalg.norm(L)
    inten = np.clip(ambient + (1 - ambient) * np.clip(np.abs(n @ L), 0, 1), 0, 1)
    cols = (np.asarray(face_colors) if face_colors is not None
            else np.tile(np.asarray(base_color, float), (len(F), 1)))
    rgb8 = (np.clip(cols * inten[:, None], 0, 1) * 255).astype(np.uint8)

    zbuf = np.full((S, S), -np.inf, np.float64)
    out = np.zeros((S, S, 4), np.uint8)
    for i in range(len(F)):
        p = tri2[i]
        x0 = max(int(np.floor(p[:, 0].min())), 0); x1 = min(int(np.ceil(p[:, 0].max())) + 1, S)
        y0 = max(int(np.floor(p[:, 1].min())), 0); y1 = min(int(np.ceil(p[:, 1].max())) + 1, S)
        if x1 <= x0 or y1 <= y0:
            continue
        xs = np.arange(x0, x1) + 0.5
        ys = np.arange(y0, y1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        d = ((p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1]))
        if abs(d) < 1e-12:
            continue
        w0 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / d
        w1 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / d
        w2 = 1.0 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any():
            continue
        z = w0 * triz[i, 0] + w1 * triz[i, 1] + w2 * triz[i, 2]
        sub = zbuf[y0:y1, x0:x1]
        upd = m & (z > sub)
        if not upd.any():
            continue
        sub[upd] = z[upd]
        blk = out[y0:y1, x0:x1]
        blk[upd, 0], blk[upd, 1], blk[upd, 2] = rgb8[i, 0], rgb8[i, 1], rgb8[i, 2]
        blk[upd, 3] = 255
    img = Image.fromarray(out, "RGBA").resize((size, size), Image.LANCZOS)
    return crop_alpha(img)


def crop_alpha(img, pad=2):
    a = np.array(img)[:, :, 3]
    ys, xs = np.where(a > 8)
    if len(xs) == 0:
        return img
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, img.width)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, img.height)
    return img.crop((x0, y0, x1, y1))


def tint(img, rgb):
    """Sprite'ı hedef renge boya (kırmızı=düşman / mavi=dost). / 给素材上色（红=敌 / 蓝=友）"""
    a = np.array(img).astype(np.float64)
    lum = a[:, :, :3].mean(2, keepdims=True) / 255.0
    lum = 0.30 + 0.85 * lum                        # kontrastı koru / 保留明暗
    a[:, :, :3] = np.clip(lum * np.array(rgb, dtype=np.float64), 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


# --------------------------------------------------------------------------
COLORS = {"kirmizi": (215, 40, 35), "mavi": (35, 85, 205), "gri": (150, 158, 166)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models_dir", default="../models_3mf")
    ap.add_argument("--out", default="../out")
    ap.add_argument("--views", type=int, default=160, help="model başına render sayısı / 每个模型渲染张数")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--az_range", type=float, nargs=2, default=[-38, 38],
                    help="yatay açı; düz baskı hedef için dar tut / 水平角，打印平面靶标时收窄")
    ap.add_argument("--el_range", type=float, nargs=2, default=[-22, 22])
    ap.add_argument("--roll_range", type=float, nargs=2, default=[-14, 14])
    ap.add_argument("--colors", default="kirmizi,mavi,gri",
                    help="üretilecek renk varyantları / 生成的颜色变体")
    ap.add_argument("--poster_cm", type=float, default=60.0, help="baskı hedef genişliği cm / 打印靶标宽度")
    ap.add_argument("--poster_cm_map", default="",
                    help="sinif basina genislik / 按类别指定宽度, orn: F16=50,MINI_IHA=37.5 "
                         "(resmi 3MF olculeri icin / 用于官方 3MF 尺寸)")
    ap.add_argument("--poster_dpi", type=int, default=150)
    ap.add_argument("--poster_only", action="store_true")
    ap.add_argument("--sprite_only", action="store_true",
                    help="poster'i atla, sadece egitim spritelari / 跳过海报，只出训练素材")
    ap.add_argument("--poster_faces", type=int, default=120000,
                    help="poster icin yuz butcesi; yuksek = temiz baski / 海报面数预算，高=打印干净")
    ap.add_argument("--sprite_faces", type=int, default=15000,
                    help="sprite icin yuz butcesi; dusuk = hizli render / 素材面数预算，低=渲染快")
    ap.add_argument("--real_mm_map", default="",
                    help="sinif basina EN UZUN kenar (mm, resmi 3MF) / 按类别的最长边(mm，官方3MF). "
                         "verilirse her sprite'in gercek fiziksel genisligi sprite_meta.json'a yazilir "
                         "/ 给了就把每张素材的真实物理宽度写进 sprite_meta.json")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    # 3MF disinda STL/OBJ/PLY/GLB de kabul et (s0b_split_3mf.py STL uretir)
    # 除 3MF 外也接受 STL/OBJ/PLY/GLB（s0b_split_3mf.py 产出的是 STL）
    files = sorted(f for ext in ("3mf", "stl", "obj", "ply", "glb")
                   for f in glob.glob(os.path.join(a.models_dir, f"*.{ext}")))
    if not files:
        sys.exit(f"Model bulunamadi / 未找到模型文件: {a.models_dir}")

    sp_root = os.path.join(a.out, "sprites")
    po_root = os.path.join(a.out, "posters")
    os.makedirs(sp_root, exist_ok=True); os.makedirs(po_root, exist_ok=True)
    variants = [c.strip() for c in a.colors.split(",") if c.strip()]

    # sinif basina baski genisligi / 按类别的打印宽度
    cm_map = {}
    for kv in a.poster_cm_map.split(","):
        kv = kv.strip()
        if kv:
            k, _, v = kv.partition("=")
            cm_map[k.strip().upper()] = float(v)
    if cm_map:
        print("Sinif basina genislik / 按类别宽度:", cm_map, "\n")

    # sinif basina en uzun kenar (mm) -> normalize edilmis birim = mm_map/2
    # 按类别的最长边(mm)，归一化单位换算：1 unit = mm_map/2
    mm_map, sprite_meta = {}, {}
    for kv in a.real_mm_map.split(","):
        kv = kv.strip()
        if kv:
            k, _, v = kv.partition("=")
            mm_map[k.strip().upper()] = float(v)

    for path in files:
        cls = os.path.splitext(os.path.basename(path))[0]
        print(f"[{cls}] yukleniyor / 加载中 ...", flush=True)
        budget = a.sprite_faces if a.sprite_only else a.poster_faces
        V, F, fc = load_mesh(path, max_faces=budget)
        print(f"   {len(V)} vertex, {len(F)} face")

        # ---- POSTER: baskı için yandan görünüm / 打印用侧视图 ----
        if not a.sprite_only:
            cm = cm_map.get(cls.upper(), a.poster_cm)
            pw = int(cm / 2.54 * a.poster_dpi)
            big = render_rgba_zbuf(V, F, fc, az=90, el=8, roll=0, size=max(pw, 1200), ss=2,
                                   base_color=(0.68, 0.71, 0.74))
            for vname in variants:
                im = tint(big, COLORS[vname]) if vname in COLORS else big
                canvas = Image.new("RGB", (im.width + 80, im.height + 80), (255, 255, 255))
                canvas.paste(im, (40, 40), im)
                fp = os.path.join(po_root, f"{cls}_{vname}_{cm:g}cm_{a.poster_dpi}dpi.png")
                canvas.save(fp, dpi=(a.poster_dpi, a.poster_dpi))
            print(f"   poster {cm:g} cm genislik/宽 -> {po_root}")
            if a.poster_only:
                continue

        # ---- SPRITE: eğitim verisi için çok açılı / 训练数据用多视角 ----
        # sprite'lar 512 px; poster mesh'i gereksiz agir -> ayrica sadelestir
        # 素材只有 512 px，海报用的网格太重 —— 单独再减一次面
        Vs, Fs = decimate_vf(V, F, a.sprite_faces)
        fcs = fc if (fc is not None and len(fc) == len(Fs)) else None
        print(f"   {len(Fs)} face (sprite)")
        d = os.path.join(sp_root, cls); os.makedirs(d, exist_ok=True)
        n = a.views
        for i in range(n):
            az = 90 + rng.uniform(*a.az_range)      # 90 = yandan görünüş / 90 度为侧视
            if rng.random() < 0.25:                 # bir kısmı ters yön / 一部分反向
                az = -90 + rng.uniform(*a.az_range)
            el = rng.uniform(*a.el_range)
            rl = rng.uniform(*a.roll_range)
            g = rng.uniform(0.55, 0.80)
            im = render_rgba(Vs, Fs, fcs, az, el, rl, size=a.size, ss=3,
                             base_color=(g, g * 1.04, g * 1.08),
                             light=(rng.uniform(-1, 1), rng.uniform(0.2, 1), rng.uniform(0.2, 1)),
                             ambient=rng.uniform(0.30, 0.55))
            vname = variants[i % len(variants)]
            if vname in COLORS:
                im = tint(im, tuple(int(np.clip(c * rng.uniform(0.82, 1.18), 0, 255))
                                    for c in COLORS[vname]))
            fn = f"{cls}_{vname}_{i:04d}.png"
            im.save(os.path.join(d, fn))

            # bu acidaki GERCEK fiziksel genislik (m) / 该视角下的真实物理宽度(米)
            # karsidan bakista F16 12 cm, yandan 50 cm -- ayni sayiyi kullanmak yanlis olur
            # 迎头看 F16 只有 12cm，侧看 50cm —— 用同一个数字是错的
            if cls.upper() in mm_map:
                Pv = Vs @ rot_matrix(az, el, rl).T
                ex = float(Pv[:, 0].max() - Pv[:, 0].min())
                sprite_meta[f"{cls}/{fn}"] = round(ex * mm_map[cls.upper()] / 2.0 / 1000.0, 5)
            if (i + 1) % 40 == 0:
                print(f"   {i+1}/{n}", flush=True)
        print(f"   sprites -> {d}")

    if sprite_meta:
        import json
        mp = os.path.join(sp_root, "sprite_meta.json")
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(sprite_meta, f)
        w = list(sprite_meta.values())
        print(f"\nsprite_meta.json: {len(w)} sprite, "
              f"gercek genislik/真实宽度 {min(w)*100:.1f} - {max(w)*100:.1f} cm")

    print("\nBITTI / 完成.  ->", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
