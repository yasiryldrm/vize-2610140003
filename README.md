# Vize Projesi — ESP32-S3 ile Raspberry Pi Haberleşmesi ve Eğim Alarmı

**Öğrenci:** Yasir YILDIRIM — 2610140003
**Ders:** İleri Gömülü Sistemler (Yüksek Lisans)

ESP32-S3, MPU-6050 sensöründen 50 Hz'de okuduğu ivme ve açısal hız verisini
UART üzerinden checksum'lı metin satırları olarak Raspberry Pi'ye gönderir;
Pi veriyi doğrulayıp kaydeder ve ESP32'ye komut gönderir.
**Seçilen ekleme: V1 — Eğim alarmı.** Pi, son 10 örneğin ivme bileşenlerinin
ortalamasından eğim açısını hesaplar, histerezisli eşik uygular
(30° üstü → `$LED,1`, 25° altı → `$LED,0`), komutu yalnızca durum değiştiğinde
gönderir ve alarm olaylarını zaman damgasıyla ayrı bir dosyaya kaydeder.
Eğim, sensörün Z ekseni ile yerçekimi arasındaki açıdır:
θ = atan2(√(ax² + ay²), az) — sensör hangi yöne eğilirse eğilsin 0° (düz) … 90° (dik) … 180° (ters).
Yönergedeki θ = atan2(ax, az) formülü `--tek-eksen` seçeneğiyle kullanılabilir.

**Sonuçlar:** 60 sn'de 3.021 örnek, 0 hatalı satır, periyot 20,0 ± 0,58 ms ·
komut → ACK medyan 3,38 ms · dik konumda θ ≈ 90,3° · histerezis LED titremesini
112'den 20 değişime (≈ 6 kat) indirdi. Ayrıntılar: `olcum/BENIOKU.md`, `rapor/`.

---

## 1. Malzeme listesi

| Malzeme | Adet | Not |
|---|---|---|
| ESP32-S3-DevKitC-1 (N16R8) | 1 | 16 MB Flash, 8 MB PSRAM |
| Raspberry Pi 4 Model B | 1 | Raspberry Pi OS 64-bit, 5,1 V / 3 A adaptör |
| GY-521 ivme/dönü sensör kartı | 1 | Kartın yongası MPU-6500 (WHO_AM_I = 0x70); kullanılan registerlar MPU-6050 ile aynı |
| 5 mm kırmızı LED | 1 | Kendinden flaşörlü tip: GPIO4 = 1 iken yanıp söner |
| 330 Ω direnç | 1 | LED akım sınırlama |
| Breadboard | 1 | Mavi (−) hat ortak GND olarak kullanıldı |
| Jumper kablo | ~10 | Dişi-dişi ve dişi-erkek |
| USB-C veri kablosu | 1 | ESP32'nin USB girişi |

## 2. Bağlantı tablosu

Kartlar ayrı USB kablolarından beslenir. Pi'nin 5V pinlerine (pin 2 ve 4)
hiçbir şey bağlanmaz. Tüm GND'ler breadboard'un mavi (−) hattında birleşir.

| ESP32-S3 | Bağlandığı yer | Açıklama |
|---|---|---|
| GPIO17 (UART1 TX) | Pi pin 10 — GPIO15 RXD | çapraz bağlantı |
| GPIO18 (UART1 RX) | Pi pin 8 — GPIO14 TXD | çapraz bağlantı |
| GND | Breadboard GND hattı ← Pi pin 6 (GND) | ortak toprak |
| 3V3 | MPU VCC | sensör beslemesi |
| GND hattı | MPU GND | |
| GPIO8 | MPU SDA | I²C veri |
| GPIO9 | MPU SCL | I²C saat |
| GPIO4 | 330 Ω → LED uzun bacak; LED kısa bacak → GND hattı | alarm göstergesi |

## 3. ESP32 tarafı (ESP-IDF v6.1)

ESP-IDF, yolda boşluk ve Türkçe karakter içeren klasörlerde derleme yapamaz;
`esp32/` klasörünü ör. `C:\esp32_vize` gibi bir konuma kopyalayıp oradan
derleyin. ESP-IDF terminalinde:

