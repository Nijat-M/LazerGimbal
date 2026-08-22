# 🎯 SADIR 1798-K

<div align="center">

### Otonom Hava Savunma ve Hassas Optik Lazer Takip Sistemi
**Gerçek Zamanlı Bilgisayarlı Görü, IFF Dost/Düşman Tanıma ve STM32 Gömülü Kontrollü 2 Eksenli Kapalı Çevrim Gimbal Platformu**

[![Yarışma](https://img.shields.io/badge/TEKNOFEST%202026-Çelikkubbe%20Hava%20Savunma-red?style=for-the-badge&logo=target)](https://www.youtube.com/watch?v=ou6Uf3Ik7QI)
[![Başvuru ID](https://img.shields.io/badge/Başvuru%20ID-5208679-blue?style=for-the-badge)](https://www.youtube.com/watch?v=ou6Uf3Ik7QI)
[![Lisans: MIT](https://img.shields.io/badge/Lisans-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Arayüz-PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/Görü-OpenCV%20%7C%20YOLOv8-5C3EE8?style=flat-square&logo=opencv&logoColor=white" alt="Görü">
  <img src="https://img.shields.io/badge/Gömülü-STM32F401-03234B?style=flat-square&logo=stmicroelectronics&logoColor=white" alt="STM32">
  <img src="https://img.shields.io/badge/CUDA-12.6%20Hızlandırmalı-76B900?style=flat-square&logo=nvidia&logoColor=white" alt="CUDA">
  <img src="https://img.shields.io/badge/Donanım-MKS%20SERVO42C%20FOC-FF6F00?style=flat-square" alt="MKS SERVO42C">
</p>

[🇬🇧 English](README.md) • [🇹🇷 Türkçe](README_TR.md)

</div>

---

## 📸 Donanım Prototipi ve Saha Konuşlandırması

<div align="center">
  <table>
    <tr>
      <td width="58%" align="center" valign="middle">
        <img src="images/2_horizontal.png" width="100%" alt="Lazer Gimbal Donanım Prototipi (Yakın Çekim)">
        <p><b>🔬 Donanım Prototipi (Yakın Çekim)</b><br>
        <i>2 Eksenli Özel Gimbal, Optik Ray, Yüksek Güçlü Lazer Modülü, Arducam Global Shutter Kamera ve STM32 Kontrolcüsü</i></p>
      </td>
      <td width="42%" align="center" valign="middle">
        <img src="images/1_vertical.jpg" width="100%" alt="15m Koridor Hedef Angajman Saha Testi">
        <p><b>🎯 15m Uzun Menzil Saha Testi</b><br>
        <i>Koridor Hedef Tespiti, Otonom Hedef Kilidi ve Bilgisayar Telemetri Takibi</i></p>
      </td>
    </tr>
  </table>
</div>

---

## 📺 Sistem Tanıtım Videosu (Video Demonstration)

<div align="center">

### 🏆 [2026 Çelikkubbe Hava Savunma Sistemleri Yarışması | Başvuru ID: 5208679](https://www.youtube.com/watch?v=ou6Uf3Ik7QI)

[![2026 Çelikkubbe Hava Savunma Sistemleri Yarışması | Başvuru ID: 5208679](https://img.youtube.com/vi/ou6Uf3Ik7QI/maxresdefault.jpg)](https://www.youtube.com/watch?v=ou6Uf3Ik7QI)

*Yukarıdaki görsele tıklayarak sistemin üçüncü aşama (Stage 3) otonom görev icrası, canlı IFF dost-hedef koruması ve hassas lazer takip kabiliyetlerini YouTube üzerinden izleyebilirsiniz.*

</div>

---

## 📌 Genel Bakış (Overview)

**LazerGimbal SADIR 1798-K**, hassas hedef tespiti, dost/düşman ayrımı (IFF) ve lazerle angajman görevleri için geliştirilmiş endüstriyel kalitede 2 eksenli kapalı çevrim bir optik hava savunma gimbal sistemidir. **TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması** gereksinimlerine tam uyumlu olarak tasarlanmış olup yüksek hızlı bilgisayarlı görü ile gerçek zamanlı mikrodenetleyici kontrolünü entegre eder.

Sistem üç ana sacayağından oluşur:
1. **Ana Bilgisayar Yapay Zeka & Görü Motoru (PC / PyQt6 / Python)**: 60 FPS hızında global shutter kamera akışını işler, çok uzaylı (HSV+BGR+CIELAB) IFF algoritması ile dost/düşman hedefleri ayrıştırır ve Ultralytics YOLO tabanlı derin öğrenme çıkarımını sıfır NMS gecikmesiyle yürütür.
2. **Gerçek Zamanlı Gömülü Kontrolcü (STM32F401 / C HAL)**: 10kHz sürekli fazlı DDA darbe üreteci ve 50Hz Artımlı PID döngüsü ile iki adet **Makerbase MKS SERVO42C kapalı çevrim vektör step motorunu (`CR_vFOC`)** sıfır adım kaybı ve yüksek torkla kontrol eder.
3. **Yetenek 6 Sıfır Etiketlemeli Sentetik Veri Hattı**: Yarışma 3MF CAD modellerini (`Modeller.3mf`) farklı açılardan fotogerçekçi olarak işleyip gerçek arka planlarla harmanlayarak el ile etiketleme yapmaksızın YOLO eğitim veri setleri üreten tam otomatik veri hattı.

---

## 🚀 Temel Özellikler ve İnovasyonlar

### 🛡️ Aşama 3 (Stage 3) Otonom Hava Savunma ve IFF Motoru
- **Otonom Görev Yöneticisi (Stage 3 Mission Director)**: Hedef tarama, düşman kilitleme ve imha, 10s atış sonrası bekleme, acil durdurma (ESTOP) tetikleme, 10s bekleme ve güvenli kapanıştan oluşan 6 aşamalı yarışma durum makinesi.
- **Yüksek Güvenilirlikli Çok Uzaylı IFF**: HSV, normalize BGR farkı ve CIELAB kroma uzaylarını birleştirerek kırmızı düşman ve mavi dost hedefleri ortam sarı ışığı ve ahşap yansımalarından kusursuzca ayırt eder.
- **%100 Dost Unsur Koruma Kilidi**: Nişangah alanı içerisine mavi dost unsur girdiğinde lazer atışını donanımsal/yazılımsal olarak kesin olarak bloke eden güvenlik kilidi.
- **Turuncu Balon Avı Modu (Balloon Hunt)**: Turuncu balon hedeflerini otomatik olarak tespit eder, hedefe kilitlenir ve patlama görsel olarak doğrulanana kadar kesintisiz lazerle angajman uygular.

### 👁️ Bilgisayarlı Görü ve Taktik HUD (PyQt6 / Python)

<div align="center">
  <img src="images/GUI.png" width="95%" alt="Taktik Kullanıcı Arayüzü">
  <p><i>Modern Siber-Karanlık PyQt6 Taktiksel Kontrol Paneli — Canlı Kamera Akışı, Hedef Kilidi, Hata Ayıklama Maskesi ve Cihaz Kontrolü</i></p>
</div>

- **Arducam AR0234 Global Shutter Kamera Desteği**: Hızlı gimbal ivmelenmelerinde jello/rolling-shutter bozulması ve hareket bulanıklığı olmaksızın 1080p @ 60 FPS kararlı takip.
- **Taktik PiP (Picture-in-Picture) Büyüteç Dürbünü**: Kalibre edilmiş lazer nişangahı ile gerçek zamanlı senkronize çalışan dijital hedef yakınlaştırma dürbünü.
- **Sabit Kare Hızlı (CFR 30fps) Video Kaydı**: Mikrofon ortam sesi ve HUD telemetri OSD katmanı ile eşzamanlı `.mp4` video kaydı.
- **Sıfır Titremeli Uzamsal Çoklu Hedef Takipçisi**: Çoklu hedeflerde kimlik karışmasını ve kutu titremelerini önleyen Öklid veri ilişkilendirmesi ve Kalman filtreleme.
- **Dinamik Görüntü Yönü Değişimi**: Tavana montaj (180° ters çevirme) ve yatay ayna modları arayüzden anında uygulanabilir.

### ⚡ Gerçek Zamanlı Hareket Kontrolü (STM32F401 / C HAL)
- **10kHz Sürekli Fazlı DDA Darbe Üreteci**: Düşük hızlarda mikro-adım sürekliliği sağlayan donanımsal darbe motoru.
- **50Hz Artımlı PID Döngüsü**: Sürtünme ve ölü bölge kompanzasyonuna sahip kapalı çevrim hassas konumlandırma.
- **3 Kademeli Vites Sistemi**: `1`, `2`, `3` kısayol tuşları ile Keşif, Seyir ve Hızlı İntikal vitesleri arasında anında geçiş.
- **5 Katmanlı Güvenlik Mimarisi**:
  1. **Voltaj Dalgalanması İyileştirme**: Hata anında pinleri 0V'a çeken ve 1ms'de yeniden başlayan (`NVIC_SystemReset()`) hata yakalayıcılar.
  2. **Çift Donanım/Yazılım Watchdog**: İletişim koptuğunda 500ms içinde motorları kilitleyen güvenlik bekçisi.
  3. **Hız ve İvme Sınırlandırması**: Mekanik zorlanmaları önleyen dinamik sınırlar.
  4. **UART Koordinat Filtreleme**: İletişim parazitlerine karşı koordinat sınırlama.
  5. **Bloklanmayan Kalp Atışı LED'i (`PC13`)**: Donanım çalışma durumunu gösteren durum göstergesi.

### 🧠 Yetenek 6 — 3MF Sentetik Eğitim ve Sınıflandırma
- **Sıfır Manuel Etiketleme Hattı**: 3MF montaj modellerini STL parçalarına böler, çok açılı aydınlatma ile render eder ve gerçek arka planlara otomatik ekleyerek YOLO etiketlerini (txt) hatasız üretir.
- **Çok Sınıflı Hava Hedefi Tespiti**: `F16` savaş uçağı, `HELIKOPTER` taarruz helikopteri, `BALISTIK_FUZE` balistik füze ve `MINI_IHA` mini İHA sınıflarını 5m, 10m ve 15m mesafelerde tespit ve sınıflandırma yeteneği.

---

## 🛠️ Donanım Malzeme Listesi (BOM)

| Bileşen | Model / Özellik | Kullanım Amacı |
| :--- | :--- | :--- |
| **Mikrodenetleyici** | STM32F401CCU6 (Blackpill / ARM Cortex-M4 @ 84MHz) | Gerçek zamanlı hareket kontrolü & DDA darbe üretimi |
| **Motorlar & Sürücüler** | 2x NEMA 17 Step Motor + MKS SERVO42C Kapalı Çevrim FOC | Manyetik enkoder geri beslemeli 2 eksen Pan/Tilt sürüşü |
| **Kamera Sensörü** | Arducam AR0234CS Global Shutter USB Kamera (1080p @ 60fps) | Yüksek hızlı, distorsiyonsuz optik hedef yakalama |
| **Lazer Modülü** | 650nm Yüksek Güçlü Lazer Diyot & Optik Ray | Hedef aydınlatma ve simüle atış kontrolü |
| **Güç Kaynağı** | 20V DC 2A+ Regüle Anahtarlamalı Güç Kaynağı | Motor güç hattı (`V+` / `GND`) |
| **Pan-Tilt Gövde** | Özel takviyeli 3D baskı mekanik montaj | Rijit 2 eksenli optik gimbal taşıyıcı |

### 🔌 Donanım Pin ve Elektrik Bağlantı Tablosu (Pinout)

| Alt Sistem | Sinyal Adı | STM32F401 Pini | Bağlı Çevre Birimi / Pin | Mantık / Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| **Pan Ekseni (X)** | `X_STEP` | `PA0` (TIM2_CH1) | MKS SERVO42C `STP` Darbesi | 3.3V Lojik (Active High) |
| **Pan Ekseni (X)** | `X_DIR` | `PA4` (GPIO) | MKS SERVO42C `DIR` Yön Sinyali | CW / CCW Yön Kutupluluğu |
| **Tilt Ekseni (Y)** | `Y_STEP` | `PA1` (TIM2_CH2) | MKS SERVO42C `STP` Darbesi | 3.3V Lojik (Active High) |
| **Tilt Ekseni (Y)** | `Y_DIR` | `PA5` (GPIO) | MKS SERVO42C `DIR` Yön Sinyali | CW / CCW Yön Kutupluluğu |
| **Lazer Modülü** | `LASER_PWM` | `PB0` (TIM3_CH3) | Lazer Sürücü Optokuplör / TTL | 1kHz PWM Güç / Tetikleme |
| **Durum Telemetrisi**| `HEARTBEAT` | `PC13` (GPIO) | Kart Üstü Mavi LED | 500ms Bloklanmayan Darbe |
| **Ana Bilgisayar Hattı**| `USB_CDC` | `PA11` (DM) / `PA12` (DP) | PC USB 3.0 / USB-C Portu | Yerel 12 Mbps Full-Speed CDC |
| **Motor Güç Hattı** | `20V_RAIL` | Harici Güç Kaynağı | MKS Sürücü `V+` / `GND` | Ortak Toprak (`COM` STM32 GND'ye) |

> [!NOTE]
> **Donanım Yol Haritası (Roadmap)**: Ön eleme ve doğrulama testlerinde prototipleme kolaylığı için breadboard kablolaması kullanılmıştır. Final yarışması öncesinde tüm sistemi tek kartta toplayan **özel entegre PCB taşıyıcı kartı** tasarım aşamasındadır.

---

## 📂 Proje Dizin Yapısı (Project Structure)

```text
LazerGimbal/
├── main.py                     # Ana uygulama giriş noktası (PyQt6 + PyTorch DLL koruması)
├── run_app.bat                 # Tek tıkla Windows başlatma betiği
├── requirements.txt            # Python bağımlılıkları
├── Modeller.3mf                # Resmi 3MF 3D hedef modelleri
├── CHANGELOG_TR.md             # Detaylı sürüm geçmişi ve değişiklik günlüğü
│
├── core/                       # Kontrol ve Durum Makinesi Katmanı
│   ├── gimbal_controller.py    # 40Hz PID takip kontrolcüsü ve güvenlik bekçisi
│   ├── serial_thread.py        # Asenkron yüksek hızlı seri UART haberleşmesi
│   ├── stage3_mission_director.py # Aşama 3 otonom hava savunma görev durum makinesi
│   └── control/                # Hata hesaplama ve fareyle manuel hedefleme kontrolcüleri
│
├── vision/                     # Bilgisayarlı Görü ve Derin Öğrenme Katmanı
│   ├── vision_worker.py        # Kamera yakalama, hedef tespiti, PiP dürbün ve video kayıt
│   ├── iff.py                  # Dost/Düşman Tanıma Sistemi (HSV + BGR + CIELAB)
│   ├── yolo_detector.py        # Ultralytics YOLO çıkarım motoru
│   ├── yetenek6_detector.py    # Yetenek 6 hedef tespit bağdaştırıcısı
│   └── yetenek6_stabilizer.py  # Uzamsal-zamansal titreme önleyici stabilizatör
│
├── gui/                        # Kullanıcı Arayüzü Katmanı (PyQt6)
│   ├── main_window.py          # Ana panel penceresi ve yerleşim düzeni
│   └── widgets/                # Modüler arayüz bileşenleri (Kamera, Kontrol, Mod, IFF, Kalibrasyon)
│
├── config/                     # Konfigürasyon ve Kalibrasyon Dosyaları
│   ├── vision_config.py        # Kamera FOV, çözünürlük, renk eşikleri, nişangah ofseti
│   ├── control_config.py       # PID parametreleri, vites hızları, hareket sınırları
│   ├── hardware_config.py      # Seri port baud rate ve darbe tanımları
│   ├── device_config.py        # Kalıcı donanım ve kamera ayarları
│   └── yetenek6_config.py      # Yetenek 6 mesafe ve hedef metrikleri
│
├── STM32F401/                  # Gömülü Yazılım (C / STM32CubeIDE)
│   ├── Core/Src/main.c         # DDA darbe motoru, artımlı PID ve güvenlik fonksiyonları
│   └── Lazer_F401.ioc          # STM32CubeMX donanım pin konfigürasyonu
│
├── yetenek6/                   # Sentetik Veri Seti ve YOLO Eğitim Hattı
│   ├── README_ZH.md            # Ayrıntılı veri hattı kılavuzu (Çince)
│   ├── HIZLI_BASLANGIC_TR.md   # Hızlı başlangıç kılavuzu (Türkçe)
│   ├── models_3mf/             # STL hedef modelleri (F16, Helikopter, Füze, İHA)
│   ├── backgrounds/            # Sentetik yerleşim için gerçek arka plan fotoğrafları
│   └── scripts/                # S0 Kamera -> S1 Render -> S2 Veri Seti -> S3 Eğitim -> S4 Tespit
├── docs/                       # Teknik Araştırma, Parametre Ayarları ve Yol Haritaları
│   ├── Phase3_Kalman_Tracking_Plan.md # Kinematik durum kestirimi ve EKF planı
│   ├── Phase4_Future_Industrial_Upgrades.md # IMU kaskad, ADRC ve PnP atış kontrol planı
│   └── TRACKING_PARAMETERS_GUIDE.md # Parametre ayar kılavuzu ve fiziksel formüller
│
└── tests/                      # Otomatik Birim ve Entegrasyon Testleri
    ├── test_stage3_balloon.py  # Aşama 3 balon savunma ve durum makinesi testi
    ├── test_balloon_hunt.py    # Turuncu balon segmentasyon ve şekil doğrulama testi
    ├── test_iff_color.py       # IFF renk ayrım testi
    └── test_manual_mouse_control.py # Gimbal hareket ve seri komut doğrulama testi
```

---

## ⚡ Hızlı Başlangıç (Quick Start)

### 1. Sistem Gereksinimleri
- **İşletim Sistemi**: Windows 10 / 11 (64-bit)
- **Python**: 3.10 veya üzeri
- **NVIDIA GPU** (YOLO derin öğrenme CUDA hızlandırması için önerilir)

### 2. Kurulum
```bash
# Depoyu klonlayın
git clone https://github.com/Nijat-M/LazerGimbal.git
cd LazerGimbal

# Sanal ortam oluşturun
python -m venv .venv
.venv\Scripts\activate

# Bağımlılıkları yükleyin
pip install -r requirements.txt
```

### 3. Uygulamayı Başlatma
```bash
python main.py
# Veya birlikte gelen toplu iş dosyasını çalıştırın:
run_app.bat
```

---

## 📜 Lisans ve Teşekkürler

Bu proje **[MIT Lisansı](LICENSE)** ile lisanslanmıştır.

**TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması (Başvuru ID: 5208679)** kapsamında geliştirilmiştir. Açık kaynak robotik ve bilgisayarlı görü topluluklarına teşekkür ederiz.