-- 001: Katalogun kopyası, toplama turları ve her turda sayfa sonuçları.
-- Para TRY kuruş (integer), zaman timestamptz (UTC). Kurallar veritabanında
-- zorlanır: koddaki bir hata bile kurala aykırı satır yazamaz.
-- Dikkat: CHECK ifadesi NULL sonuç verirse satır kabul edilir; bu yüzden
-- koşullar IS NULL / IS NOT NULL ile NULL'a karşı korunarak yazılır.

-- Katalog kopyası. Asıl kaynak config/catalog.json; her tur başında eşitlenir,
-- kayıt silinmez, kimlikler değişmez.
CREATE TABLE platforms (
    key text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_]*$'),
    name text NOT NULL CHECK (name <> ''),
    active boolean NOT NULL
);

CREATE TABLE products (
    product_id integer PRIMARY KEY CHECK (product_id > 0),
    product_key text NOT NULL UNIQUE CHECK (product_key <> ''),
    brand text NOT NULL CHECK (brand <> ''),
    model text NOT NULL CHECK (model <> ''),
    storage_gb integer NOT NULL CHECK (storage_gb > 0),
    active boolean NOT NULL
);
-- Katalogdaki kural: marka + model + kapasite, büyük/küçük harften bağımsız tekil.
CREATE UNIQUE INDEX products_identity
    ON products (lower(brand), lower(model), storage_gb);

CREATE TABLE listings (
    listing_id text PRIMARY KEY CHECK (listing_id <> ''),
    product_id integer NOT NULL REFERENCES products (product_id),
    platform text NOT NULL REFERENCES platforms (key),
    url text NOT NULL CHECK (url LIKE 'https://%'),
    color text NOT NULL,
    active boolean NOT NULL,
    UNIQUE (platform, url),
    -- listing_checks'teki (sayfa, ürün) çiftinin doğruluğu bunun üzerinden denetlenir.
    UNIQUE (listing_id, product_id)
);

-- Her fiyat toplama turu bir satır.
CREATE TABLE collection_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trigger text NOT NULL CHECK (trigger IN ('scheduled', 'manual')),
    status text NOT NULL
        CHECK (status IN ('running', 'completed', 'interrupted')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    -- Turun başındaki catalog.json dosyasının parmak izi.
    catalog_sha256 text NOT NULL CHECK (catalog_sha256 ~ '^[0-9a-f]{64}$'),
    planned_count integer NOT NULL CHECK (planned_count >= 0),
    note text,
    -- Süren turun bitiş zamanı yoktur, biten turun vardır.
    CHECK ((status = 'running') = (finished_at IS NULL)),
    CHECK (finished_at >= started_at)
);
-- Aynı anda en fazla bir tur sürebilir.
CREATE UNIQUE INDEX collection_runs_one_running
    ON collection_runs ((true)) WHERE status = 'running';

-- Her tur × planlanan sayfa bir satır. Satır tur başında sonuçsuz açılır
-- (outcome NULL = planlandı, henüz bakılmadı) ve sayfa okununca doldurulur.
CREATE TABLE listing_checks (
    run_id bigint NOT NULL REFERENCES collection_runs (run_id),
    listing_id text NOT NULL,
    product_id integer NOT NULL,
    checked_at timestamptz,
    outcome text CHECK (outcome IN ('offer', 'sold_out', 'error')),
    current_price integer CHECK (current_price > 0),
    original_price integer CHECK (original_price > 0),
    seller_name text,
    seller_rating numeric CHECK (seller_rating >= 0),
    seller_rating_scale numeric CHECK (seller_rating_scale > 0),
    stock_status text
        CHECK (stock_status IN ('Stokta Var', 'Kritik Stok', 'Tükendi')),
    error_code text,
    error_message text,
    -- Aynı turda aynı sayfa yalnızca bir kez: tekrar kayıt engeli.
    PRIMARY KEY (run_id, listing_id),
    -- Sayfanın sonucu başka bir ürünün altına yazılamaz.
    FOREIGN KEY (listing_id, product_id)
        REFERENCES listings (listing_id, product_id),
    CHECK (seller_rating <= seller_rating_scale),
    -- Sonuç türleri birbirine karışamaz: hata fiyat taşımaz, fiyat satıcısız
    -- olmaz, Tükendi yalnızca Tükendi stokla yazılır.
    CHECK (
        CASE outcome
            WHEN 'offer' THEN
                checked_at IS NOT NULL
                AND current_price IS NOT NULL
                AND seller_name IS NOT NULL AND seller_name <> ''
                AND stock_status IS NOT NULL
                AND stock_status IN ('Stokta Var', 'Kritik Stok')
                AND error_code IS NULL AND error_message IS NULL
            WHEN 'sold_out' THEN
                checked_at IS NOT NULL
                AND stock_status IS NOT NULL AND stock_status = 'Tükendi'
                AND error_code IS NULL AND error_message IS NULL
            WHEN 'error' THEN
                checked_at IS NOT NULL
                AND error_code IS NOT NULL AND error_code <> ''
                AND current_price IS NULL AND original_price IS NULL
                AND seller_name IS NULL AND seller_rating IS NULL
                AND seller_rating_scale IS NULL AND stock_status IS NULL
            ELSE
                outcome IS NULL
                AND checked_at IS NULL
                AND current_price IS NULL AND original_price IS NULL
                AND seller_name IS NULL AND seller_rating IS NULL
                AND seller_rating_scale IS NULL AND stock_status IS NULL
                AND error_code IS NULL AND error_message IS NULL
        END
    )
);
-- "Bir telefonun zaman içindeki fiyatları" sorgusu için.
CREATE INDEX listing_checks_product_time
    ON listing_checks (product_id, checked_at);
