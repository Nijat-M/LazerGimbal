#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 6 / 步骤 6 : Telefon ekraninda gosterilecek test gorselleri
                  用于手机屏幕显示的测试图

NEDEN / 为什么需要这个:
    out/posters/*.png BEYAZ zeminlidir (matbaa icin, dis hattan kesilecek).
    Model ise seffaf sprite'lari SIYAH zemine yapistirarak egitildi.
    Beyaz zeminli posteri telefonda gostermek modele hic gormedigi bir sey
    gosterir -> tespit edemez. Bu bir model hatasi DEGIL, test hatasidir.

    posters 是白底的（给打印店用，之后要沿轮廓裁掉）。
    而模型是把透明素材贴到黑背景上训练的。
    用手机显示白底海报 = 给模型看它从没见过的东西 -> 检不到。
    这是测试方法的问题，不是模型的问题。

    python s6_telefon_test.py --sprites ../out/sprites --out ../out/telefon_test
"""
import argparse, glob, os, random
import numpy as np
from PIL import Image


def make(sprite_fp, w, h, fill, rng):
    """Sprite'i siyah zemine, ekranin %fill kadarini kaplayacak sekilde yerlestir.
       把素材贴到黑底上，占屏幕宽度的 fill 比例。"""
    # egitimdeki gibi duz siyah degil - hafif gurultulu koyu zemin
    # 跟训练一致：不是纯黑，是带噪声的深色底
    base = rng.integers(10, 34)
    bg = np.full((h, w, 3), float(base))
    yy, xx = np.mgrid[0:h, 0:w]
    vig = 1.0 - 0.25 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    bg *= np.clip(vig, 0.6, 1.0)[:, :, None]
    bg += rng.normal(0, 3.0, (h, w, 3))
    canvas = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))

    sp = Image.open(sprite_fp).convert("RGBA")
    tw = int(w * fill)
    sc = tw / sp.width
    sp = sp.resize((max(int(sp.width * sc), 4), max(int(sp.height * sc), 4)), Image.LANCZOS)
    canvas.paste(sp, ((w - sp.width) // 2, (h - sp.height) // 2), sp)
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprites", default="../out/sprites")
    ap.add_argument("--out", default="../out/telefon_test")
    ap.add_argument("--w", type=int, default=1170, help="telefon ekran px / 手机屏幕宽")
    ap.add_argument("--h", type=int, default=2532)
    ap.add_argument("--fills", default="0.75,0.45,0.25",
                    help="ekrani kaplama orani = yakin/orta/uzak / 占屏比例=近/中/远")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    random.seed(a.seed)
    os.makedirs(a.out, exist_ok=True)

    classes = sorted(d for d in os.listdir(a.sprites)
                     if os.path.isdir(os.path.join(a.sprites, d)))
    fills = [float(x) for x in a.fills.split(",")]

    n = 0
    for cls in classes:
        # yandan gorunume yakin olanlari sec (ilk yarisi karisik aci)
        pool = sorted(glob.glob(os.path.join(a.sprites, cls, "*.png")))
        for i, fill in enumerate(fills):
            fp = random.choice(pool)
            im = make(fp, a.w, a.h, fill, rng)
            name = f"{cls}_{int(fill*100):02d}pct.png"
            im.save(os.path.join(a.out, name))
            print(f"  {name}")
            n += 1

    print(f"\n{n} gorsel / 张 -> {os.path.abspath(a.out)}")
    print("\nKULLANIM / 用法:")
    print("  1. Bu klasoru telefona kopyala / 把这个文件夹拷到手机")
    print("  2. Ekran parlakligini ARTIR / 屏幕亮度调高")
    print("  3. Kameraya tut, ileri geri hareket ettir / 举到镜头前，前后移动")
    print("  _75pct = yakin hedef / 近距离,  _25pct = uzak hedef / 远距离")


if __name__ == "__main__":
    main()
