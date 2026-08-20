#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 0 / 步骤 0 : Kamera HFOV olcumu + hedef boyutu planlamasi  (20 DAKIKA - ATLAMAYIN)
                  测量相机水平视场角 + 规划靶标尺寸（20 分钟，不要跳过）

Bu adim, 15 m'de hedefin kac piksel olacagini soyler. Butun projenin fizibilitesi buna bagli.
这一步告诉你 15 m 处目标有多少像素。整个方案可行与否取决于此。

--- A) HFOV olcumu / 测量视场角 ---
1. Bilinen genislikte bir cismi (orn. 1.00 m karton) tam olarak 5.00 m mesafeye koyun.
   把一个已知宽度的物体（如 1.00 m 的纸板）放在正好 5.00 m 处。
2. Kameranizla 1 kare cekin, bir goruntu programinda cismin piksel genisligini olcun.
   拍一帧，用看图软件量出该物体的像素宽度。
3. python s0_kamera.py --img_w 1920 --ref_m 1.0 --ref_d 5.0 --ref_px 640

--- B) Planlama / 规划 ---
   python s0_kamera.py --img_w 1920 --hfov 60 --target_m 0.6
"""
import argparse, math


def hfov_from_ref(img_w, ref_m, ref_d, ref_px):
    return 2 * math.degrees(math.atan(img_w * ref_m / (2.0 * ref_d * ref_px)))


def px_size(img_w, hfov, target_m, d):
    return img_w * target_m / (2.0 * d * math.tan(math.radians(hfov) / 2.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img_w", type=int, required=True)
    ap.add_argument("--hfov", type=float, default=None)
    ap.add_argument("--target_m", type=float, default=0.6)
    ap.add_argument("--ref_m", type=float, default=None)
    ap.add_argument("--ref_d", type=float, default=None)
    ap.add_argument("--ref_px", type=float, default=None)
    a = ap.parse_args()

    hfov = a.hfov
    if a.ref_m and a.ref_d and a.ref_px:
        hfov = hfov_from_ref(a.img_w, a.ref_m, a.ref_d, a.ref_px)
        print(f"\nOLCULEN HFOV / 实测视场角 = {hfov:.1f} derece\n")
    if hfov is None:
        raise SystemExit("--hfov ver ya da --ref_m/--ref_d/--ref_px ver")

    print(f"Kamera genisligi / 画面宽度 : {a.img_w} px")
    print(f"HFOV                       : {hfov:.1f} deg")
    print(f"Hedef gercek genisligi / 靶标实际宽度 : {a.target_m:.2f} m\n")
    print(" mesafe/距离   hedef piksel/目标像素   durum/判断")
    for d in (5, 10, 15):
        p = px_size(a.img_w, hfov, a.target_m, d)
        if p >= 80:
            s = "COK IYI / 很好"
        elif p >= 45:
            s = "IYI (imgsz>=960 kullan) / 可以，用 imgsz>=960"
        elif p >= 28:
            s = "SINIRDA (imgsz 1280 + hedefi buyut) / 临界，用 1280 并加大靶标"
        else:
            s = "YETERSIZ! hedefi buyut veya dar FOV lens / 不足！加大靶标或换窄视场镜头"
        print(f"  {d:>2} m        {p:7.1f} px           {s}")

    print("\n--- 15 m'de 60 px icin gereken hedef genisligi / 15m 处达到 60px 所需靶标宽度 ---")
    need = 60 * 2 * 15 * math.tan(math.radians(hfov) / 2.0) / a.img_w
    print(f"  {need:.2f} m  ({need*100:.0f} cm)")
    print("\nNOT: sartname hedef maket/gorsel boyutunu SINIRLAMIYOR. Buyuk yapin.")
    print("注意：规范未限制靶标尺寸，做大一点。\n")


if __name__ == "__main__":
    main()
