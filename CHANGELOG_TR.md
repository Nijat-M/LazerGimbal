# Değişiklik Günlüğü (Changelog)

<div align="right">
  🇬🇧 <a href="CHANGELOG.md">English</a> | 🇹🇷 <a href="CHANGELOG_TR.md">Türkçe</a>
</div>

### [v0.4.1] - 2026-08-16
- **Ultralytics YOLO26 NMS-Free Motoru ve CUDA 12.6 Donanım Hızlandırması**:
  - En güncel **Ultralytics YOLO26** (`yolo26n.pt`) yerel uçtan uca mimarisi entegre edildi; NMS (Non-Maximum Suppression) işlem yükü ve hedef kutularındaki titremeler tamamen ortadan kaldırıldı.
  - RTX 3060 üzerinde FP16 Tensör Çekirdekleri ile çalışan NVIDIA CUDA 12.6 GPU hızlandırması devreye alınarak çıkarım süresi 30ms altına indirildi.
  - Eski YOLOv8 model kalıntıları ve gereksiz ağırlık dosyaları temizlendi.
- **Asenkron Ayrıştırılmış Görsel İşlem Hattı (`AsyncYOLODetector`)**:
  - 60 FPS kamera yakalama/arayüz çizim akışı ile arka plan GPU derin öğrenme çıkarımını tamamen birbirinden ayıran çift tamponlu asenkron mimari kuruldu.
  - 1080p, 720p ve 480p çözünürlüklerdeki mikro-takılmalar (micro-stuttering) ve düzensiz kare aralıkları giderilerek 60.0 FPS pürüzsüz canlı izleme ve kesintisiz hedef takibi sağlandı.
- **Arducam AR0234 Global Shutter Endüstriyel Kamera Uyarlaması**:
  - Arducam AR0234 Global Shutter (Onsemi AR0234CS) yüksek hızlı endüstriyel kamera entegrasyonu; hızlı gimbal dönüşlerinde oluşan hareket bulanıklığı (motion blur) ve jello/rolling-shutter bozulması tamamen ortadan kaldırıldı.
  - DirectShow üzerinde öncelikli `CAP_PROP_FOURCC = 'MJPG'` donanımsal sıkıştırma anlaşması ile USB bant genişliği darboğazları çözüldü.
  - Arayüze eklenen `CAP_PROP_SETTINGS` donanım paneli butonu ile mikrosaniye düzeyinde manuel Pozlama Süresi (Exposure), Kazanç (Gain) ve Beyaz Dengesi ayarı sağlandı.
- **Piramit Çok Ölçekli Algılama Hızlandırması ve Tek Geçişli HSV İşleme**:
  - `TargetDetector` modülünde piramit alt örnekleme (pyramid subsampling) mimarisi uygulandı: 1080p kareler renk ayrımı ve morfolojik filtreleme için çalışma anında optimize edilerek CPU işlem gecikmesi 18ms'den **~3.2ms'ye düşürüldü (5.5 kat hızlanma)**.
  - Aktif takip modlarında (`BLUE_TRACKING` / `TRACKING`) kare düşmesi engellenerek stabil **60.0 FPS** tam kare hızı güvenceye alındı.
  - Hedef koordinatları ve yarıçapları orijinal 1080p tam çözünürlüğe alt piksel hassasiyetiyle otomatik geri eşlendi.
- **Anlık Görüntü Yönü ve Ters Montaj (Upside-Down) Sıcak Değişimi**:
  - Algılama öncesinde doğrudan yakalama akışına uygulanan sıfır gecikmeli görüntü çevirme (`Normal`, `180° Ters Montaj Çevirme`, `Dikey Çevirme`, `Yatay Ayna`) eklendi; PID koordinat polaritesi kusursuz korundu.
- **GUI Kamera Paneli Düzenlemesi ve Hata Düzeltmeleri**:
  - Kamera kontrol paneli çift sütunlu ergonomik buton gruplarıyla (`Aç/Kapat` & `Uygula`, `⚙️ Pozlama/Kazanç Ayarı` & `🔄 Cihazları Yenile`) modernize edildi.
  - Çözünürlük seçenekleri gimbal takip için ideal altın oran olan **60 FPS** standartlarına uyarlandı (`640x480`, `1280x720`, `1920x1080`).
  - Kontrolü Başlat butonuna tıklandığında oluşan `AttributeError: 'ModePanel' object has no attribute 'get_current_mode'` hatası giderildi.

