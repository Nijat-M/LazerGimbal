# Laser Gimbal Pro

<div align="left">
  <img src="https://img.shields.io/badge/Language-Python%20%7C%20C-blue">
  <img src="https://img.shields.io/badge/GUI-PyQt6-green">
  <img src="https://img.shields.io/badge/Vision-OpenCV%20%7C%20YOLO-orange">
  <img src="https://img.shields.io/badge/Hardware-STM32F401-lightgrey">
</div>

<br>

<div align="right">
  🇬🇧 <a href="README.md">English</a> | 🇹🇷 <a href="README_TR.md">Türkçe</a>
</div>

Masaüstü bilgisayarlı görü (computer vision) ile gerçek zamanlı mikrodenetleyici donanım yürütmesini harmanlayan 2 eksenli (2-axis) lazer gimbal takip sistemi.

## Genel Bakış (Overview)
Bu proje, bilgisayarlı görü ve bir mikrodenetleyicinin birleşimi ile çalışan deneysel bir 2 eksenli lazer gimbal takip sistemidir. Sistem, kamera anlık görüntülerini işlemek, hedefleri algılamak (HSV renk takibi veya YOLO tabanlı derin öğrenme kullanarak) ve konum hatalarını hesaplamak için PyQt6/Python tabanlı bir masaüstü uygulaması kullanır. Hesaplanarak elde edilen bu hata koordinatları, daha sonra yüksek hızlı bir seri iletişim üzerinden STM32F401 mikrodenetleyicisine iletilir.

Donanım tarafında ise STM32, kamerayı etkili bir şekilde hedefin merkezinde tutarak iki MG996R servo motoru kusursuzca sürebilmek için donanım tabanlı bir Artımlı PID (Incremental PID) algoritması çalıştırır. Proje, gerçek zamanlı izleme, PID parametre ayarı ve manuel testler için kullanıcı dostu bir grafiksel arayüze (GUI) sahiptir.

*Not: Bu sistem şu an için sadece test ve AR-GE amaçlı küçük bir kişisel projedir. Gelecekteki bir Teknofest projesi için temel bir prototip (ön model) niteliğindedir. İlerleyen süreçte donanım bileşenleri; endüstriyel sınıf sensörler, gelişmiş motorlar, daha sağlam mekanik yapılar ve sisteme özel tasarlanmış çok katmanlı PCB'ler ile baştan aşağı revize edilecektir.*

