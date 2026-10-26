-- Satıcı bağlantısı ölçüm anına aittir; eski turlardan türetilmez.
ALTER TABLE listing_checks
    ADD COLUMN offer_url text,
    ADD CONSTRAINT listing_checks_offer_url CHECK (
        offer_url IS NULL OR (
            outcome IS NOT NULL AND outcome = 'offer'
            AND offer_url ~* '^https://www\.(trendyol|hepsiburada)\.com(:443)?/[^[:space:]]+$'
        )
    );
