-- ============================================================
-- PPIC Digital System — seed_data.sql
-- Data contoh untuk pengujian. Idempoten (ON CONFLICT DO NOTHING).
-- Jalankan setelah schema.sql.
-- Catatan: admin awal TIDAK dibuat di sini — gunakan
--          default_admin_password di secrets (lihat modules/auth.py).
-- ============================================================

-- ------------------------------------------------------------
-- CATEGORIES
-- ------------------------------------------------------------
INSERT INTO categories (name, description) VALUES
    ('Bahan Baku',  'Material mentah produksi'),
    ('Komponen',    'Komponen rakitan'),
    ('Consumable',  'Barang habis pakai'),
    ('Spare Part',  'Suku cadang mesin')
ON CONFLICT (name) DO NOTHING;

-- ------------------------------------------------------------
-- SUPPLIERS
-- ------------------------------------------------------------
INSERT INTO suppliers (name, contact_person, phone, email, lead_time_days) VALUES
    ('PT Baja Utama',     'Andi',  '021-5550100', 'sales@bajautama.co.id',  5),
    ('CV Maju Jaya',      'Budi',  '021-5550200', 'order@majujaya.co.id',   3),
    ('UD Teknik Makmur',  'Citra', '021-5550300', 'cs@teknikmakmur.co.id',  7)
ON CONFLICT (name) DO NOTHING;

-- ------------------------------------------------------------
-- PRODUCTS
-- category_id & supplier_id diambil via sub-select agar tahan
-- terhadap perbedaan urutan SERIAL.
-- ------------------------------------------------------------
INSERT INTO products
    (sku, name, category_id, supplier_id, unit,
     current_stock, safety_stock, annual_demand, annual_demand_source,
     ordering_cost, unit_cost, holding_cost_pct, lead_time_days, is_active)
VALUES
    ('BM-001', 'Plat Besi 3mm',        (SELECT id FROM categories WHERE name='Bahan Baku'), (SELECT id FROM suppliers WHERE name='PT Baja Utama'),    'lembar',  42,  80,  1200, 'manual', 75000, 185000, 20, 5, TRUE),
    ('BM-002', 'Baja Hollow 40x40',    (SELECT id FROM categories WHERE name='Bahan Baku'), (SELECT id FROM suppliers WHERE name='PT Baja Utama'),    'batang', 125,  50,   800, 'manual', 75000,  95000, 20, 5, TRUE),
    ('BM-003', 'Pipa Galvanis 1 inch', (SELECT id FROM categories WHERE name='Bahan Baku'), (SELECT id FROM suppliers WHERE name='PT Baja Utama'),    'batang',  67,  30,   500, 'manual', 75000, 145000, 20, 5, TRUE),
    ('KP-001', 'Baut M8 x 25',         (SELECT id FROM categories WHERE name='Komponen'),   (SELECT id FROM suppliers WHERE name='CV Maju Jaya'),     'pcs',   1250, 500, 15000, 'manual', 75000,    850, 20, 7, TRUE),
    ('KP-002', 'Mur Hex M10',          (SELECT id FROM categories WHERE name='Komponen'),   (SELECT id FROM suppliers WHERE name='CV Maju Jaya'),     'pcs',    180, 250, 12000, 'manual', 75000,    650, 20, 7, TRUE),
    ('KP-003', 'Seal Karet 10mm',      (SELECT id FROM categories WHERE name='Komponen'),   (SELECT id FROM suppliers WHERE name='CV Maju Jaya'),     'pcs',    680, 200,  5000, 'manual', 75000,   4500, 20, 3, TRUE),
    ('CN-001', 'Cat Primer Abu',       (SELECT id FROM categories WHERE name='Consumable'), (SELECT id FROM suppliers WHERE name='CV Maju Jaya'),     'kg',      95, 100,   600, 'manual', 75000,  35000, 20, 3, TRUE),
    ('CN-002', 'Elektroda Las 3.2mm',  (SELECT id FROM categories WHERE name='Consumable'), (SELECT id FROM suppliers WHERE name='CV Maju Jaya'),     'kg',     380, 150,  2400, 'manual', 75000,  28000, 20, 7, TRUE),
    ('SP-001', 'V-Belt A-48',          (SELECT id FROM categories WHERE name='Spare Part'), (SELECT id FROM suppliers WHERE name='UD Teknik Makmur'), 'pcs',     15,  10,   120, 'manual', 75000, 125000, 20, 3, TRUE),
    ('SP-002', 'Bearing 6205',         (SELECT id FROM categories WHERE name='Spare Part'), (SELECT id FROM suppliers WHERE name='UD Teknik Makmur'), 'pcs',     28,  15,   180, 'manual', 75000,  85000, 20, 5, TRUE)
ON CONFLICT (sku) DO NOTHING;

-- ------------------------------------------------------------
-- DEMAND HISTORY (24 bulan untuk 3 SKU utama — cukup untuk seasonal)
-- Dibuat via generate_series agar ringkas; pola = base + tren + musiman.
-- ------------------------------------------------------------
INSERT INTO demand_history (product_sku, demand_period, demand_qty, source)
SELECT
    'BM-001',
    (DATE '2024-01-01' + (g || ' month')::interval)::date,
    GREATEST(0, ROUND(100 + 2*g + 15*SIN(g/2.0) + (g % 5) * 4))::numeric,
    'manual'
FROM generate_series(0, 23) AS g
ON CONFLICT DO NOTHING;

INSERT INTO demand_history (product_sku, demand_period, demand_qty, source)
SELECT
    'KP-001',
    (DATE '2024-01-01' + (g || ' month')::interval)::date,
    GREATEST(0, ROUND(1200 + 10*g + 120*SIN(g/3.0)))::numeric,
    'manual'
FROM generate_series(0, 23) AS g
ON CONFLICT DO NOTHING;

-- SP-001 = intermittent demand (banyak nol) untuk menguji Croston/TSB.
INSERT INTO demand_history (product_sku, demand_period, demand_qty, source)
SELECT
    'SP-001',
    (DATE '2024-01-01' + (g || ' month')::interval)::date,
    (CASE WHEN g % 3 = 0 THEN (5 + (g % 4)) ELSE 0 END)::numeric,
    'manual'
FROM generate_series(0, 23) AS g
ON CONFLICT DO NOTHING;
