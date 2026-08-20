# -*- coding: utf-8 -*-
"""
枚举所有相机，每个存一张样图 —— 看图就知道哪个编号是对的。
Tum kameralari listeler, her birinden 1 ornek kare kaydeder.
"""
import os, sys
import cv2

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kamera_ornek")
os.makedirs(out, exist_ok=True)
for f in os.listdir(out):
    try:
        os.remove(os.path.join(out, f))
    except Exception:
        pass

print("扫描相机 0-4 ...\n")
found = []
for i in range(5):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(i)
    if not cap.isOpened():
        print(f"  相机 {i}: 无")
        cap.release()
        continue

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    for _ in range(8):
        cap.read()
    ok, fr = cap.read()
    if not ok or fr is None:
        print(f"  相机 {i}: 打开了但没画面")
        cap.release()
        continue

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fp = os.path.join(out, f"kamera_{i}__{w}x{h}.jpg")
    cv2.imwrite(fp, fr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"  相机 {i}: {w}x{h}  -> {os.path.basename(fp)}")
    found.append(i)
    cap.release()

print(f"\n可用相机编号: {found}")
print(f"样图在: {out}")
print("\n打开那个文件夹看图，认出哪张是你要的 AR0234，")
print("然后用那个编号抓帧:   YETENEK6_KARE_YAKALA.bat <编号>")
