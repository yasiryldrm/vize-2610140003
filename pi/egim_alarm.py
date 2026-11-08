"""
Vize eklemesi (V1): Eğim alarmı.

ESP32'den gelen IMU satırlarından eğim açısını hesaplar:
    θ = atan2(ax, az)  (derece)
Gürültüyü azaltmak için son N örneğin ortalamasını kullanır.
Histerezisli eşik uygular:
    ortalama θ > UST  ->  $LED,1  (alarm başlar)
    ortalama θ < ALT  ->  $LED,0  (alarm biter)
Komut YALNIZCA durum değiştiğinde gönderilir.
Alarm olayları zaman damgasıyla ayrı bir CSV dosyasına yazılır.

Kullanım:
    python egim_alarm.py                          # /dev/serial0, ust=30, alt=25, pencere=10
    python egim_alarm.py --ust 30 --alt 25 --pencere 10
    python egim_alarm.py --ust 30 --alt 30        # histerezissiz (karşılaştırma deneyi)
    python egim_alarm.py --port /dev/pts/3        # sim_esp32.py ile donanımsız deneme
Çıkış: klavyeden q + Enter
"""
import argparse
import csv
import math
import os
import threading
import time
from collections import deque
from datetime import datetime

import serial

from protokol import coz, imu_coz, kodla


def klavye_dongusu(dur):
    """Ayrı bir iş parçacığında 'q' bekler; ana döngü seri portu okumaya devam eder."""
    while not dur.is_set():
        try:
            if input().strip() == "q":
                dur.set()
        except EOFError:
            break


def main():
    ap = argparse.ArgumentParser(description="V1 eğim alarmı")
    ap.add_argument("--port", default="/dev/serial0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--ust", type=float, default=30.0, help="alarmı başlatan açı (derece)")
    ap.add_argument("--alt", type=float, default=25.0, help="alarmı bitiren açı (derece)")
    ap.add_argument("--pencere", type=int, default=10, help="ortalamadaki örnek sayısı")
    ap.add_argument("--csv", default="../olcum/egim.csv", help="her örneğin kaydı")
    ap.add_argument("--olay", default="../olcum/olaylar.csv", help="alarm olayları günlüğü")
    ap.add_argument("--yazdir", type=int, default=25, help="her N örnekte bir ekrana yaz")
    a = ap.parse_args()

    if a.alt > a.ust:
        ap.error("--alt, --ust değerinden büyük olamaz")

    for yol in (a.csv, a.olay):
        klasor = os.path.dirname(yol)
        if klasor:
            os.makedirs(klasor, exist_ok=True)

    ser = serial.Serial(a.port, a.baud, timeout=1)
    ser.reset_input_buffer()

    # Başlangıç durumu güvenli olsun: LED kapalı
    ser.write(kodla("LED", 0))

    dur = threading.Event()
    threading.Thread(target=klavye_dongusu, args=(dur,), daemon=True).start()

    son_acilar = deque(maxlen=a.pencere)   # kayan pencere: en eski örnek otomatik düşer
    alarm = False                          # şu anki durum (LED açık mı)
    gonderim_zamani = None                 # son komutun gönderildiği an (ACK süresi için)
    sayac = {"imu": 0, "hata": 0, "led_degisim": 0}
    t0 = time.monotonic()

    print(f"{a.port} dinleniyor | üst={a.ust}° alt={a.alt}° pencere={a.pencere} | çıkış: q")

    with open(a.csv, "w", newline="") as f_ornek, open(a.olay, "w", newline="") as f_olay:
        ornek = csv.writer(f_ornek)
        olay = csv.writer(f_olay)
        ornek.writerow(["pi_zaman_s", "esp_zaman_ms", "ax_g", "az_g",
                        "aci_ham_deg", "aci_ort_deg", "alarm"])
        olay.writerow(["tarih_saat", "pi_zaman_s", "esp_zaman_ms", "olay",
                       "aci_ort_deg", "ack_suresi_ms"])

        while not dur.is_set():
            satir = ser.readline().decode("ascii", errors="replace")
            if not satir:
                continue
            alanlar = coz(satir)
            if alanlar is None:                # biçim veya checksum hatası
                sayac["hata"] += 1
                continue

            # ESP32'nin komut yanıtları: ACK süresini ölç ve olay günlüğüne ekle
            if alanlar[0] in ("ACK", "ERR"):
                ack_ms = ""
                if gonderim_zamani is not None and alanlar[0] == "ACK":
                    ack_ms = f"{(time.perf_counter() - gonderim_zamani) * 1000:.1f}"
                    gonderim_zamani = None
                print(f"ESP32: {','.join(alanlar)}  {ack_ms and ack_ms + ' ms'}")
                olay.writerow([datetime.now().isoformat(timespec="milliseconds"),
                               f"{time.monotonic() - t0:.3f}", "", ",".join(alanlar), "", ack_ms])
                f_olay.flush()
                continue

            if alanlar[0] != "IMU" or len(alanlar) != 8:
                continue

            # 1) Eğim açısı: θ = atan2(ax, az), radyandan dereceye
            t_ms, ivme, _ = imu_coz(alanlar)
            ax, _, az = ivme
            aci = math.degrees(math.atan2(ax, az))

            # 2) Son N örneğin ortalaması (gürültü süzme)
            son_acilar.append(aci)
            ort = sum(son_acilar) / len(son_acilar)

            # 3) Histerezisli karar; komut yalnızca durum değişince gönderilir
            yeni = alarm
            if not alarm and ort > a.ust:
                yeni = True
            elif alarm and ort < a.alt:
                yeni = False

            if yeni != alarm:
                alarm = yeni
                ser.write(kodla("LED", int(alarm)))
                gonderim_zamani = time.perf_counter()
                sayac["led_degisim"] += 1
                ad = "ALARM_BASLADI" if alarm else "ALARM_BITTI"
                olay.writerow([datetime.now().isoformat(timespec="milliseconds"),
                               f"{time.monotonic() - t0:.3f}", t_ms, ad, f"{ort:.2f}", ""])
                f_olay.flush()
                print(f">>> {ad}  θ_ort={ort:+.1f}°")

            # 4) Her örneği kaydet
            ornek.writerow([f"{time.monotonic() - t0:.3f}", t_ms, f"{ax:.4f}", f"{az:.4f}",
                            f"{aci:.2f}", f"{ort:.2f}", int(alarm)])
            sayac["imu"] += 1
            if sayac["imu"] % a.yazdir == 0:
                hiz = sayac["imu"] / (time.monotonic() - t0)
                print(f"t={t_ms:8d} ms  θ={aci:+6.1f}°  θ_ort={ort:+6.1f}°  "
                      f"alarm={'AÇIK ' if alarm else 'kapalı'}  {hiz:5.1f} örnek/s  "
                      f"hatalı={sayac['hata']}")

    ser.write(kodla("LED", 0))                 # çıkarken LED'i söndür
    ser.close()
    print("Özet:", sayac)


if __name__ == "__main__":
    main()
