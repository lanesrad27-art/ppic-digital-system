# 🏭 PPIC Digital System

Aplikasi **Production Planning & Inventory Control** berbasis Streamlit yang
menggabungkan **Demand Forecasting**, **Inventory Control**, dan **Reorder
Recommendation** dalam satu sistem terintegrasi.

Proyek ini adalah penggabungan & perapian dari dua aplikasi terpisah
(Inventory Dashboard + PPIC Forecasting) menjadi satu sistem multi-halaman.

---

## ✨ Fitur

| Modul | Deskripsi |
|---|---|
| 🏠 **Dashboard** | KPI ringkas (nilai inventory, stok kritis, reorder, overstock) + grafik status & ABC |
| 📦 **Inventory** | Tabel produk dengan EOQ/ROP/ABC, filter kategori/supplier/status, export CSV/Excel, import CSV |
| 🔄 **Stock Transactions** | Input transaksi IN/OUT (role warehouse/admin) dengan proteksi stok negatif |
| 📈 **Demand Forecasting** | ARIMA, ETS/Holt-Winters, XGBoost/Gradient Boosting, Croston/TSB + **Auto Select Best Model** |
| 🔗 **Forecast Sync** | Sinkronkan hasil forecast ke annual demand produk + audit log + rollback |
| 📊 **Forecast Insight** | Analisis perubahan demand, risiko stockout, rekomendasi EOQ/ROP terkini |
| 🧮 **EOQ / ROP Calculator** | Kalkulator interaktif + visualisasi siklus persediaan (sawtooth) |
| 👥 **User Management** | Kelola user & role (khusus admin) |
| 🩺 **System Health** | Status DB, jumlah baris tabel, cek ketersediaan paket model, inisialisasi & seed DB |

### Model Forecasting
- **ARIMA** — auto order via grid search AIC, uji stasioneritas ADF, confidence interval.
- **ETS / Holt-Winters** — trend + musiman (seasonal_periods=12 bila data ≥24 bulan).
- **XGBoost** — lag features; otomatis fallback ke `GradientBoostingRegressor` bila XGBoost tidak terinstal.
- **Croston / TSB** — khusus intermittent demand (spare part dengan banyak nilai nol).
- **Auto Select** — membandingkan MAE/RMSE/MAPE/sMAPE/Bias dan memilih model terbaik.

---

## 📁 Struktur Proyek

```
ppic-digital-system/
├─ app.py                       # Landing + login (tanpa logika bisnis)
├─ requirements.txt
├─ README.md
├─ .gitignore
├─ pages/
│  ├─ 1_🏠_Dashboard.py
│  ├─ 2_📦_Inventory.py
│  ├─ 3_🔄_Stock_Transactions.py
│  ├─ 4_📈_Demand_Forecasting.py
│  ├─ 5_🔗_Forecast_Sync.py
│  ├─ 6_📊_Forecast_Insight.py
│  ├─ 7_🧮_EOQ_ROP_Calculator.py
│  ├─ 8_Users_Management.py
│  └─ 9_System_Health.py
├─ modules/
│  ├─ auth.py                  # login, role & permission (bcrypt + fallback)
│  ├─ database.py              # koneksi PostgreSQL (SQLAlchemy)
│  ├─ inventory_calculations.py# EOQ, ROP, safety stock, ABC, turnover
│  ├─ inventory_service.py     # query produk & transaksi stok
│  ├─ forecast_service.py      # simpan/sync/rollback forecast
│  ├─ arima_forecaster.py
│  ├─ ets_forecaster.py
│  ├─ xgboost_forecaster.py
│  ├─ croston_forecaster.py
│  ├─ forecasting_metrics.py   # MAE, RMSE, MAPE, sMAPE, Bias
│  ├─ validators.py
│  └─ formatting.py
├─ sql/
│  ├─ schema.sql               # tabel + index (idempoten)
│  ├─ views.sql                # v_stock_status, v_latest_forecast_runs, v_pending_forecasts
│  └─ seed_data.sql            # data contoh
├─ data/
│  ├─ sample_inventory.csv
│  └─ sample_demand_history.csv
├─ tests/
│  ├─ test_inventory_calculations.py
│  └─ test_forecasting_metrics.py
└─ .streamlit/
   └─ secrets.example.toml
```

