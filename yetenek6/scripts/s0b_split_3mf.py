#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 0b / 步骤 0b : Tek bir cok-nesneli 3MF -> sinif basina ayri mesh dosyasi
                    把一个包含多个对象的 3MF 拆成每类一个网格文件

Modeller.3mf icinde 4 nesne var ama adlari '1','3','5','7' -- anlamsiz.
Bu script onlari ayirir, DOGRU YONE cevirir, yuz sayisini dusurur ve
models_3mf/ altina sinif adiyla STL olarak yazar.
Modeller.3mf 里有 4 个对象但名字是 '1','3','5','7'（无意义）。
本脚本拆分、摆正朝向、减面，按类别名写成 STL 到 models_3mf/。

Yon duzeltme / 朝向校正:
    en uzun eksen -> Z (govde boyu, goruntude yatay)
    en kisa eksen -> X (bakis ekseni)
  s1_render.py az=90'da X ekseni boyunca bakar => planform (ustten) goruntu.
  --side veren siniflar 90 derece dondurulur => yandan goruntu.
    最长轴 → Z（机身长，图像里水平方向）
    最短轴 → X（视线方向）
  s1_render.py 在 az=90 时沿 X 轴看 ⇒ 得到平面视图（俯视）。
  用 --side 指定的类别会绕长轴转 90°，改成侧视图。

Kullanim / 用法:
    python s0b_split_3mf.py --src ../../Modeller.3mf --out ../models_3mf \
        --map 1=BALISTIK_FUZE,3=HELIKOPTER,5=F16,7=MINI_IHA \
        --side BALISTIK_FUZE,HELIKOPTER
"""
import argparse, os, sys
import numpy as np

try:
    import trimesh
except ImportError:
    sys.exit("trimesh yok / 未安装 trimesh:  pip install trimesh lxml networkx")


def decimate(mesh, target):
    """Yuz sayisini gercekten dusur. Basarisizsa uyar (rastgele ornekleme YAPMA -
       o siluetleri benek benek yapar).
       真正减面。失败就告警——绝不随机抽面（那会让轮廓变成麻点）。"""
    n = len(mesh.faces)
    if n <= target:
        return mesh, "atlandi/跳过"

    try:
        import fast_simplification
        v, f = fast_simplification.simplify(
            np.asarray(mesh.vertices, np.float32),
            np.asarray(mesh.faces, np.int32),
            target_reduction=1.0 - target / n,
        )
        return trimesh.Trimesh(vertices=v, faces=f, process=False), "fast_simplification"
    except Exception as e:
        err = e

    try:
        r = mesh.simplify_quadric_decimation(face_count=target)
        if r is not None and len(r.faces) > 0:
            return r, "trimesh_quadric"
    except Exception:
        pass

    print(f"    !! DIKKAT / 警告: yuz azaltma basarisiz ({err}); tam mesh kullaniliyor")
    return mesh, "BASARISIZ/失败"


def canonicalize(V, side_view=False):
    """Eksenleri uzunluga gore siralar: en uzun -> Z, orta -> Y, en kisa -> X.
       按尺寸排序坐标轴：最长→Z，中→Y，最短→X。"""
    V = V - (V.min(0) + V.max(0)) / 2.0
    ext = V.max(0) - V.min(0)
    order = np.argsort(ext)          # [en kisa, orta, en uzun] / [最短, 中, 最长]
    V = V[:, order]                  # -> X=en kisa, Y=orta, Z=en uzun
    if side_view:
        # govde ekseni (Z) etrafinda 90 derece -> X ile Y yer degistirir
        # 绕机身轴(Z)转 90°，X 与 Y 互换 => 俯视变侧视
        V = V[:, [1, 0, 2]]
    V /= max(np.abs(V).max(), 1e-9)
    return V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="cok nesneli 3MF / 多对象 3MF")
    ap.add_argument("--out", default="../models_3mf")
    ap.add_argument("--map", required=True,
                    help="gerecgeom=SINIF virgullu / 几何名=类别名，逗号分隔. orn: 1=F16,3=HELIKOPTER")
    ap.add_argument("--side", default="",
                    help="yandan gorunum istenen siniflar / 需要侧视图的类别，逗号分隔")
    ap.add_argument("--faces", type=int, default=20000, help="hedef yuz sayisi / 目标面数")
    ap.add_argument("--fmt", default="stl", choices=["stl", "obj", "ply"])
    a = ap.parse_args()

    mapping = {}
    for kv in a.map.split(","):
        kv = kv.strip()
        if not kv:
            continue
        k, _, v = kv.partition("=")
        mapping[k.strip()] = v.strip()
    side = {s.strip().upper() for s in a.side.split(",") if s.strip()}

    scene = trimesh.load(a.src)
    if not isinstance(scene, trimesh.Scene):
        sys.exit("Kaynak tek mesh, sahne degil / 源文件是单一网格而非场景")

    os.makedirs(a.out, exist_ok=True)
    print(f"kaynak / 源: {a.src}")
    print(f"nesne / 对象: {list(scene.geometry.keys())}\n")

    missing = set(mapping) - set(scene.geometry)
    if missing:
        sys.exit(f"3MF icinde bulunamayan geometri / 3MF 中找不到这些几何: {missing}")

    for gname, cls in mapping.items():
        g = scene.geometry[gname]
        ext0 = (g.bounds[1] - g.bounds[0]).round(1)
        m, how = decimate(g, a.faces)

        V = canonicalize(np.asarray(m.vertices, np.float64), side_view=cls.upper() in side)
        out_mesh = trimesh.Trimesh(vertices=V, faces=np.asarray(m.faces, np.int64),
                                   process=False)

        fp = os.path.join(a.out, f"{cls}.{a.fmt}")
        out_mesh.export(fp)
        view = "yandan/侧视" if cls.upper() in side else "planform/俯视"
        print(f"[{gname}] -> {cls}")
        print(f"    yuz/面   : {len(g.faces)} -> {len(out_mesh.faces)}  ({how})")
        print(f"    bbox0    : {ext0}")
        print(f"    gorunum  : {view}")
        print(f"    yazildi  : {fp}\n")

    print("BITTI / 完成 ->", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
