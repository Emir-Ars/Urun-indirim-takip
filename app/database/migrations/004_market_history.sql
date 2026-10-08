-- Cimri geçmişi kendi toplama turlarımızdan ayrı tutulur; ilk kayıt korunur.
CREATE TABLE market_history (
    product_id integer NOT NULL REFERENCES products (product_id),
    source text NOT NULL CHECK (source = 'cimri'),
    source_product_id text NOT NULL CHECK (source_product_id ~ '^[1-9][0-9]*$'),
    source_url text NOT NULL CHECK (
        source_url ~ '^https://(www\.)?cimri\.com/cep-telefonlari/[^[:space:]]+$'
    ),
    day date NOT NULL CHECK (isfinite(day)),
    price_kurus bigint CHECK (price_kurus > 0),
    captured_at timestamptz NOT NULL CHECK (isfinite(captured_at)),
    page_sha256 text NOT NULL CHECK (page_sha256 ~ '^[0-9a-f]{64}$'),
    api_sha256 text NOT NULL CHECK (api_sha256 ~ '^[0-9a-f]{64}$'),
    report_sha256 text NOT NULL CHECK (report_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (product_id, source, day)
);

CREATE FUNCTION guard_market_history_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'market_history kaydı değiştirilemez; ilk kayıt korunur'
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE TRIGGER market_history_no_update BEFORE UPDATE ON market_history
    FOR EACH ROW EXECUTE FUNCTION guard_market_history_update();
CREATE TRIGGER market_history_no_delete BEFORE DELETE ON market_history
    FOR EACH ROW EXECUTE FUNCTION reject_delete();
CREATE TRIGGER market_history_no_truncate BEFORE TRUNCATE ON market_history
    FOR EACH STATEMENT EXECUTE FUNCTION reject_delete();
