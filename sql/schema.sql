-- ============================================================
-- PPIC Digital System — schema.sql
-- Skema utama PostgreSQL.
-- Idempoten: aman dijalankan berulang (CREATE TABLE IF NOT EXISTS).
-- ============================================================

-- ------------------------------------------------------------
-- 1. USERS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory_users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(50)  UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,            -- bcrypt / pbkdf2 hash
    role        VARCHAR(20)  DEFAULT 'viewer'
                CHECK (role IN ('admin','planner','warehouse','viewer')),
    full_name   VARCHAR(100),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 2. CATEGORIES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(255),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 3. SUPPLIERS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(150) UNIQUE NOT NULL,
    contact_person VARCHAR(100),
    phone          VARCHAR(30),
    email          VARCHAR(120),
    lead_time_days INTEGER DEFAULT 7 CHECK (lead_time_days >= 0),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 4. PRODUCTS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id                   SERIAL PRIMARY KEY,
    sku                  VARCHAR(50) UNIQUE NOT NULL,
    name                 VARCHAR(150) NOT NULL,
    category_id          INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    supplier_id          INTEGER REFERENCES suppliers(id)  ON DELETE SET NULL,
    unit                 VARCHAR(20) DEFAULT 'pcs',
    current_stock        NUMERIC(14,2) DEFAULT 0 CHECK (current_stock >= 0),
    safety_stock         NUMERIC(14,2) DEFAULT 0 CHECK (safety_stock  >= 0),
    annual_demand        NUMERIC(14,2) DEFAULT 0 CHECK (annual_demand  >= 0),
    annual_demand_source VARCHAR(20)  DEFAULT 'manual'
                         CHECK (annual_demand_source IN ('manual','forecast')),
    ordering_cost        NUMERIC(14,2) DEFAULT 0 CHECK (ordering_cost  >= 0),
    unit_cost            NUMERIC(14,2) DEFAULT 0 CHECK (unit_cost      >= 0),
    holding_cost_pct     NUMERIC(6,2)  DEFAULT 20 CHECK (holding_cost_pct >= 0),
    lead_time_days       INTEGER DEFAULT 7 CHECK (lead_time_days >= 0),
    is_active            BOOLEAN DEFAULT TRUE,
    last_forecast_sync_at TIMESTAMP,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 5. STOCK TRANSACTIONS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_transactions (
    id               SERIAL PRIMARY KEY,
    product_id       INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    transaction_type VARCHAR(3) NOT NULL CHECK (transaction_type IN ('IN','OUT')),
    quantity         NUMERIC(14,2) NOT NULL CHECK (quantity > 0),
    unit_price       NUMERIC(14,2) DEFAULT 0 CHECK (unit_price >= 0),
    reference_no     VARCHAR(50),
    notes            VARCHAR(255),
    created_by       VARCHAR(50),
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 6. DEMAND HISTORY
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS demand_history (
    id            SERIAL PRIMARY KEY,
    product_sku   VARCHAR(50) NOT NULL,
    demand_period DATE NOT NULL,                 -- biasanya awal bulan
    demand_qty    NUMERIC(14,2) NOT NULL CHECK (demand_qty >= 0),
    source        VARCHAR(20) DEFAULT 'manual',  -- manual / import / transaction
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 7. FORECAST RUNS  (metadata 1 baris per produk per run)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forecast_runs (
    id               SERIAL PRIMARY KEY,
    run_id           VARCHAR(40) NOT NULL,        -- UUID per eksekusi forecast
    product_sku      VARCHAR(50) NOT NULL,
    model_name       VARCHAR(40),
    model_mape       NUMERIC(10,4),
    model_mae        NUMERIC(14,4),
    model_rmse       NUMERIC(14,4),
    model_smape      NUMERIC(10,4),
    model_bias       NUMERIC(14,4),
    window_size      INTEGER,
    forecast_horizon INTEGER,
    created_by       VARCHAR(50),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 8. FORECAST RESULTS  (1 baris per bulan hasil forecast)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forecast_results (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(40) NOT NULL,
    product_sku     VARCHAR(50) NOT NULL,
    product_name    VARCHAR(150),
    forecast_period DATE,                         -- bulan yang diprediksi
    bulan_ke        INTEGER,
    prediksi_demand NUMERIC(14,2),
    lower_bound     NUMERIC(14,2),
    upper_bound     NUMERIC(14,2),
    model_name      VARCHAR(40),
    model_mape      NUMERIC(10,4),
    sync_status     VARCHAR(20) DEFAULT 'pending'
                    CHECK (sync_status IN ('pending','synced','rejected')),
    synced_at       TIMESTAMP,
    synced_by       VARCHAR(50),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 9. FORECAST SYNC LOGS  (audit trail sinkronisasi demand)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forecast_sync_logs (
    id                SERIAL PRIMARY KEY,
    run_id            VARCHAR(40),
    product_sku       VARCHAR(50) NOT NULL,
    old_annual_demand NUMERIC(14,2),
    new_annual_demand NUMERIC(14,2),
    forecast_date     DATE,
    synced_by         VARCHAR(50),
    synced_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- INDEXES
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_products_sku
    ON products (sku);
CREATE INDEX IF NOT EXISTS idx_demand_history_sku_period
    ON demand_history (product_sku, demand_period);
CREATE INDEX IF NOT EXISTS idx_forecast_results_sku_date
    ON forecast_results (product_sku, forecast_period);
CREATE INDEX IF NOT EXISTS idx_forecast_results_run_id
    ON forecast_results (run_id);
CREATE INDEX IF NOT EXISTS idx_forecast_results_sync_status
    ON forecast_results (sync_status);

-- Index pendukung tambahan (tidak wajib, mempercepat join umum).
CREATE INDEX IF NOT EXISTS idx_stock_transactions_product
    ON stock_transactions (product_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_run_id
    ON forecast_runs (run_id);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_sku
    ON forecast_runs (product_sku);
