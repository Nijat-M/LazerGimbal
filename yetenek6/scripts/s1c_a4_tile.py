#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 1c : Buyuk hedef gorselini A4 sayfalara bol (evde yazdirip yapistirmak icin)
          把大幅靶标图切成 A4 分页（在家打印后拼贴）

Neden script gerekiyor / 为什么需要脚本:
  1) Yazicilar kagit kenarindan ~5mm basamaz. Goruntuyu duz bolerseniz
     her ekte bir serit kaybolur ve parcalar tutmaz.
     打印机四周约 5mm 打不到。直接切图的话每个接缝都会少一条，拼不上。
  2) Parcalar arasinda BINDIRME payi olmali ki yapistirirken hizalanabilsin.
     拼块之间要有【重叠】余量，粘的时候才能对齐。
  3) Her sayfada 10 cm cetvel var - yazdirdiktan sonra olcun.
     Tam 10 cm degilse yazici olcegi bozmus demektir (En sik hata).
     每页都印一把 10cm 尺子 —— 打完拿尺量，不是正好 10cm 就说明打印机缩放了（最常见的错误）。

Kullanim / 用法:
    python s1c_a4_tile.py --src ../out/posters_multi --out ../out/a4_tiles
"""
import argparse, glob, math, os, re
from PIL import Image, ImageDraw, ImageFont

MM = 25.4
A4_W_MM, A4_H_MM = 210.0, 297.0


def _font(px):
    for p in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                pass
    return ImageFont.load_default()


def plan(w_mm, h_mm, use_w, use_h, ov):
    """Kac sutun x kac satir gerekir / 需要几列几行"""
    cols = max(1, math.ceil((w_mm - ov) / (use_w - ov)))
    rows = max(1, math.ceil((h_mm - ov) / (use_h - ov)))
    return cols, rows


def tile_one(img, w_mm, name, out_dir, dpi=150, margin=10.0, ov=10.0):
    h_mm = w_mm * img.height / img.width

    # dikey mi yatay mi az sayfa tutar / 竖版还是横版页数少
    best = None
    for land in (False, True):
        pw, ph = (A4_H_MM, A4_W_MM) if land else (A4_W_MM, A4_H_MM)
        uw, uh = pw - 2 * margin, ph - 2 * margin
        c, r = plan(w_mm, h_mm, uw, uh, ov)
        if best is None or c * r < best[0] * best[1]:
            best = (c, r, land, pw, ph, uw, uh)
    cols, rows, land, pw, ph, uw, uh = best

    px_per_mm = dpi / MM
    big = img.resize((max(int(w_mm * px_per_mm), 1), max(int(h_mm * px_per_mm), 1)),
                     Image.LANCZOS).convert("RGB")

    PW, PH = int(pw * px_per_mm), int(ph * px_per_mm)
    M = int(margin * px_per_mm)
    step_x = (uw - ov) * px_per_mm
    step_y = (uh - ov) * px_per_mm
    f = _font(int(4.0 * px_per_mm))
    fs = _font(int(3.0 * px_per_mm))

    pages = []
    for r in range(rows):
        for c in range(cols):
            page = Image.new("RGB", (PW, PH), (255, 255, 255))
            sx, sy = int(c * step_x), int(r * step_y)
            part = big.crop((sx, sy, min(sx + int(uw * px_per_mm), big.width),
                             min(sy + int(uh * px_per_mm), big.height)))
            page.paste(part, (M, M))
            dr = ImageDraw.Draw(page)

            # bindirme cizgisi: buradan kesip ustune yapistir
            # 重叠线：沿这条线裁，然后压在下一张上面
            ovpx = int(ov * px_per_mm)
            if c < cols - 1:
                x = M + int(uw * px_per_mm) - ovpx
                dr.line([(x, 0), (x, PH)], fill=(255, 0, 0), width=2)
            if r < rows - 1:
                y = M + int(uh * px_per_mm) - ovpx
                dr.line([(0, y), (PW, y)], fill=(255, 0, 0), width=2)

            # kose hizalama isaretleri / 四角对齐标记
            t = int(5 * px_per_mm)
            for (cx, cy) in ((M, M), (PW - M, M), (M, PH - M), (PW - M, PH - M)):
                dr.line([(cx - t, cy), (cx + t, cy)], fill=(0, 0, 0), width=1)
                dr.line([(cx, cy - t), (cx, cy + t)], fill=(0, 0, 0), width=1)

            # 10 cm CETVEL - yazdirdiktan sonra olcun / 10cm 尺子，打完必量
            rx, ry = M, PH - int(6 * px_per_mm)
            dr.line([(rx, ry), (rx + int(100 * px_per_mm), ry)], fill=(0, 0, 0), width=3)
            for k in range(11):
                x = rx + int(k * 10 * px_per_mm)
                dr.line([(x, ry - int(2.5 * px_per_mm)), (x, ry)], fill=(0, 0, 0), width=2)
            dr.text((rx + int(102 * px_per_mm), ry - int(4 * px_per_mm)),
                    "10 cm - OLCUN! / 量这个!", font=fs, fill=(200, 0, 0))

            idx = r * cols + c + 1
            dr.text((M, int(2 * px_per_mm)),
                    f"{name}   [{idx}/{cols*rows}]  satir{r+1}-sutun{c+1}   "
                    f"TAM BOYUT {w_mm:.0f}x{h_mm:.0f}mm   %100 OLCEK",
                    font=f, fill=(0, 0, 0))
            pages.append(page)

    fp = os.path.join(out_dir, f"{name}__{cols}x{rows}_A4_{'yatay' if land else 'dikey'}.pdf")
    pages[0].save(fp, "PDF", resolution=dpi, save_all=True, append_images=pages[1:])
    return cols, rows, land, w_mm, h_mm, fp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="../out/posters_multi")
    ap.add_argument("--out", default="../out/a4_tiles")
    ap.add_argument("--only", default="kirmizi", help="renk filtresi / 颜色过滤")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--margin", type=float, default=10.0, help="yazdirilamayan kenar payi mm / 页边距")
    ap.add_argument("--overlap", type=float, default=10.0, help="yapistirma bindirmesi mm / 拼贴重叠")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    files = [f for f in sorted(glob.glob(os.path.join(a.src, "*.png")))
             if a.only in os.path.basename(f)]
    if not files:
        raise SystemExit(f"gorsel yok / 无图片: {a.src}")

    print(f"{'hedef/靶标':<34}{'A4':<8}{'yon':<8}{'gercek boyut/实际尺寸':<22}")
    print("-" * 84)
    tot = 0
    for fp in files:
        base = os.path.splitext(os.path.basename(fp))[0]
        m = re.search(r"_(\d+)x(\d+)cm", base)
        if not m:
            print(f"  ATLANDI/跳过 (boyut adda yok): {base}")
            continue
        w_mm = float(m.group(1)) * 10.0
        img = Image.open(fp)
        c, r, land, W, H, out = tile_one(img, w_mm, base, a.out, a.dpi, a.margin, a.overlap)
        tot += c * r
        print(f"{base:<34}{c}x{r}={c*r:<4}{'yatay' if land else 'dikey':<8}"
              f"{W/10:.1f} x {H/10:.1f} cm")
    print("-" * 84)
    print(f"TOPLAM / 共 {tot} sayfa A4\n-> {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
