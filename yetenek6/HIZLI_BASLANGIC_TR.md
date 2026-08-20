# Yetenek 6 — Hizli Baslangic (TR)

3MF dosyalarini `models_3mf/` icine SINIF ADIYLA koyun:
`F16.3mf`, `HELIKOPTER.3mf`, `BALISTIK_FUZE.3mf`, `MINI_IHA.3mf`

```bash
pip install -r requirements.txt
cd scripts

# 0) Kamera HFOV olcumu (1 m'lik cismi 5 m'ye koy, piksel genisligini olc)  --- ATLAMAYIN
python s0_kamera.py --img_w 1920 --ref_m 1.0 --ref_d 5.0 --ref_px 640 --target_m 0.6

# 1) 3MF -> sprite + baski posteri
python s1_render.py --models_dir ../models_3mf --out ../out --views 200 --poster_cm 60

#    -> out/posters/*.png  BUGUN matbaaya verin (KT panoya kaplatip siluet kesin)
#    -> test alaninizdan 30-40 bos fotograf cekip ../backgrounds/ icine koyun

# 2) Otomatik etiketli veri seti (elle etiketleme YOK)
python s2_dataset.py --sprites ../out/sprites --bg ../backgrounds --out ../dataset \
    --n_train 5000 --n_val 500 --img_w 1920 --img_h 1080 --hfov 60 --target_m 0.6

# 3) Egitim  (DIKKAT: imgsz 640 KULLANMAYIN, 15 m'de hedef ~45 px)
python s3_train.py --data ../dataset/data.yaml --imgsz 960 --epochs 80 --device 0

# 4) Test / arayuz
python s5_ui_pyqt.py --weights runs/detect/yetenek6/weights/best.pt \
    --source 0 --hfov 60 --target_m 0.6
```

## Mevcut arayuze entegrasyon (3 satir)

```python
from s4_detector import HedefDedektoru
self.det = HedefDedektoru("best.pt", conf=0.35, imgsz=960, hfov_deg=60, hedef_genislik_m=0.6)

dets = self.det.tespit(frame)
self.label.setPixmap(self.mat2pix(self.det.ciz(frame, dets)))
```

## Cekim kontrol listesi (Yetenek 6)
- [ ] Yerde 5 m / 10 m / 15 m serit metre ile isaretli ve kadrajda gorunuyor
- [ ] Her mesafede 4 hedef tipi sirayla
- [ ] Arayuz ekrani kayitta net gorunuyor (kutu + sinif adi + guven)
- [ ] "Yetenek 6" alt yazi karti
- [ ] 40-60 saniye
