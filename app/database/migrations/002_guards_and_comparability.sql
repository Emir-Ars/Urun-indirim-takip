-- 002: Geçmişi koruyan kurallar ve turlar arası karşılaştırılabilirlik.
-- 001 değişmez; bu dosya ona ekleme yapar. Üç bölüm:
--   A) iki yeni CHECK: Tükendi satırı fiyat taşımaz, çizili fiyat güncel fiyattan büyüktür;
--   B) tetikleyiciler: satır silinemez, kimlik alanları değişmez, yazılmış sonuç donar;
--   C) product_run_prices görünümü: iki turun fiyatı ne zaman karşılaştırılabilir.
-- CHECK ifadesi NULL verirse satır kabul edilir; koşullar bu yüzden 001'deki gibi
-- IS NULL / IS NOT NULL ile NULL'a karşı korunarak yazılır.

-- A) CHECK kuralları ---------------------------------------------------------

-- Satın alınamayan fiyat "en ucuz" hesabına karışmasın (docs/teknik.md "Tükendi").
ALTER TABLE listing_checks
    ADD CONSTRAINT listing_checks_sold_out_has_no_offer CHECK (
        outcome IS DISTINCT FROM 'sold_out'
        OR (
            current_price IS NULL AND original_price IS NULL
            AND seller_name IS NULL AND seller_rating IS NULL
            AND seller_rating_scale IS NULL
        )
    );

-- Üstü çizili fiyat yalnızca güncel fiyattan büyükse saklanır; scraper bu kuralı
-- zaten uygular, burası elle SQL ile veya yarın bozulan bir kodla ihlali engeller.
ALTER TABLE listing_checks
    ADD CONSTRAINT listing_checks_original_above_current CHECK (
        original_price IS NULL
        OR (current_price IS NOT NULL AND original_price > current_price)
    );

-- B) Tetikleyiciler ----------------------------------------------------------

-- Hiçbir tabloda satır silinmez: geçmiş kalıcıdır, katalogdan düşen kayıt pasife
-- alınır (active = false). Gerçekten gerekirse tablonun sahibi ilgili
-- tetikleyiciyi bilerek kapatır (ALTER TABLE ... DISABLE TRIGGER ...).
CREATE FUNCTION reject_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% reddedildi: % tablosundan satır silinemez', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation',
              HINT = 'Kayıt silinmez; katalog kayıtları pasife alınır (active = false).';
END;
$$;

-- Kimlik alanları değişmez; kod bugün de değiştirmez, bu elle SQL'e karşı korumadır.
-- Değişebilenler (kodun gerçekten güncellediği sütunlar) açıkça bırakılmıştır:
--   platforms name, active | products active | listings url, color, active
--   collection_runs status, finished_at, note
CREATE FUNCTION guard_platforms_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.key IS DISTINCT FROM OLD.key THEN
        RAISE EXCEPTION 'platforms.key kimlik alanıdır, değiştirilemez'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION guard_products_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.product_id IS DISTINCT FROM OLD.product_id
        OR NEW.product_key IS DISTINCT FROM OLD.product_key
        OR NEW.brand IS DISTINCT FROM OLD.brand
        OR NEW.model IS DISTINCT FROM OLD.model
        OR NEW.storage_gb IS DISTINCT FROM OLD.storage_gb THEN
        RAISE EXCEPTION 'products kimlik alanları (product_id, product_key, brand, model, storage_gb) değiştirilemez'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION guard_listings_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.listing_id IS DISTINCT FROM OLD.listing_id
        OR NEW.product_id IS DISTINCT FROM OLD.product_id
        OR NEW.platform IS DISTINCT FROM OLD.platform THEN
        RAISE EXCEPTION 'listings kimlik alanları (listing_id, product_id, platform) değiştirilemez'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