## Demo Videoları
- [V0.1.0 Lazer Takip Demosu](https://www.youtube.com/shorts/czz0KMfvBXw) - Gerçek zamanlı lazer takip tanıtımı
- [V0.1.5 Lazer Takip ve PID Demosu](https://www.youtube.com/watch?v=KGi6N0OxIrQ) - Geliştirilmiş PID tepkisi ile gerçek zamanlı takip
- [V0.1.6 Manuel Test Modu](https://www.youtube.com/shorts/dynt_BvkDTA) -  Manuel kontrol paneli ve kalibrasyon

## Değişiklik Günlüğü (Changelog)
Güncellemelerin ve düzeltmelerin detaylı geçmişi için lütfen [CHANGELOG_TR.md](CHANGELOG_TR.md) dosyasına göz atın.

## Sistem Görselleri

<div align="center">
  <img src="images/Camera_and_new_power%20suply.jpeg" width="400" alt="Yeni Kamera ve Güç Sistemi">
  <p><i>Harici 720p USB Kamera ve Stabilize Güç Modülü</i></p>
  
  <img src="images/Pan%20Tilt.jpeg" width="400" alt="Pan-Tilt Mekanizması">
  <p><i>Pan-Tilt Servo Mekanizması (MG996R)</i></p>
  
  <img src="images/GUI.png" width="600" alt="GUI Arayüzü">
  <p><i>Kontrol Arayüzü - Gerçek Zamanlı Durum İzleme, PID Ayarlama ve Manuel Test Paneli</i></p>
</div>

## Temel Özellikler (Core Features)

### 👁️ Bilgisayarlı Görü (PC / Python)
- **Çift Takip Modu (Dual Tracking)**: Hafif ve yüksek performanslı HSV renk takibi ile Derin Öğrenme tabanlı nesne algılama (YOLO26 `yolo26n.pt`) algoritmaları arasında sorunsuzca geçiş imkanı.
- **Kesintisiz Hedef Kilidi**: Çerçevedeki birden fazla algılanan hedef karşısında stabiliteyi koruyabilmek için, merkeze olan Öklid (Euclidean) uzaklığı eşik algoritması temel alınarak veri ilişkilendirmesi yapılmıştır.
- **Çok İş Parçacıklı İşleme (Multithreading)**: Arayüz güncellemeleri (`QTimer`), kamera kare işleme (`vision_worker`) ve seri haberleşme (`serial_thread`) için atanmış asenkron iş parçacıkları kullanılarak UI donmaları tamamen engellenmiştir.
- **Temiz Arayüz (PyQt6)**: Entegre durum izleme (FPS/Çözünürlük), gerçek zamanlı canlı PID ayarlama paneli, Ölü Bölge (Deadzone) koruma sürgüleri ve kapsamlı bir donanım test arayüzü sunar.

### ⚙️ Donanım Kontrolü (STM32 MCU / C)
- **Donanımsal Artımlı (Incremental) PID**: Denetim algoritması yazılımdan tamamen çıkarılarak STM32 mikrodenetleyicisine devredilmiştir. 50Hz'lik donanım kesmesi (`TIM2`) üzerinde çalışarak integral birikmesini (Windup) yok eder ve matematiksel olarak istikrarlı bir motor hızı çıktısı sağlar.
- **Sıfır Gecikmeli Telemetri**: Bloklamasız çalışan yüksek hızlı seri iletişim hattı, yazılım kaynaklı gecikmelere (smoothing delay) maruz kalmadan, hata verisini anlık olarak doğrudan mikrodenetleyiciye besler.
- **Yazılımsal Donanım Koruması**: 
  - **Dönüş Hızı Sınırlandırıcı** (`MAX_SERVO_DELTA`), hedef bir anda farklı bir konuma atladığında dişli sıyırmasını (gear-stripping) engeller.
  - **Asenkron Veri Doğrulama** (`new_data_flag`), bilgisayarlı görü paketlerinde kayıp/gecikme yaşandığında PID integral artışını durdurarak sistemin kontrolden çıkmasını önler.
  - Sınır limiti kodları, servo motorları fiziksel zarar görebileceği açılara (10~170 derece dışı) sürmeyi engeller.

## Gelecek Yol Haritası (Teknofest'e Doğru)
Şu anki geliştirme sürümü işlevsel bir "kavram kanıtlama" (Proof of Concept) prototipidir. Teknofest yarışmasının zorlu gereksinimlerini karşılayabilmek ve endüstriyel standartlara ulaşabilmek adına geliştirmenin sonraki aşamaları şunlara odaklanacaktır:
- **Aşama 3 (Kestirimci Takip - Predictive Tracking)**: Görsel sinyaldeki gürültüleri filtrelemek ve hedefin anlık olarak arkada kalması (oklüzyon) durumlarında takibi sürdürebilmek için Kalman Filtresi yardımıyla yörünge tahmini algoritması eklenecektir.
- **Aşama 4 (Donanım Revizyonu ve PCB Entegrasyonu)**: Çok daha yüksek özellikli endüstriyel donanımlara geçilecektir. Sistem stabilitesi ve kare hızlarını (FPS) doğrudan etkileyen endüstriyel bir kamera yapısına geçiş yapılıp, hobi tipi RC servo motorlar yüksek torklu hassas "Adım (Stepper) Motorlarla" değiştirilecektir. Ayrıca, tüm dağınık kablolama ve kontrolcü yükleri tek bir kompakt devrede birleştirecek özel tasarım bir PCB dizayn edilecektir.

## Donanım Gereksinimleri

### Elektronik
- **Mikrodenetleyici**: STM32F401CCU6 (Blackpill)
- **Motorlar (Aktüatör)**: 2x MG996R Yüksek Torklu Servo
- **Kapasitör**: 1000µF Elektrolitik Kapasitör (Servolar için güç filtrelemesi)
- **Kamera**: Harici 720p USB Masaüstü Kamera (Gimbal üzerine monte)
- **Güç Kaynağı**: 12V 2A DC Adaptör
- **Gerilim Düşürücü (Step-Down)**: XL4016 Buck Converter (Servolar için 6V sabit gerilim)
- **Haberleşme**: HC-05 Bluetooth Modülü veya doğrudan USB-TTL çevirici
- **Lazer**: Kırmızı lazer işaretçi (Takip testleri için, opsiyonel)

### Güç Altyapısı
- **ESKİ**: 4x 1.5V Duracell AA Kalem Pil (6V Çıkış - Kararsız)
- **ŞU ANKİ**: 12V DC Kesintisiz Adaptör + XL4016 Buck Converter (Stabil voltaj ve anlık akım tepkisi)

### Mekanik Altyapı
- **3 Boyutlu Yazdırılan Pan-Tilt Sistemi**: [MakerWorld - Pan Tilt Servo Antenna Tracker MG996R](https://makerworld.com/en/models/973248-pan-tilt-servo-antenna-tracker-mg996r#profileId-945437)

### Devre Şeması (Schematic)
<div align="center">
  <img src="images/Schematic.svg" width="700" alt="Devre Şeması">
  <p><i>Sistem Elektrik Bağlantı Şeması - STM32F401, HC-05, MG996R Servolar</i></p>
</div>

### Proje Dosya Yapısı (Project Structure)
```text
LazerGimbal/
├── config/                # Global konfigürasyon profilleri
│   ├── control_config.py  # PID parametreleri, limitler
│   ├── hardware_config.py # COM port ve Baud Rate ayarları
│   └── vision_config.py   # HSV eşikleri ve kamera çözünürlüğü
├── core/                  # Çekirdek mantık ve haberleşme
│   ├── serial_thread.py   # Asenkron yüksek hızlı seri haberleşme işçisi
│   ├── gimbal_controller.py # 40Hz Çalışan ana döngü & Güvenlik kontrolcüsü (Watchdog)
│   └── control/           
│       └── error_processor.py # Görsel hataların matematiksel sınırlandırıcıları
├── gui/                   # Grafiksel Kullanıcı Arayüzü (PyQt6)
│   ├── main_window.py     # Ana pencerenin montaj noktası
│   ├── test_panel.py      # Manuel servo sürüş kontrol paneli
│   └── widgets/           # Modüler arayüz bileşenleri
├── STM32F401/             # MCU Donanım Yazılımı (Firmware) (C/C++ HAL)
│   ├── Core/Src/main.c    # Donanım tabanlı Artımlı PID çekirdeği ve limit korumaları
│   └── Lazer_F401.ioc     # STM32CubeMX konfigürasyon dosyası
├── utils/                 # Genel yardımcı araçlar (Log, Kayıt)
├── vision/                # Bilgisayarlı Görü (Computer Vision) operasyonları
│   ├── vision_worker.py   # Kareleri yakalayan/işleyen arka plan aracı
│   ├── detector.py        # Temel arayüz sınıfı
│   ├── yolo_detector.py   # YOLO26 destekli Derin Öğrenme sınıfı
│   └── models/            # Sinir ağı ağırlıkları (.pt)
├── CHANGELOG.md           # Harici tutulan versiyon geçmişi
├── main.py                # Sistemin giriş/tetiklenme noktası
└── requirements.txt       # Gerekli bağımlılıklar
```

## Yazılım Gereksinimleri
- Python 3.10 veya üzeri
- Kullanılan Kütüphaneler: `PyQt6`, `opencv-python`, `numpy`, `pyserial`, `qdarktheme`

## Kurulum (Installation)
1. **Projeyi klonlayın (Clone)**:
   ```bash
   git clone https://github.com/Nijat-M/LazerGimbal.git
   cd LazerGimbal
   ```

2. **Sanal ortamı oluşturun (Virtual environment)**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. **Gerekli Python paketlerini yükleyin**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Sistemi başlatın**:
   ```bash
   python main.py
   ```

## Lisans
[MIT Lisansı](LICENSE)