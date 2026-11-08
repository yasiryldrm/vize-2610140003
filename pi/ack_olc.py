"""
Ölçüm betiği: komut -> ACK süresi.

Pi'den ESP32'ye $LED komutu gönderir ve $ACK,LED satırı gelene kadar geçen
süreyi ölçer. Bunu N kez (varsayılan 30) tekrarlar, sonuçları CSV'ye yazar
ve özet istatistikleri ekrana basar. Ölçüm sırasında IMU satırları akmaya
devam eder; betik onları atlar.

Kullanım:
    python ack_olc.py                       # /dev/serial0, 30 tekrar
    python ack_olc.py --tekrar 50 --csv ../olcum/ack_suresi.csv
"""
import argparse
import csv
import os
import statistics
import time

import serial

from protokol import coz, kodla


def main():
    ap = argparse.ArgumentParser(description="Komut-ACK süresi ölçümü")
    ap.add_argument("--port", default="/dev/serial0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--tekrar", type=int, default=30)
    ap.add_argument("--zaman-asimi", type=float, default=1.0, help="saniye")
    ap.add_argument("--csv", default="../olcum/ack_suresi.csv")
    a = ap.parse_args()

    klasor = os.path.dirname(a.csv)
    if klasor:
        os.makedirs(klasor, exist_ok=True)

    ser = serial.Serial(a.port, a.baud, timeout=0.05)
    sureler, kayip = [], 0

    with open(a.csv, "w", newline="") as f:
        yaz = csv.writer(f)
        yaz.writerow(["tekrar", "komut", "sure_ms"])
        for i in range(1, a.tekrar + 1):
            deger = i % 2                       # LED'i sırayla yak / söndür
            ser.reset_input_buffer()            # eski satırları at
            t0 = time.perf_counter()
            ser.write(kodla("LED", deger))

            sure = None
            while time.perf_counter() - t0 < a.zaman_asimi:
                alanlar = coz(ser.readline().decode("ascii", errors="replace"))
                if alanlar == ["ACK", "LED", str(deger)]:
                    sure = (time.perf_counter() - t0) * 1000
                    break

            if sure is None:
                kayip += 1
                print(f"{i:3d}: LED,{deger}  ACK gelmedi")
                yaz.writerow([i, f"LED,{deger}", ""])
            else:
                sureler.append(sure)
                print(f"{i:3d}: LED,{deger}  {sure:6.2f} ms")
                yaz.writerow([i, f"LED,{deger}", f"{sure:.3f}"])
            time.sleep(0.2)                     # tekrarlar arasında kısa bekleme

    ser.write(kodla("LED", 0))
    ser.close()

    if sureler:
        s = sorted(sureler)
        p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
        print(f"\nn={len(s)}  kayıp={kayip}")
        print(f"ortalama={statistics.mean(s):.2f} ms  medyan={statistics.median(s):.2f} ms  "
              f"ss={statistics.pstdev(s):.2f} ms")
        print(f"min={s[0]:.2f} ms  p95={p95:.2f} ms  max={s[-1]:.2f} ms")


if __name__ == "__main__":
    main()
