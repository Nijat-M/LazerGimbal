#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 3 / 步骤 3 : YOLOv8 egitimi  /  训练

  pip install ultralytics
  python s3_train.py --data ../dataset/data.yaml --imgsz 960 --epochs 80

NOT / 注意:
  15 m'deki hedef ~45 px olur. imgsz=640 KULLANMAYIN, kucuk hedefte recall duser.
  15 m 处目标只有约 45 像素。不要用默认 imgsz=640，小目标召回会明显下降。
  960 veya 1280 kullanin.  /  用 960 或 1280。
"""
import argparse, os, sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../dataset/data.yaml")
    ap.add_argument("--model", default="yolov8s.pt", help="yolov8n.pt daha hizli / 更快")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default="0", help="GPU icin '0', CPU icin 'cpu'")
    ap.add_argument("--name", default="yetenek6")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        sys.exit("pip install ultralytics")

    if not os.path.exists(a.data):
        sys.exit(f"data.yaml yok / 不存在: {a.data}  (once s2_dataset.py)")

    m = YOLO(a.model)
    m.train(
        data=os.path.abspath(a.data),
        imgsz=a.imgsz, epochs=a.epochs, batch=a.batch,
        device=a.device, workers=a.workers, name=a.name,
        patience=25, cache=False, pretrained=True, val=True, plots=True,
        # sentetik veri zaten cesitli; asiri augment gereksiz / 合成数据已够多样，无需过度增广
        hsv_h=0.015, hsv_s=0.6, hsv_v=0.4,
        degrees=8.0, translate=0.12, scale=0.55, shear=2.0,
        fliplr=0.5, mosaic=0.8, mixup=0.05, copy_paste=0.0,
    )
    best = os.path.join("runs", "detect", a.name, "weights", "best.pt")
    print("\n=== BITTI / 完成 ===")
    print("Agirlik / 权重:", os.path.abspath(best))
    print("Sonraki adim / 下一步:  python s4_detector.py --weights", best, "--source 0")


if __name__ == "__main__":
    main()
