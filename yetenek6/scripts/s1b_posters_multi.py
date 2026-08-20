#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 1b : Ayni modelin 3 farkli acidan baski posteri
          同一模型的 3 种视角打印图

Neden 3 aci / 为什么要 3 个视角:
    Videoda ayni hedefi farkli acilardan gostermek, siniflandiricinin tek bir
    sabit gorunume ezberlemedigini kanitlar. Hakem icin ikna edici.
    视频里同一目标以不同角度出现，证明分类器不是死记一个固定视角。

Fiziksel boyut resmi 3MF olculerinden ANALITIK hesaplanir - her aci icin
projeksiyon genisligi farklidir, sabit bir sayi kullanmak yanlis olur.
物理尺寸由官方 3MF 尺寸解析算出 —— 每个视角的投影尺寸不同，用固定值是错的。

    python s1b_posters_multi.py --models_dir ../models_3mf --out ../out/posters_multi
"""
import argparse, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s1_render import load_mesh, render_rgba_zbuf, rot_matrix, tint, COLORS

# 3MF (resmi) ham bbox mm / 官方 3MF 原始外形尺寸
BBOX_MM = {
    "BALISTIK_FUZE": (105.1, 218.9, 500.0),
    "HELIKOPTER":    (392.5, 582.7, 178.4),
    "F16":           (300.4, 500.0, 139.3),
    "MINI_IHA":      (287.5, 375.0, 195.1),
}

# (etiket, azimut, elevasyon) / (标签, 方位角, 俯仰角)
VIEWS = [
    ("A_yandan",  90, 8),    # mevcut: yan / ust gorunum   当前：侧视/俯视
    ("B_capraz",  45, 10),   # 3/4 capraz                  45 度斜视
    ("C_karsidan", 0, 6),    # burun uste - karsidan       迎头正视
]


def projected_cm(V, Zmm, az, el):
    """Bu acidaki projeksiyon genisligi/yuksekligi (cm).
       该视角下的投影宽高（厘米）。V 已归一化，尺度 = Zmm/2。"""
    P = V @ rot_matrix(az, el, 0).T
    ex = (P[:, 0].max() - P[:, 0].min()) * Zmm / 2 / 10.0
    ey = (P[:, 1].max() - P[:, 1].min()) * Zmm / 2 / 10.0
    return ex, ey


def paper_of(w, h):
    for n, (pw, ph) in (("A4", (21.0, 29.7)), ("A3", (29.7, 42.0)),
                        ("A2", (42.0, 59.4)), ("A1", (59.4, 84.1))):
        if (w <= pw and h <= ph) or (w <= ph and h <= pw):
            return n
    return ">A1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models_dir", default="../models_3mf")
    ap.add_argument("--out", default="../out/posters_multi")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--colors", default="kirmizi")
    ap.add_argument("--faces", type=int, default=200000)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    variants = [c.strip() for c in a.colors.split(",") if c.strip()]

    print(f"{'sinif/类别':<16}{'aci/视角':<13}{'baski cm/打印':<15}{'kagit/纸型':<8}dosya")
    print("-" * 86)

    for cls, bb in BBOX_MM.items():
        path = os.path.join(a.models_dir, f"{cls}.stl")
        if not os.path.exists(path):
            sys.exit(f"model yok / 缺模型: {path}")
        Zmm = max(bb)
        V, F, fc = load_mesh(path, max_faces=a.faces)

        for vname, az, el in VIEWS:
            ex, ey = projected_cm(V, Zmm, az, el)
            pw = int(max(ex, ey) / 2.54 * a.dpi)
            img = render_rgba_zbuf(V, F, fc, az=az, el=el, roll=0,
                                   size=max(pw, 1200), ss=2,
                                   base_color=(0.68, 0.71, 0.74))
            for vc in variants:
                im = tint(img, COLORS[vc]) if vc in COLORS else img
                canvas = Image.new("RGB", (im.width + 80, im.height + 80), (255, 255, 255))
                canvas.paste(im, (40, 40), im)
                fn = f"{cls}_{vname}_{vc}_{ex:.0f}x{ey:.0f}cm.png"
                canvas.save(os.path.join(a.out, fn), dpi=(a.dpi, a.dpi))
            print(f"{cls:<16}{vname:<13}{ex:5.1f} x {ey:<6.1f}{paper_of(ex,ey):<8}{fn}")
        print()

    print("BITTI / 完成 ->", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
