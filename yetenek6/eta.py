# -*- coding: utf-8 -*-
"""训练还剩多久 —— 读 results.csv 算平均每轮耗时并外推"""
import os, glob, time, csv

CANDS = [
    r"C:\Users\BYC TURK\Desktop\Hava savunma\LazerGimbal\runs\detect\*",
    r"C:\Users\BYC TURK\Desktop\Hava savunma\LAZERCODE\LazerGimbal\yetenek6\scripts\runs\detect\*",
    r"C:\Users\BYC TURK\Desktop\Hava savunma\LAZERCODE\LazerGimbal\runs\detect\*",
]

dirs = [d for p in CANDS for d in glob.glob(p) if os.path.isdir(d)]
if not dirs:
    raise SystemExit("找不到训练目录，可能还没开始训练")
run = max(dirs, key=os.path.getmtime)
csv_fp = os.path.join(run, "results.csv")
print(f"训练目录: {run}\n")

if not os.path.exists(csv_fp):
    print("results.csv 还没生成 —— 第一轮还没跑完，再等一两分钟")
    raise SystemExit

rows = list(csv.DictReader(open(csv_fp, encoding="utf-8")))
if not rows:
    print("第一轮还没跑完")
    raise SystemExit

TOTAL = 60
done = len(rows)
# time 列是从训练开始的累计秒数
key = next((k for k in rows[0] if k.strip().lower() == "time"), None)
elapsed = float(rows[-1][key]) if key else (time.time() - os.path.getctime(csv_fp))
per = elapsed / done
left = per * (TOTAL - done)


def hm(s):
    s = int(s)
    return f"{s//3600}小时{s%3600//60}分" if s >= 3600 else f"{s//60}分{s%60}秒"


m = next((k for k in rows[0] if "mAP50(B)" in k and "95" not in k), None)
best = max(float(r[m]) for r in rows) if m else None

print(f"进度      : {done}/{TOTAL} 轮  ({done/TOTAL*100:.0f}%)")
print(f"每轮耗时  : {per:.0f} 秒")
print(f"已用时间  : {hm(elapsed)}")
print(f"预计剩余  : {hm(left)}")
print(f"预计完成  : {time.strftime('%H:%M', time.localtime(time.time() + left))}")
if best is not None:
    cur = float(rows[-1][m])
    print(f"\n当前 mAP50: {cur:.3f}   最好: {best:.3f}   (合格线 0.85)")
