# 🎯 Lazer Gimbal (HSS) - Fütüristik WebUI & 3D Telemetri Sistemi

TEKNOFEST Hava Savunma Sistemi (HSS) ve Lazer Gimbal projesi için geliştirilmiş **Askeri Standartta Fütüristik HUD (Heads-Up Display)**, **Three.js tabanlı 3D Donanım İkizi** ve **Ultra Düşük Gecikmeli Web İstasyonu**.

---

## ✨ Öne Çıkan Özellikler

- 🛸 **3D Donanım İkizi (Three.js):** Gimbal donanımından gelen Pitch/Yaw/Roll telemetrisiyle eşzamanlı dönen 3D taret modeli, dinamik lazer ışını huzmesi ve hedef vektörü.
- 🎯 **Fütüristik HUD & Nişangah (Canvas):** Yapay ufuk (Attitude Indicator), 360° Azimut pusula şeridi, hedef kilitlenme halkaları (`TARGET LOCKED`), Kalman filtreli lead-angle nişangahı.
- 🔊 **Taktiksel Ses Efektleri (Web Audio API):** Hedefe kilitlenme (`Lock-on tone`), lazer ateşleme ve sistem alarm sesleri (açılıp kapatılabilir).
- ⚡ **Düşük Gecikmeli WebSocket & MJPEG Stream:** FastAPI üzerinden ~30-60 FPS telemetri ve canlı video akışı.
- 🎛️ **Canlı PID & Filtre Ayarlama:** Arayüz üzerinden Kp, Ki, Kd ve Deadzone değerlerini canlı olarak ayarlayıp doğrudan STM32'ye aktarma.
- ⌨️ **Taktiksel Klavye Kısayolları:**
  - `W / A / S / D` veya `Ok Tuşları`: Manuel Gimbal Yönlendirme
  - `Space (Boşluk)`: Lazer Ateşleme (Lazer silahı aktifken)
  - `C`: Gimbal'ı Merkeze Sıfırlama (`(0, 0)`)
  - `Esc`: Acil Durum Durdurma (`EMERGENCY STOP / !STOP`)

---

## 🚀 Hızlı Başlatma

### Tek Komutla Başlatma:

#### macOS / Linux:
```bash
./run_webui.sh
```

#### Windows:
```cmd
run_webui.bat
```

Sunucu açıldıktan sonra tarayıcınızdan **`http://localhost:8000`** adresine gidin.

---

### Geliştirici (Dev) Modu:

1. **Python Backend Başlat:**
   ```bash
   source .venv/bin/activate
   python3 web_server.py --port 8000
   ```

2. **React Frontend (Hot-Reloading):**
   ```bash
   cd webui
   npm run dev
   ```
   Arayüz **`http://localhost:3000`** adresinde çalışacaktır (API istekleri otomatik olarak 8000 portuna yönlendirilir).

---

## 🏗️ Mimari ve Dizin Yapısı

- `web_server.py`: FastAPI backend, WebSocket telemetri hub'ı ve MJPEG video akış servisi.
- `core/web_bridge.py`: GimbalController, VisionWorker ve SerialThread'i WebUI'a bağlayan köprü.
- `webui/`: React 19 + Vite + TypeScript + Tailwind CSS + Three.js kaynak kodları.
  - `src/components/Gimbal3DView.tsx`: Three.js 3D Gimbal/Taret bileşeni.
  - `src/components/HudOverlay.tsx`: Canvas HUD ve nişangah katmanı.
  - `src/components/VideoFeed.tsx`: Video oynatıcı ve HUD entegrasyonu.
  - `src/components/TelemetryPanel.tsx`: Donanım, sensör ve STM32 telemetri göstergeleri.
  - `src/components/ControlCenter.tsx`: Lazer kontrolü, D-Pad ve mod seçici.
  - `src/components/PidTuningModal.tsx`: Canlı PID ayar penceresi.
  - `src/hooks/useGimbalSocket.ts`: Çift yönlü WebSocket istemci kancası.
  - `src/utils/audioEffects.ts`: Web Audio API taktiksel ses sentezleyicisi.