### [v0.4.0] - 2026-08-16
- **MKS SERVO42C Kapalı Çevrim Step Motor Yükseltmesi**: Eski MG996R RC servolar, 20V DC endüstriyel güç beslemeli, yüksek torklu NEMA 17 step motorlar ve Makerbase MKS SERVO42C vektör FOC (`CR_vFOC`) kapalı çevrim sürücülerle değiştirildi. Adım kaybı (lost steps) tamamen ortadan kaldırıldı.
- **10kHz Donanımsal DDA Mikro-Adım Darbe Üreticisi**: STM32F401 ürün yazılımı, 10kHz donanımsal zamanlayıcı kesmesi (`TIM2`) ve Bresenham / DDA gerçek zamanlı darbe enterpolasyonuyla yeniden yazıldı. 50Hz Artımlı PID döngüsü ile titreşimsiz ve ultra akıcı hareket sağlandı.
- **5 Katmanlı Endüstriyel Güvenlik ve Hata Koruma Mimarisi**:
  - Güç dalgalanmalarına ve ani akım şoklarına karşı motor pinlerini anında 0V'a çeken ve 1 milisaniyede kendini yeniden başlatan (`NVIC_SystemReset()`) otomatik iyileşen `HardFault_Handler` entegrasyonu.
  - 2.0 saniye kesintisiz görsel güvenlik bekçisi (Watchdog) ile bağlantı koptuğunda otomatik frenleme ve şaft kitleme.
  - Darbe hızı sınırlayıcı (`MAX_STEPS_PER_CYCLE = 80`) ve seri port koordinat kısıtlaması ($\pm 400\text{px}$) ile motor kontrol dışı dönmelerine karşı koruma.
  - 500ms bloklanmayan durum bildirim LED'i (`PC13`) ile donanım çalışma göstergesi.
- **Gelişmiş Manuel ve Klavye Kontrolü**:
  - Çift modlu kontrol: Kısa tıklama ile tek adımlık hassas mikro-adım, basılı tutma ile 40Hz pürüzsüz sürekli dönüş ve bırakıldığında anında frenleme.
  - Ayrı bir anahtarla etkinleştirilen `WASD` / Yön tuşları (`↑ / ↓ / ← / →`) klavye kontrol modu ve otomatik tekrarlama filtresi.
  - Eksen atalet dengelemesi (X ekseni gövde ağırlığı kompanzasyonu ve Y ekseni hassasiyet kalibrasyonu).
- **Akıllı Takip Kontrol Bağlantısı**: Seri port ve kamera durumunu otomatik doğrulayan ve tek tıklamayla görsel takip algoritmasını başlatan akıllı "Kontrolü Başlat" butonu.

### [v0.3.7] - 2026-08-09

- **Arayüz ve Kontrol Yenilemesi (GUI & Control Refactor)**: PyQt6 arayüz bileşenleri (Kamera görünümü, Kamera paneli, Seri panel) geliştirilmiş durum göstergeleri ve sinyal yapılarıyla güncellendi.
- **Gimbal Kontrolcüsü Stabilitesi**: İş parçacığı (thread) döngüsü performansı artırıldı, güvenlik (watchdog) mekanizmaları ve telemetri işleme optimize edildi.
- **Yapay Zeka Modeli ve Günlükleme**: YOLO26 desteğinin yanında varsayılan YOLOv8 model ağırlıkları (`yolov8n.pt`) entegre edildi, iş parçacıkları genelinde standart günlükleme (logging) sağlandı.
- **Otomatik Başlatıcı**: Otomatik ortam kurulumu ve bağımlılık başlatması için `run_app.bat` betiği eklendi.

### [v0.3.6] - 2026-03-19
- **YOLO26 Takip Motoru (Tracking Engine)**: Bilgisayarlı görü mimarisi YOLOv8'den son teknoloji NMS-Free (Non-Maximum Suppression içermeyen) YOLO26 `yolo26n.pt` modeline yükseltildi. Sınırlayıcı kutu (bounding-box) titremeleri ve algılama gecikmeleri önemli ölçüde azaltıldı.
- **Merkez-Mesafe Odaklı Veri İlişkilendirme**: Saf yüksek güven (confidence) seçimi yerine, Öklid mesafesine dayalı hedef kilitleme algoritması (`150px` eşik değeri) uygulandı. Bu sayede kareler arasında kalıcı ve kararlı bir hedef kilidi (lock-on) sağlandı.
- **Sıfır Gecikmeli Hata İşlemcisi**: Yazılımsal `.max_pixel_jump` güvenlik kısıtlayıcısı kullanılarak, eski `deque` hareketli ortalama (moving average) yazılım filtreleri kaldırıldı. Yerini "Sıfır Gecikmeli (0-delay)", ham ve doğrudan hata iletimi aldı.
- **Çok İş Parçacıklı PID Eşzamanlılığı**: `GimbalController`, PyQt `QTimer` ana olay döngüsünden (event loop) ayrıştırılarak, doğrudan `40Hz` (`time.perf_counter()`) frekansta çalışan bağımsız bir asenkron iş parçacığına (Thread) dönüştürüldü. Arayüzde (UI) yaşanabilecek saniyelik donmaların PID türev (derivative) hesaplamalarını bozmasının önüne geçildi.
- **Bloklanmayan Seri Haberleşme**: `serial_thread.py` modülü `readline()` tıkanmalarını (deadlock) tamamen önleyecek şekilde yeniden yazıldı. Telemetri aktarımlarında kuyruk bloklanmaları önlenerek mikrosaniye düzeyinde iletişim güvence altına alındı.
- **STM32 Uç Durum (Edge-Case) Korumaları**: 
  - Asenkron telemetri kaybı yaşandığında "Kör İntegral Birikmesini (Blind Integral Windup)" önlemek için `new_data_flag` mantığı devreye alındı.
  - Ölü bölgeden (deadzone) çıkarken oluşan hedef sapmalarını önlemek adına, hata akışı durum sürekliliği güvence altına alınarak "Türev Sıçraması (Derivative Kick)" düzeltildi.
  - Motor dişlilerinin kırılmasını ve yüksek akım şoklarını önlemek amacıyla mekanik fiziksel servolara Dönüş Hızı Limitörleri/Kısıtlayıcıları (`MAX_SERVO_DELTA`) entegre edildi.

