# Ölçüm kayıtları

| Dosya | Ölçüm | Özet |
|---|---|---|
| `kayit_60s.csv` | 60 sn kayıt, `alici.py`, sensör masada | 3.021 örnek, 60,4 s, 0 hatalı, periyot 20,0 ± 0,58 ms |
| `hiz_testi.csv` | `hiz 10` → `hiz 100` → `hiz 50` | periyot 100,0 / 10,0 / 20,0 ms |
| `ack_suresi.csv` | `ack_olc.py --tekrar 30` | ort. 3,88 ms, medyan 3,38 ms, p95 5,92 ms, kayıp 0 |
| `egim.csv`, `olaylar.csv` | `egim_alarm.py`: düz → yarı yatık → dik → düz | alarm 30,3°'de açıldı, 24,1°'de kapandı; dikte θ ≈ 90,3° |
| `egim_hist_yok.csv`, `olaylar_hist_yok.csv` | `--ust 30 --alt 30 --pencere 1`, eşik çevresinde el hareketi | 32,8 s'de 112 LED değişimi |
| `egim_hist_var.csv`, `olaylar_hist_var.csv` | varsayılan (30/25°, 10 örnek), aynı hareket | 35,5 s'de 20 LED değişimi |