---

## 🚀 Cara Menjalankan

### 1. Prasyarat
- Python 3.10+
- PostgreSQL 13+ (lokal atau cloud, mis. Supabase/Neon)

### 2. Install dependency
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
> XGBoost opsional. Tanpa XGBoost, sistem otomatis memakai
> `GradientBoostingRegressor` dari scikit-learn.

### 3. Konfigurasi database
```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
# edit .streamlit/secrets.toml -> isi kredensial database
```

### 4. Siapkan database
Skema & view dibuat otomatis saat aplikasi pertama dijalankan
(`schema.sql` + `views.sql`). Data contoh bisa dimuat dari halaman
**System Health** (tombol *Inisialisasi Skema* & *Load Seed Data*), atau manual:
```bash
psql "$DATABASE_URL" -f sql/schema.sql
psql "$DATABASE_URL" -f sql/views.sql
psql "$DATABASE_URL" -f sql/seed_data.sql
```

### 5. Jalankan aplikasi
```bash
streamlit run app.py
```

### 6. Login pertama
- Isi `default_admin_password` di `secrets.toml` agar user `admin` dibuat otomatis, **atau**
- Buat admin pertama langsung di tabel `inventory_users`.

---

## 🔑 Role & Hak Akses

| Role | Akses |
|---|---|
| **admin** | Semua modul + User Management |
| **planner** | Dashboard, Inventory, EOQ/ROP, Forecasting, Forecast Sync, Insight |
| **warehouse** | Dashboard, Inventory, EOQ/ROP, Stock Transactions |
| **viewer** | Dashboard, Inventory (lihat saja) |

---

## 🔁 Alur Data

```
Demand History → Forecasting → Forecast Results → Sync Annual Demand
              → EOQ/ROP → Reorder Recommendation
```

---

## 🖼️ Screenshot & Demo Flow

> Letakkan screenshot Anda di `docs/screenshots/` lalu sematkan, contoh:
> `![Dashboard](docs/screenshots/dashboard.png)`

| Halaman | Berkas screenshot |
|---|---|
| Dashboard | `docs/screenshots/dashboard.png` |
| Demand Forecasting | `docs/screenshots/forecasting.png` |
| Forecast Sync | `docs/screenshots/forecast_sync.png` |
| EOQ/ROP Calculator | `docs/screenshots/eoq_rop.png` |

### Demo Flow (alur demonstrasi ~5 menit)
1. **Login** sebagai admin.
2. **System Health** → klik *Inisialisasi Skema* lalu *Load Seed Data* untuk mengisi data contoh.
3. **Dashboard** → tinjau KPI: nilai inventory, stok kritis, item perlu reorder.
4. **Demand Forecasting** → pilih `BM-001`, horizon 6 bulan, *Auto Select Best Model* → *Jalankan Forecast* → cek metrik & badge kualitas MAPE → *Save Forecast*.
5. **Forecast Sync** → bandingkan demand lama vs baru → *Sync* per item atau *Sync All* → cek audit log & coba *Rollback*.
6. **Forecast Insight** → lihat perubahan demand & rekomendasi reorder berbasis forecast.
7. **EOQ/ROP Calculator** → hitung EOQ, ROP, safety stock untuk skenario manual.
8. **Inventory** → filter, *Export Excel*, atau *Import Inventory CSV*.
9. **User Management** → tambah user planner/warehouse & atur role.

---

## 🧪 Testing
```bash
pip install pytest
pytest tests/ -q
```
Test mencakup kalkulasi inventory (EOQ/ROP/ABC/safety stock/turnover) dan
metrik forecasting (MAE/RMSE/MAPE/sMAPE/Bias) serta Croston/TSB.

---

## ⚠️ Catatan Keamanan
- Password di-hash dengan **bcrypt** (fallback PBKDF2-HMAC-SHA256 bila bcrypt tidak ada).
- **Tidak ada** password default yang di-hardcode — admin awal hanya dibuat bila Anda mengisi `default_admin_password`.
- `secrets.toml` sudah masuk `.gitignore`; jangan commit kredensial.
