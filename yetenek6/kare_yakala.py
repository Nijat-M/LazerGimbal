# -*- coding: utf-8 -*-
"""
从相机抓原始帧存盘，用于离线诊断（不带任何叠加绘制）。
Kameradan ham kare kaydeder - offline teshis icin.

    python kare_yakala.py            # 相机 0，抓 20 帧
    python kare_yakala.py 1 30       # 相机 1，抓 30 帧
"""
import os, sys, time
import cv2

cam = int(sys.argv[1]) if len(sys.argv) > 1 else 0
n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gercek_kareler")
os.makedirs(out, exist_ok=True)

cap = cv2.VideoCapture(cam, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(cam)
if not cap.isOpened():
    sys.exit(f"相机 {cam} 打不开。先关掉上位机界面，或换个编号试试 (0/1/2)。")

# 用比赛分辨率抓，别用 640x360
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
for _ in range(10):
    cap.read()                       # 预热，等自动曝光稳定

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"相机 {cam}  {w}x{h}\n抓 {n} 帧，每 0.3 秒一张。请让靶标保持在画面里...\n")

k = 0
while k < n:
    ok, fr = cap.read()
    if not ok:
        continue
    fp = os.path.join(out, f"kare_{k:03d}.jpg")
    cv2.imwrite(fp, fr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    k += 1
    print(f"  {k}/{n}")
    time.sleep(0.3)
cap.release()
print(f"\n完成 -> {out}")
print("把这个文件夹告诉 Claude，我来分析为什么检不到。")
