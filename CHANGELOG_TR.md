# Değişiklik Günlüğü (Changelog)

<div align="right">
  🇬🇧 <a href="CHANGELOG.md">English</a> | 🇹🇷 <a href="CHANGELOG_TR.md">Türkçe</a>
</div>

Laser Gimbal Pro projesinde yapılan tüm kayda değer değişiklikler bu dosyada belgelenecektir.

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