### [v0.3.5] - 2026-03-19
- **STM32 Artımlı (Incremental) PID**: STM32 mikrodenetleyicisi üzerindeki matematiksel olarak patlamaya müsait Konumsal PID algoritması, kararlı ve güvenilir motor hız çıkışı sağlayan sistemler için kalibre edilmiş gerçek bir "Artımlı (Incremental) PID" sistemine çevrildi.
- **Arayüz Üzerinden (UI) Ölü Bölge (Deadzone) Ayarı**: PID ayar paneline özel bir 'Ölü Bölge' kontrol kaydırıcısı eklendi. Sabit hedeflerdeki zayıf kamera fps hızlarının/gecikmelerin veya piksel gürültülerinin yol açtığı yapısal motor avlanma (hunting/osilasyon) durumu yazılımsal olarak filtrelenebildi.
- **Mimari Temizlik**: Doğrudan saf doğrusal (linear) sistem takibi sağlamak üzere, eski koddaki katı oranlama tabloları ve kullanılmayan yapılar (`CONTROL_DEADZONE_LEVELS`, `ERROR_SCALING`) `error_processor` dosyasından kaldırıldı.
- **Endüstriyel Takip Yol Haritası**: Geleceğe dönük profesyonel sürekli takip yapısı (Kalman Filtresi, ADRC, Kinematik Öncü Hesaplaması) yolları formüle edilerek belgelendirildi.

### [v0.3.0] - 2026-03-13
- **YOLOv8 Nesne Takibi (Object Tracking)**: Ultralytics YOLOv8 kullanılarak Derin Öğrenme (Deep Learning) özellikleri eklendi. 
- **Çoklu Hedef (Multi-Target) Algılama**: Sistem artık çerçeve (frame) içerisindeki birden fazla nesneyi aynı anda tarayıp vurgulayabiliyor (Sarı kutular), tüm bunların içinden de sisteme gelen güven skoru en yüksek olan asıl hedefi seçip kilitleyebiliyor (Kırmızı kutu ile `[LOCKED]` yazısı).
- **Dinamik Nesne (Object) Geçişi**: YOLO modu COCO veri kümesi nesnelerini esnekçe takip edecek biçimde ayarlandı. Özel `.pt` modelleri ile Drone, İnsan Yüzü ve Araç takibine de uygun yapısı sayesinde dış eğitim verisi setleriyle (dataset) kolay adaptasyon sağlandı.
- **Bağımlılık (Dependency) Yükleme Yaması**: Windows sistemleri için sorunsuz yüklenmeyi temin etmek adına `WinError 1114` PyTorch CUDA çalışma zamanı kütüphanesi hataları ve PyQt6 DLL modül çakışmaları düzeltildi.

### [v0.2.0] - 2026-03-12
- **Güç (Power) Altyapısı Yükseltmesi**: Gimbal servo hareketlerini sabit 6V'ta izole sunabilmek için, XL4016 modülü donatılmış 12V DC güç adaptörü kullanılarak bütünleşik enerji sistemi güçlendirildi.
- **Çatı ve Kritik Hata Düzenlemeleri (Refactor & Bug Fixes)**: Yazılım iskeletini güçlendirme kapsamında detaylı hata çözümleri yapıldı:
    - Daha güvenilir donanım komutu iletimleri için seri haberleşme tutarsızlıkları giderildi.
    - Hedef üzerine görsel kilitlenmenin (target lock) kalitesi perçinlendi.
    - Daha yumuşak gimbal dönüşleri için PID kontrolcüsü stabilize edildi.
    - Genel hisiyat ve kullanıcı kolaylığı standartlarını modernize etmek üzere Grafiksel Kullanıcı Arayüzü (GUI) elden geçirildi.
    - Hedef tepki hızlarını güçlendirmek için adım atış değerleri ve ölü bölge limit parametreleri yeniden ele alındı.
