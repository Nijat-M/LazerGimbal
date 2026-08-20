#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 2 / 步骤 2 : sprite'lardan YOLO veri seti uret (otomatik etiket, elle etiketleme YOK)
                  用素材合成 YOLO 数据集（标注自动生成，无需人工标注）

Hedefin görüntüdeki piksel boyu gerçek optikten hesaplanır:
目标在画面中的像素尺寸由真实光学参数推算：
        px = img_w * hedef_genislik_m / (2 * mesafe_m * tan(hfov/2))

Kullanım / 用法:
  python s2_dataset.py --sprites ../out/sprites --bg ../backgrounds \
      --out ../dataset --n_train 4000 --n_val 400 \
      --img_w 1920 --img_h 1080 --hfov 60 --target_m 0.6

--bg  = yarışma/test alanınızdan çekilmiş 20-40 fotoğraf koyun (ÇOK ÖNEMLİ).
        放 20-40 张你们实际测试场地的照片（非常重要）。klasör yoksa sentetik zemin üretir.
"""
import argparse, glob, math, os, random, sys
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw


def px_size(img_w, hfov_deg, target_m, dist_m):
    """Gerçek optikten piksel genişliği / 由真实光学参数算像素宽度"""
    return img_w * target_m / (2.0 * dist_m * math.tan(math.radians(hfov_deg) / 2.0))


def synth_bg(w, h, rng):
    """Zemin fotoğrafı yoksa sentetik arka plan / 无场地照片时的合成背景"""
    top = np.array([rng.integers(150, 225), rng.integers(165, 230), rng.integers(185, 245)], float)
    bot = np.array([rng.integers(70, 190), rng.integers(75, 185), rng.integers(70, 175)], float)
    g = np.linspace(0, 1, h)[:, None, None]
    img = top[None, None, :] * (1 - g) + bot[None, None, :] * g
    img = np.repeat(img, w, axis=1)
    # ufuk çizgisi / 地平线
    hz = int(h * rng.uniform(0.45, 0.75))
    img[hz:] *= rng.uniform(0.72, 0.92)
    img += rng.normal(0, 7, img.shape)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    # kaba doku / 粗糙纹理
    for _ in range(rng.integers(4, 14)):
        x, y = rng.integers(0, w), rng.integers(hz, h)
        bw, bh = rng.integers(30, 320), rng.integers(20, 160)
        patch = Image.new("RGB", (bw, bh), tuple(int(c) for c in rng.integers(40, 200, 3)))
        im.paste(Image.blend(im.crop((x, y, x + bw, y + bh)).resize((bw, bh)), patch, 0.35), (x, y))
    return im.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.4)))


def dark_bg(w, h, rng):
    """Siyah kumas / karanlik salon arka plani.
       黑布幕 / 暗色场馆背景。

    Gercek siyah kumas kamerada saf siyah GORUNMEZ: koyu gri, kirisiklik
    golgeleri, esitsiz aydinlatma ve sensor gurultusu icerir. Modeli saf
    siyah uzerinde egitirsek gercek cekimde tokezler.
    真实黑布在相机里【不是纯黑】：是深灰，带褶皱阴影、不均匀打光和传感器噪声。
    只用纯黑训练的话，实拍时会翻车。
    """
    base = rng.integers(8, 46)                       # 布料基础亮度 / 布の基准亮度
    img = np.full((h, w, 3), float(base))
    # 布料轻微偏色（冷/暖光）/ 轻微色偏
    img += rng.normal(0, 3, 3)[None, None, :]

    # 不均匀打光：几个柔和亮斑 / 灯光造成的柔和亮斑
    for _ in range(int(rng.integers(1, 4))):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(0.25, 0.9) * max(w, h)
        yy, xx = np.mgrid[0:h, 0:w]
        fall = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r ** 2)))
        img += (fall * rng.uniform(6, 38))[:, :, None]

    # 竖向褶皱 / 布料垂褶
    if rng.random() < 0.75:
        xs = np.arange(w)
        fold = np.zeros(w)
        for _ in range(int(rng.integers(2, 7))):
            fold += rng.uniform(3, 13) * np.sin(
                2 * np.pi * xs / rng.uniform(60, 420) + rng.uniform(0, 6.3))
        img += fold[None, :, None]

    # 暗角 / 镜头暗角
    yy, xx = np.mgrid[0:h, 0:w]
    vig = 1.0 - 0.32 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    img *= np.clip(vig, 0.55, 1.0)[:, :, None]

    # 传感器噪声：暗部噪声更明显 / 暗部噪声更重
    img += rng.normal(0, rng.uniform(1.5, 6.0), (h, w, 3))

    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

    # 偶尔露出地面 / 场馆地面
    if rng.random() < 0.35:
        gy = int(h * rng.uniform(0.80, 0.97))
        g = np.array(im)
        floor = float(rng.integers(25, 85))
        g[gy:] = np.clip(g[gy:].astype(float) * 0.5 + floor, 0, 255).astype(np.uint8)
        im = Image.fromarray(g)

    return im.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.6)))


def bright_bg(w, h, rng):
    """Beyaz duvar / studyo / asiri pozlanmis zemin  —  白墙 / 影棚 / 过曝背景"""
    base = rng.integers(150, 250)
    img = np.full((h, w, 3), float(base)) + rng.normal(0, 4, 3)[None, None, :]
    yy, xx = np.mgrid[0:h, 0:w]
    # 斜向光照渐变
    ang = rng.uniform(0, 6.28)
    grad = (np.cos(ang) * xx / w + np.sin(ang) * yy / h)
    img += (grad * rng.uniform(-45, 45))[:, :, None]
    if rng.random() < 0.4:                       # 墙面接缝 / 踢脚线
        y0 = int(h * rng.uniform(0.6, 0.95))
        img[y0:] *= rng.uniform(0.55, 0.85)
    img += rng.normal(0, rng.uniform(1, 5), (h, w, 3))
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def outdoor_bg(w, h, rng):
    """Gokyuzu + zemin  —  室外天空 + 地面"""
    top = np.array([rng.integers(120, 235), rng.integers(140, 240), rng.integers(165, 255)], float)
    bot = np.array([rng.integers(55, 175), rng.integers(60, 170), rng.integers(50, 160)], float)
    g = np.linspace(0, 1, h)[:, None, None]
    img = np.repeat(top[None, None, :] * (1 - g) + bot[None, None, :] * g, w, axis=1)
    hz = int(h * rng.uniform(0.45, 0.8))
    img[hz:] *= rng.uniform(0.6, 0.9)
    img += rng.normal(0, 6, (h, w, 3))
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return im.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.5)))


def clutter_bg(w, h, rng):
    """Dagink ic mekan: kutular, direkler, ekipman  —  杂乱室内：箱子、立柱、器材"""
    base = rng.integers(30, 190)
    img = np.full((h, w, 3), float(base)) + rng.normal(0, 6, 3)[None, None, :]
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(im)
    for _ in range(int(rng.integers(6, 26))):
        x0, y0 = rng.integers(-60, w), rng.integers(-40, h)
        bw, bh = rng.integers(25, w // 2), rng.integers(20, h // 2)
        col = tuple(int(c) for c in rng.integers(15, 245, 3))
        if rng.random() < 0.75:
            dr.rectangle([x0, y0, x0 + bw, y0 + bh], fill=col)
        else:
            dr.ellipse([x0, y0, x0 + bw, y0 + bh], fill=col)
    a = np.array(im).astype(float) + rng.normal(0, rng.uniform(2, 9), (h, w, 3))
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return im.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 2.5)))


_BG_CACHE = {}
_BG_CACHE_MAXW = 1700          # bellek/keskinlik dengesi / 内存与清晰度的平衡点


def _bg_cached(fp):
    """9.4MP JPEG'i her ornekte yeniden cozmek uretimi 2 kat yavaslatir.
       Bir kez coz, kucult, bellekte tut.
       每个样本都重新解码 9.4MP JPEG 会让生成慢一倍。解码一次、缩小、常驻内存。"""
    im = _BG_CACHE.get(fp)
    if im is None:
        im = Image.open(fp).convert("RGB")
        if im.width > _BG_CACHE_MAXW:
            s = _BG_CACHE_MAXW / im.width
            im = im.resize((_BG_CACHE_MAXW, int(im.height * s)), Image.LANCZOS)
        _BG_CACHE[fp] = im
    return im


def real_bg(bgs, w, h, rng):
    """SADECE gercek saha fotograflari + guclu augmentasyon.
       只用真实场地照片 + 强增广。

    Az sayida foto (10-20) varsa model onlari ezberler. Bunu onlemek icin
    her seferinde farkli kirpma / ayna / parlaklik / renk sicakligi uygulanir.
    照片只有 10-20 张时模型会背下来。所以每次都做不同的裁剪/镜像/亮度/色温扰动。
    """
    im = _bg_cached(random.choice(bgs))
    if rng.random() < 0.5:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)

    # --- kirpma / 裁剪 ---
    # Kamera koridora YATAY bakar: kare = duvarlar + zemin + tavan, ortada kacis noktasi.
    # Dikey telefon fotosundan ORTA BANDI almaliyiz; rastgele alirsak sadece tavan
    # veya sadece zemin cikar (modele hicbir sey ogretmez).
    # 相机水平看向走廊：画面 = 两侧墙+地+顶，中间是消失点。
    # 竖构图手机照要取【中间那条带】；完全随机会切出纯天花板或纯地板，没有信息量。
    ar = w / h
    # Kaynak 2304x4096 orijinal -> 16:9 kirpma zaten kucultme demek, buyutme yok.
    # Bu yuzden zoom araligi genis tutulabilir (daha fazla cerceveleme cesitliligi).
    # 源图 2304x4096 原片 —— 裁 16:9 本身就是降采样，不存在放大糊化，
    # 所以缩放范围可以放宽，取景变化更多。
    zoom = float(rng.uniform(0.42, 1.0))
    ch = max(int(min(im.height, im.width / ar) * zoom), 64)
    cw = max(int(ch * ar), 64)
    if cw > im.width:
        cw = im.width; ch = max(int(cw / ar), 64)

    cy = im.height * float(rng.uniform(0.38, 0.62))   # 消失点附近
    y = int(np.clip(cy - ch / 2, 0, max(im.height - ch, 0)))
    x = int(rng.integers(0, max(im.width - cw, 0) + 1))
    im = im.crop((x, y, x + cw, y + ch))

    # --- kucuk donme, SIYAH KOSE BIRAKMADAN / 轻微旋转，不留黑角 ---
    # Once dondur, sonra %8 icerden kes -> bos kose kalmaz.
    # 先旋转，再向内裁掉 8% —— 否则四角会出现黑边，模型会把黑边学成特征。
    if rng.random() < 0.35:
        im = im.rotate(float(rng.uniform(-3.5, 3.5)), resample=Image.BILINEAR, expand=False)
        m = 0.08
        im = im.crop((int(im.width * m), int(im.height * m),
                      int(im.width * (1 - m)), int(im.height * (1 - m))))
    im = im.resize((w, h), Image.BILINEAR)

    im = ImageEnhance.Brightness(im).enhance(float(rng.uniform(0.62, 1.22)))
    im = ImageEnhance.Contrast(im).enhance(float(rng.uniform(0.75, 1.30)))
    im = ImageEnhance.Color(im).enhance(float(rng.uniform(0.60, 1.35)))

    # renk sicakligi (ampul sarisi <-> beyaz led) / 色温漂移（暖光灯↔白光）
    a = np.array(im).astype(np.float32)
    a[:, :, 0] *= float(rng.uniform(0.90, 1.12))
    a[:, :, 2] *= float(rng.uniform(0.88, 1.14))
    a += rng.normal(0, rng.uniform(1.5, 7.0), a.shape)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    if rng.random() < 0.35:
        im = im.filter(ImageFilter.GaussianBlur(float(rng.uniform(0.3, 1.6))))
    return im


def rich_bg(w, h, rng, bgs=None):
    """Cesitli arka plan karisimi  —  多样化背景混合"""
    r = rng.random()
    if bgs and r < 0.30:                 # 有真实场地照就优先用
        try:
            im = Image.open(random.choice(bgs)).convert("RGB")
            s = max(w / im.width, h / im.height) * rng.uniform(1.0, 1.4)
            im = im.resize((max(int(im.width * s), w), max(int(im.height * s), h)), Image.BILINEAR)
            x = rng.integers(0, im.width - w + 1); y = rng.integers(0, im.height - h + 1)
            return im.crop((x, y, x + w, y + h))
        except Exception:
            pass
    if r < 0.42:
        return dark_bg(w, h, rng)        # 黑幕（实拍主场景）
    if r < 0.60:
        return clutter_bg(w, h, rng)     # 杂乱室内
    if r < 0.76:
        return bright_bg(w, h, rng)      # 白墙/过曝
    if r < 0.90:
        return outdoor_bg(w, h, rng)     # 室外
    return synth_bg(w, h, rng)           # 原有渐变


def on_card(sp, rng):
    """Sprite'i beyaz/renkli dikdortgen karta yapistir.
       把素材贴到白色/彩色矩形卡片上。
       Matbaa dis hattan kesmezse gercek hedef boyle gorunur - modele ogretelim.
       如果打印店没沿轮廓裁，实物就长这样 —— 让模型也见过。"""
    pad_x = int(sp.width * rng.uniform(0.05, 0.28))
    pad_y = int(sp.height * rng.uniform(0.05, 0.35))
    W, H = sp.width + 2 * pad_x, sp.height + 2 * pad_y
    v = int(rng.integers(190, 255)) if rng.random() < 0.8 else int(rng.integers(20, 90))
    card = Image.new("RGBA", (W, H), (v, v, int(np.clip(v + rng.integers(-12, 12), 0, 255)), 255))
    card.paste(sp, (pad_x, pad_y), sp)
    # etiket maskesi: SADECE ucak (kart degil) -> kutu ucagi cevreler
    # 标注掩膜：只含飞机，不含卡片 —— 保证框住的是飞机而不是白方块
    lab = Image.new("L", (W, H), 0)
    lab.paste(sp.getchannel("A"), (pad_x, pad_y))
    return card, lab


def load_bgs(bg_dir):
    if not bg_dir or not os.path.isdir(bg_dir):
        return []
    ex = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.JPG", "*.PNG")
    return [f for e in ex for f in glob.glob(os.path.join(bg_dir, e))]


def get_bg(bgs, w, h, rng, mode="auto", dark_ratio=0.85):
    """mode: auto = foto varsa foto yoksa acik sentetik / 有照片用照片，否则用亮色合成
             dark = siyah kumas fon (salon cekimi) / 黑布幕（场馆拍摄）"""
    if mode == "real":
        if not bgs:
            sys.exit("bg_mode=real ama backgrounds/ bos! / 但 backgrounds/ 是空的！")
        return real_bg(bgs, w, h, rng)

    if mode == "rich":
        return rich_bg(w, h, rng, bgs)

    if mode == "dark":
        # cogunlukla siyah fon, kalani cesitlilik icin acik zemin
        # 大部分黑幕，留一小部分亮背景保持泛化能力
        if rng.random() < dark_ratio:
            return dark_bg(w, h, rng)
        return synth_bg(w, h, rng)

    if bgs:
        try:
            im = Image.open(random.choice(bgs)).convert("RGB")
            s = max(w / im.width, h / im.height) * rng.uniform(1.0, 1.35)
            im = im.resize((max(int(im.width * s), w), max(int(im.height * s), h)), Image.BILINEAR)
            x = rng.integers(0, im.width - w + 1); y = rng.integers(0, im.height - h + 1)
            return im.crop((x, y, x + w, y + h))
        except Exception:
            pass
    return synth_bg(w, h, rng)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprites", default="../out/sprites")
    ap.add_argument("--bg", default="../backgrounds")
    ap.add_argument("--out", default="../dataset")
    ap.add_argument("--n_train", type=int, default=4000)
    ap.add_argument("--n_val", type=int, default=400)
    ap.add_argument("--img_w", type=int, default=1920)
    ap.add_argument("--img_h", type=int, default=1080)
    ap.add_argument("--hfov", type=float, default=60.0, help="kameranın yatay görüş açısı / 相机水平视场角")
    ap.add_argument("--target_m", type=float, default=0.6, help="baskı hedefin gerçek genişliği (m) / 靶标实际宽度")
    ap.add_argument("--target_m_map", default="",
                    help="sinif basina gercek genislik / 按类别指定实际宽度(米), "
                         "orn: F16=0.50,MINI_IHA=0.375  (resmi 3MF olculeri / 官方 3MF 尺寸)")
    ap.add_argument("--dist_min", type=float, default=3.5)
    ap.add_argument("--dist_max", type=float, default=18.0)
    ap.add_argument("--focus_m", default="5,10,15",
                    help="yogunlastirilacak mesafeler / 重点加密的距离，逗号分隔; bos = kapali/留空关闭")
    ap.add_argument("--focus_ratio", type=float, default=0.55,
                    help="ornegin yuzde kaci focus mesafelerinde / 多大比例样本落在重点距离上")
    ap.add_argument("--max_obj", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bg_mode", default="auto", choices=["auto", "dark", "rich", "real"],
                    help="dark = siyah kumas / 黑布幕;  rich = karisik / 混合;  "
                         "real = SADECE backgrounds/ icindeki gercek saha fotolari / 只用真实场地照")
    ap.add_argument("--card_ratio", type=float, default=0.0,
                    help="hedefi beyaz karta yapistirma orani / 贴白卡片的比例"
                         "（模拟打印店没沿轮廓裁的情况）")
    ap.add_argument("--dark_ratio", type=float, default=0.85,
                    help="bg_mode=dark iken siyah fon orani / 黑幕占比，其余为亮背景保泛化")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed); random.seed(a.seed)
    a.focus_m = [float(x) for x in a.focus_m.split(",") if x.strip()]

    classes = sorted([d for d in os.listdir(a.sprites)
                      if os.path.isdir(os.path.join(a.sprites, d))])
    if not classes:
        sys.exit(f"sprite yok / 无素材: {a.sprites}  (once s1_render.py calistirin)")
    pool = {c: sorted(glob.glob(os.path.join(a.sprites, c, "*.png"))) for c in classes}
    print("Siniflar / 类别:", {c: len(v) for c, v in pool.items()})

    # sinif basina gercek hedef genisligi / 按类别的靶标实际宽度
    tmap = {}
    for kv in a.target_m_map.split(","):
        kv = kv.strip()
        if kv:
            k, _, v = kv.partition("=")
            tmap[k.strip().upper()] = float(v)
    tgt = {c: tmap.get(c.upper(), a.target_m) for c in classes}
    print("Hedef genislik / 靶标宽度 (m):", tgt)

    # s1_render --real_mm_map ile uretildiyse: her sprite'in KENDI gercek genisligi
    # 若 s1_render 带 --real_mm_map 生成过：每张素材有自己的真实宽度
    meta_fp = os.path.join(a.sprites, "sprite_meta.json")
    smeta = {}
    if os.path.exists(meta_fp):
        import json
        with open(meta_fp, encoding="utf-8") as f:
            smeta = json.load(f)
        w = list(smeta.values())
        print(f"sprite_meta.json bulundu / 已找到: {len(w)} sprite, "
              f"{min(w)*100:.1f}-{max(w)*100:.1f} cm  (aci basina gercek olcek / 按视角真实缩放)")
    else:
        print("sprite_meta.json YOK -> sinif basina sabit genislik / 无，按类别固定宽度")

    bgs = load_bgs(a.bg)
    if a.bg_mode == "dark":
        print(f"Arka plan / 背景: SIYAH KUMAS modu (oran {a.dark_ratio:.0%}) / 黑布幕模式")
    else:
        print(f"Arka plan foto / 背景照片: {len(bgs)}" + ("  (SENTETIK kullanilacak / 将用合成背景)" if not bgs else ""))

    for split, n in (("train", a.n_train), ("val", a.n_val)):
        os.makedirs(os.path.join(a.out, "images", split), exist_ok=True)
        os.makedirs(os.path.join(a.out, "labels", split), exist_ok=True)
        for k in range(n):
            W, H = a.img_w, a.img_h
            canvas = get_bg(bgs, W, H, rng, a.bg_mode, a.dark_ratio).convert("RGB")
            lines, boxes = [], []
            for _ in range(int(rng.integers(1, a.max_obj + 1))):
                c = random.choice(classes)
                spf = random.choice(pool[c])
                sp = Image.open(spf).convert("RGBA")
                # bu sprite'in kendi gercek genisligi varsa onu kullan
                # 该素材有自己的真实宽度就用它（迎头/侧视物理宽度不同）
                w_m = smeta.get(f"{c}/{os.path.basename(spf)}", tgt[c])
                # lab = etiket maskesi (kutu bundan hesaplanir) / 标注掩膜，边界框由它算
                lab = sp.getchannel("A")
                # bir kismini beyaz karta yapistir (kesilmemis baski senaryosu)
                # 一部分贴到白卡片上（模拟未沿轮廓裁的打印件）
                if a.card_ratio > 0 and rng.random() < a.card_ratio:
                    w0 = sp.width
                    sp, lab = on_card(sp, rng)
                    w_m *= sp.width / w0          # 卡片变宽了，物理宽度同步放大

                d = float(rng.uniform(a.dist_min, a.dist_max))
                # yogunlastirma / 加密采样：--focus_m ile belirtilen mesafeler
                if a.focus_m and rng.random() < a.focus_ratio:
                    d = float(random.choice(a.focus_m) * rng.uniform(0.85, 1.15))
                tw = px_size(W, a.hfov, w_m * rng.uniform(0.85, 1.15), d)
                if tw < 8 or tw > W * 0.9:
                    continue
                sc = tw / sp.width
                nw, nh = max(int(sp.width * sc), 4), max(int(sp.height * sc), 4)
                rot = float(rng.uniform(-12, 12))
                sp = sp.resize((nw, nh), Image.LANCZOS)
                sp = sp.rotate(rot, expand=True, resample=Image.BICUBIC)
                # etiket maskesine AYNI donusumleri uygula / 标注掩膜施加完全相同的变换
                lab = lab.resize((nw, nh), Image.LANCZOS)
                lab = lab.rotate(rot, expand=True, resample=Image.BICUBIC)

                # mesafeye bagli bulaniklik + atmosfer / 随距离的模糊与大气衰减
                if d > 8:
                    sp = sp.filter(ImageFilter.GaussianBlur(min((d - 8) / 12.0, 0.9)))
                sp = ImageEnhance.Brightness(sp).enhance(float(rng.uniform(0.72, 1.28)))
                sp = ImageEnhance.Contrast(sp).enhance(float(rng.uniform(0.75, 1.25)))

                for _try in range(12):
                    x = int(rng.integers(0, max(W - sp.width, 1)))
                    y = int(rng.integers(0, max(int(H * 0.85) - sp.height, 1)))
                    bb = (x, y, x + sp.width, y + sp.height)
                    if all(not (bb[0] < o[2] and o[0] < bb[2] and bb[1] < o[3] and o[1] < bb[3])
                           for o in boxes):
                        break
                else:
                    continue
                canvas.paste(sp, (x, y), sp)
                boxes.append(bb)

                # kutu SADECE ucaktan hesaplanir, karttan degil
                # 边界框只从飞机算，不含白卡片
                al = np.array(lab)
                ys, xs = np.where(al > 20)
                if len(xs) == 0:
                    continue
                bx0, bx1 = x + xs.min(), x + xs.max()
                by0, by1 = y + ys.min(), y + ys.max()
                cx, cy = (bx0 + bx1) / 2 / W, (by0 + by1) / 2 / H
                bw, bh = (bx1 - bx0) / W, (by1 - by0) / H
                lines.append(f"{classes.index(c)} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

            # global augment / 全局增广
            canvas = ImageEnhance.Brightness(canvas).enhance(float(rng.uniform(0.75, 1.25)))
            if rng.random() < 0.3:
                canvas = canvas.filter(ImageFilter.GaussianBlur(float(rng.uniform(0.2, 1.0))))
            if rng.random() < 0.5:
                arr = np.array(canvas).astype(np.float32) + rng.normal(0, rng.uniform(1, 7), (H, W, 3))
                canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

            name = f"{split}_{k:06d}"
            canvas.save(os.path.join(a.out, "images", split, name + ".jpg"),
                        quality=int(rng.integers(72, 96)))
            with open(os.path.join(a.out, "labels", split, name + ".txt"), "w") as f:
                f.write("\n".join(lines))
            if (k + 1) % 250 == 0:
                print(f"  {split} {k+1}/{n}", flush=True)

    yml = os.path.join(a.out, "data.yaml")
    with open(yml, "w", encoding="utf-8") as f:
        f.write(f"path: {os.path.abspath(a.out)}\ntrain: images/train\nval: images/val\n\n")
        f.write(f"nc: {len(classes)}\nnames:\n")
        for i, c in enumerate(classes):
            f.write(f"  {i}: {c}\n")

    print("\n--- Piksel boyu tablosu / 像素尺寸参考表 ---")
    print(f"kamera {a.img_w}px, hfov {a.hfov} deg")
    print(f"  {'sinif/类别':<16}{'genislik':<10}{'5 m':>9}{'10 m':>9}{'15 m':>9}   15m durum/判断")
    for c in classes:
        row = [px_size(a.img_w, a.hfov, tgt[c], d) for d in (5, 10, 15)]
        p15 = row[2]
        s = ("COK IYI/很好" if p15 >= 80 else "IYI/可以" if p15 >= 45
             else "SINIRDA/临界" if p15 >= 28 else "YETERSIZ!/不足!")
        print(f"  {c:<16}{tgt[c]:.3f} m  " + "".join(f"{v:8.1f} " for v in row) + f"  {s}")
    print("\nBITTI / 完成 ->", os.path.abspath(a.out), "\ndata.yaml ->", yml)


if __name__ == "__main__":
    main()