-- run_id burada yok: GENERATED ALWAYS kimlik sütunu olduğu için PostgreSQL
-- zaten yalnızca DEFAULT'a güncellenmesine izin verir.
CREATE FUNCTION guard_collection_runs_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW."trigger" IS DISTINCT FROM OLD."trigger"
        OR NEW.started_at IS DISTINCT FROM OLD.started_at
        OR NEW.catalog_sha256 IS DISTINCT FROM OLD.catalog_sha256
        OR NEW.planned_count IS DISTINCT FROM OLD.planned_count THEN
        RAISE EXCEPTION 'collection_runs kimlik alanları (trigger, started_at, catalog_sha256, planned_count) değiştirilemez'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

-- Sonuç bir kez yazılır: tur başında satır sonuçsuz açılır (outcome NULL), sayfa
-- okununca ilk sonuç yazılır, sonra satır donar. Tek istisna: çalışan turdaki
-- `network` hatası, aynı tur içinde yeniden okunup yerine sonuç yazılabilir
-- (Adım 11, tur sonu ikinci geçiş). Biten turun satırı hiçbir hâlde değişmez.
CREATE FUNCTION guard_listing_checks_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.run_id IS DISTINCT FROM OLD.run_id
        OR NEW.listing_id IS DISTINCT FROM OLD.listing_id
        OR NEW.product_id IS DISTINCT FROM OLD.product_id THEN
        RAISE EXCEPTION 'listing_checks kimlik alanları (run_id, listing_id, product_id) değiştirilemez'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF OLD.outcome IS NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.outcome = 'error' AND OLD.error_code = 'network'
        AND EXISTS (
            SELECT 1 FROM collection_runs r
            WHERE r.run_id = OLD.run_id AND r.status = 'running'
        ) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Yazılmış sonuç değiştirilemez (tur % sayfa %)', OLD.run_id, OLD.listing_id
        USING ERRCODE = 'integrity_constraint_violation',
              HINT = 'Yalnızca çalışan turdaki network hatası yeniden yazılabilir.';
END;
$$;

CREATE TRIGGER platforms_guard_update BEFORE UPDATE ON platforms
    FOR EACH ROW EXECUTE FUNCTION guard_platforms_update();
CREATE TRIGGER products_guard_update BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION guard_products_update();
CREATE TRIGGER listings_guard_update BEFORE UPDATE ON listings
    FOR EACH ROW EXECUTE FUNCTION guard_listings_update();
CREATE TRIGGER collection_runs_guard_update BEFORE UPDATE ON collection_runs
    FOR EACH ROW EXECUTE FUNCTION guard_collection_runs_update();
CREATE TRIGGER listing_checks_guard_update BEFORE UPDATE ON listing_checks
    FOR EACH ROW EXECUTE FUNCTION guard_listing_checks_update();

CREATE TRIGGER platforms_no_delete BEFORE DELETE ON platforms
    FOR EACH ROW EXECUTE FUNCTION reject_delete();
CREATE TRIGGER products_no_delete BEFORE DELETE ON products
    FOR EACH ROW EXECUTE FUNCTION reject_delete();
CREATE TRIGGER listings_no_delete BEFORE DELETE ON listings
    FOR EACH ROW EXECUTE FUNCTION reject_delete();
CREATE TRIGGER collection_runs_no_delete BEFORE DELETE ON collection_runs
    FOR EACH ROW EXECUTE FUNCTION reject_delete();
CREATE TRIGGER listing_checks_no_delete BEFORE DELETE ON listing_checks
    FOR EACH ROW EXECUTE FUNCTION reject_delete();

-- TRUNCATE satır tetikleyicilerini çalıştırmaz; bu yüzden ayrı (komut düzeyinde).
CREATE TRIGGER platforms_no_truncate BEFORE TRUNCATE ON platforms
    FOR EACH STATEMENT EXECUTE FUNCTION reject_delete();
CREATE TRIGGER products_no_truncate BEFORE TRUNCATE ON products
    FOR EACH STATEMENT EXECUTE FUNCTION reject_delete();
CREATE TRIGGER listings_no_truncate BEFORE TRUNCATE ON listings
    FOR EACH STATEMENT EXECUTE FUNCTION reject_delete();
