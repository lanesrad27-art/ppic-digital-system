-- ============================================================
-- PPIC Digital System — views.sql
-- View turunan untuk dashboard & inventory.
-- Dijalankan setelah schema.sql.
-- ============================================================

-- ------------------------------------------------------------
-- v_stock_status
-- Menghitung EOQ, ROP, nilai stok, kelas ABC, dan status stok
-- langsung di level database.
--   EOQ = sqrt( (2 * D * S) / H ),  H = unit_cost * holding_cost_pct/100
--   ROP = (D/365 * lead_time) + safety_stock
-- Semua pembagian dilindungi NULLIF agar tidak division-by-zero.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_stock_status CASCADE;
CREATE VIEW v_stock_status AS
WITH base AS (
    SELECT
        p.id,
        p.sku,
        p.name,
        COALESCE(c.name, '-')           AS category,
        COALESCE(s.name, '-')           AS supplier,
        p.unit,
        p.current_stock,
        p.safety_stock,
        p.annual_demand,
        p.annual_demand_source,
        p.ordering_cost,
        p.unit_cost,
        p.holding_cost_pct,
        p.lead_time_days,
        p.is_active,
        p.last_forecast_sync_at,
        -- biaya simpan per unit per tahun
        (p.unit_cost * p.holding_cost_pct / 100.0) AS holding_per_unit,
        -- nilai stok & nilai tahunan
        (p.current_stock * p.unit_cost)            AS stock_value,
        (p.annual_demand * p.unit_cost)            AS annual_value
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    LEFT JOIN suppliers  s ON p.supplier_id = s.id
    WHERE p.is_active = TRUE
),
calc AS (
    SELECT
        base.*,
        -- EOQ
        CASE
            WHEN annual_demand > 0 AND ordering_cost > 0 AND holding_per_unit > 0
            THEN ROUND(SQRT((2 * annual_demand * ordering_cost)
                            / NULLIF(holding_per_unit, 0)))
            ELSE 0
        END AS eoq,
        -- ROP
        ROUND((annual_demand / 365.0) * lead_time_days + safety_stock) AS rop
    FROM base
),
abc AS (
    SELECT
        calc.*,
        CASE WHEN SUM(annual_value) OVER () > 0
             THEN 100.0 * SUM(annual_value)
                  OVER (ORDER BY annual_value DESC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                  / SUM(annual_value) OVER ()
             ELSE 100.0
        END AS cumulative_pct
    FROM calc
)
SELECT
    id, sku, name, category, supplier, unit,
    current_stock, safety_stock, annual_demand, annual_demand_source,
    ordering_cost, unit_cost, holding_cost_pct, lead_time_days,
    last_forecast_sync_at,
    eoq, rop,
    stock_value, annual_value,
    CASE
        WHEN cumulative_pct <= 80 THEN 'A'
        WHEN cumulative_pct <= 95 THEN 'B'
        ELSE 'C'
    END AS abc_class,
    CASE
        WHEN current_stock <= safety_stock           THEN 'KRITIS'
        WHEN current_stock <= rop                     THEN 'REORDER'
        WHEN eoq > 0 AND current_stock > rop + 2 * eoq THEN 'OVERSTOCK'
        ELSE 'AMAN'
    END AS status,
    -- rekomendasi order kuantitas (0 bila tidak perlu reorder)
    CASE
        WHEN current_stock <= rop
        THEN GREATEST(eoq, rop - current_stock)
        ELSE 0
    END AS recommended_order_qty
FROM abc;

-- ------------------------------------------------------------
-- v_latest_forecast_runs
-- Ambil run forecast TERBARU per SKU (berdasarkan created_at).
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_latest_forecast_runs CASCADE;
CREATE VIEW v_latest_forecast_runs AS
SELECT DISTINCT ON (product_sku)
    id, run_id, product_sku, model_name,
    model_mape, model_mae, model_rmse, model_smape, model_bias,
    window_size, forecast_horizon, created_by, created_at
FROM forecast_runs
ORDER BY product_sku, created_at DESC, id DESC;

-- ------------------------------------------------------------
-- v_pending_forecasts
-- Forecast pending di-join dengan products untuk perbandingan demand.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_pending_forecasts CASCADE;
CREATE VIEW v_pending_forecasts AS
SELECT
    fr.run_id,
    fr.product_sku,
    fr.product_name,
    fr.model_name,
    fr.model_mape,
    MAX(fr.forecast_period)              AS latest_forecast_period,
    COUNT(*)                             AS n_months,
    SUM(fr.prediksi_demand)              AS total_forecast_demand,
    p.annual_demand                      AS current_annual_demand,
    p.annual_demand_source,
    (p.sku IS NOT NULL)                  AS sku_found
FROM forecast_results fr
LEFT JOIN products p ON p.sku = fr.product_sku
WHERE fr.sync_status = 'pending'
GROUP BY fr.run_id, fr.product_sku, fr.product_name, fr.model_name,
         fr.model_mape, p.annual_demand, p.annual_demand_source, p.sku;