```
cd C:\esp32_vize
idf.py set-target esp32s3
idf.py build
idf.py -p COMx flash monitor
```

- COM numarası: `[System.IO.Ports.SerialPort]::GetPortNames()`
- Yükleme bağlanamazsa: BOOT basılı → RST bas-bırak → BOOT bırak → tekrar `flash`.
- Monitörde `MPU-6050 bulundu` görülmeli; sensör yoksa firmware sentetik veri gönderir.
- Monitörden çıkış: Ctrl+T, ardından Ctrl+X.

## 4. Raspberry Pi tarafı

Bir kez yapılacak hazırlık:

```bash
sudo raspi-config nonint do_serial_cons 1   # seri hattaki login konsolunu kapat
sudo raspi-config nonint do_serial_hw 0     # UART donanımını aç
sudo reboot
python3 -m venv ~/yz
source ~/yz/bin/activate
pip install pyserial matplotlib
```

Çalıştırma (`pi/` klasöründe, `(yz)` ortamı açıkken):

```bash
mkdir -p ../olcum

# Temel sistem: veri akışı, kayıt, komut
python alici.py --csv ../olcum/kayit_60s.csv
#   klavyeden: led 1 | led 0 | hiz 10 | hiz 100 | q

# V1 eklemesi: eğim alarmı
python egim_alarm.py                           # üst=30°, alt=25°, pencere=10
python egim_alarm.py --ust 30 --alt 30 --pencere 1   # histerezissiz karşılaştırma
python egim_alarm.py --tek-eksen                       # yönergedeki atan2(ax, az) formülü
#   çıktılar: ../olcum/egim.csv (her örnek), ../olcum/olaylar.csv (alarm olayları)

# Ölçüm: komut -> ACK süresi (30 tekrar)
python ack_olc.py --tekrar 30

# Donanımsız deneme (sanal seri port)
python sim_esp32.py &            # "Sanal port: /dev/pts/N" yazar
python alici.py --port /dev/pts/N
```

## 5. Protokol

Her satır `$GOVDE*HH\r\n` biçimindedir; `HH`, `$` ile `*` arasındaki
karakterlerin XOR'unun iki haneli onaltılık gösterimidir. Hız 115200 baud, 8N1.

| Yön | Mesaj | Alanlar | Açıklama |
|---|---|---|---|
| ESP32 → Pi | `$IMU,t,ax,ay,az,gx,gy,gz*HH` | t: ms; ivme ham (16384 LSB/g); dönü ham (131 LSB/(°/s)) | Ölçüm, varsayılan 50 Hz |
| ESP32 → Pi | `$ACK,LED,<0\|1>*HH` | | LED komutu uygulandı |
| ESP32 → Pi | `$ACK,HIZ,<1..100>*HH` | | Örnekleme hızı değişti |
| ESP32 → Pi | `$ERR,BICIM*HH` | | Satır `$` ile başlamıyor, `*` ya da komut ile değer arasındaki `,` yok |
| ESP32 → Pi | `$ERR,CHECKSUM*HH` | | Checksum tutmuyor |
| ESP32 → Pi | `$ERR,KOMUT*HH` | | Bilinmeyen komut ya da değer aralık dışı |
| ESP32 → Pi | `$ERR,I2C*HH` | | Sensör okunamadı |
| Pi → ESP32 | `$LED,<0\|1>*HH` | | LED'i söndür / yak (eğim alarmı bunu kullanır) |
| Pi → ESP32 | `$HIZ,<1..100>*HH` | Hz | Örnekleme hızı |

V1 eklemesi protokole yeni mesaj eklemez; mevcut `$LED` komutunu, Pi'de
veriden verilen karara göre ve **yalnızca durum değiştiğinde** gönderir.

Örnek: `$LED,1*50`, `$HIZ,25*70`, `$ACK,LED,1*35`.

## 6. Klasör yapısı

```
esp32/   ESP32-S3 firmware (şablon, değiştirilmedi)
pi/      protokol.py, alici.py, egim_alarm.py (V1), ack_olc.py (ölçüm), sim_esp32.py, canli_grafik.py
olcum/   ölçüm kayıtları (CSV) ve çıktılar
rapor/   rapor.pdf ve şekiller
```