CREATE TRIGGER collection_runs_no_truncate BEFORE TRUNCATE ON collection_runs
    FOR EACH STATEMENT EXECUTE FUNCTION reject_delete();
CREATE TRIGGER listing_checks_no_truncate BEFORE TRUNCATE ON listing_checks
    FOR EACH STATEMENT EXECUTE FUNCTION reject_delete();

-- C) Karşılaştırılabilirlik görünümü -----------------------------------------

-- Her biten tur × ürün için bir satır. İki tur ancak cevap veren sayfa kümesi
-- (outcome 'offer' veya 'sold_out'; hata cevap değildir, Tükendi gerçek cevaptır)
-- aynıysa karşılaştırılır; yoksa bir sayfanın hata alması "en ucuz fiyat"ı
-- sahte olarak yükseltir, geri gelince sahte bir düşüş gibi görünürdü. Aynı kural
-- yeni eklenen veya pasife alınan sayfalar için de geçerlidir (kapsam değişti).
-- Karşılaştırma yalnız comparable_with_previous = true olan satırlarda yapılır.
--   - Önceki tur: o ürünün satırı bulunan bir önceki biten tur (--prefix turu
--     başka ürünleri atlar). Süren ve yarıda kalan turlar görünüme girmez.
--   - hours_since_previous bilgi içindir, karşılaştırmayı engellemez: uzun
--     boşluğu (örn. bilgisayar uyuyunca kaçan turlar) tüketen taraf yorumlar.
--   - best_price: fiyatı olan (offer) sayfalar arasındaki en ucuz fiyat, kuruş.
--     Ürünün bütün cevapları Tükendi ise NULL; bu bir düşüş değildir.
CREATE VIEW product_run_prices AS
WITH per_product AS (
    SELECT
        c.run_id,
        c.product_id,
        r.started_at AS run_started_at,
        count(*) AS planned_pages,
        count(*) FILTER (WHERE c.outcome IN ('offer', 'sold_out')) AS answered_pages,
        count(*) FILTER (WHERE c.outcome = 'offer') AS offer_pages,
        count(*) FILTER (WHERE c.outcome = 'sold_out') AS sold_out_pages,
        count(*) FILTER (WHERE c.outcome = 'error') AS error_pages,
        min(c.current_price) FILTER (WHERE c.outcome = 'offer') AS best_price,
        -- Eşit fiyatta sayfa kimliği küçük olan kazanır (sonuç tekrarlanabilir olsun).
        (array_agg(c.listing_id ORDER BY c.current_price, c.listing_id)
            FILTER (WHERE c.outcome = 'offer'))[1] AS best_listing_id,
        coalesce(
            array_agg(c.listing_id ORDER BY c.listing_id)
                FILTER (WHERE c.outcome IN ('offer', 'sold_out')),
            ARRAY[]::text[]
        ) AS answered_listing_ids
    FROM listing_checks AS c
    JOIN collection_runs AS r ON r.run_id = c.run_id
    WHERE r.status = 'completed'
    GROUP BY c.run_id, c.product_id, r.started_at
),
with_previous AS (
    SELECT
        p.*,
        lag(p.run_id) OVER w AS previous_run_id,
        lag(p.run_started_at) OVER w AS previous_run_started_at,
        lag(p.best_price) OVER w AS previous_best_price,
        lag(p.answered_listing_ids) OVER w AS previous_answered_listing_ids
    FROM per_product AS p
    WINDOW w AS (PARTITION BY p.product_id ORDER BY p.run_id)
)
SELECT
    run_id,
    product_id,
    run_started_at,
    planned_pages,
    answered_pages,
    offer_pages,
    sold_out_pages,
    error_pages,
    best_price,
    best_listing_id,
    previous_run_id,
    previous_best_price,
    round(
        extract(epoch FROM run_started_at - previous_run_started_at)::numeric / 3600, 2
    ) AS hours_since_previous,
    (
        previous_run_id IS NOT NULL
        AND answered_pages > 0
        AND answered_listing_ids = previous_answered_listing_ids
    ) AS comparable_with_previous
FROM with_previous;
