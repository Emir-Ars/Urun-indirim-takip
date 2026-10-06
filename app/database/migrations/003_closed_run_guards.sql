CREATE OR REPLACE FUNCTION guard_collection_runs_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW."trigger" IS DISTINCT FROM OLD."trigger"
        OR NEW.started_at IS DISTINCT FROM OLD.started_at
        OR NEW.catalog_sha256 IS DISTINCT FROM OLD.catalog_sha256
        OR NEW.planned_count IS DISTINCT FROM OLD.planned_count THEN
        RAISE EXCEPTION 'collection_runs kimlik alanları (trigger, started_at, catalog_sha256, planned_count) değiştirilemez'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF OLD.status <> 'running'
        AND (NEW.status IS DISTINCT FROM OLD.status
             OR NEW.finished_at IS DISTINCT FROM OLD.finished_at) THEN
        RAISE EXCEPTION 'Kapanmış turun durumu ve bitiş zamanı değiştirilemez (tur %)', OLD.run_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION guard_listing_checks_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.run_id IS DISTINCT FROM OLD.run_id
        OR NEW.listing_id IS DISTINCT FROM OLD.listing_id
        OR NEW.product_id IS DISTINCT FROM OLD.product_id THEN
        RAISE EXCEPTION 'listing_checks kimlik alanları (run_id, listing_id, product_id) değiştirilemez'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF OLD.outcome IS NULL
        OR (OLD.outcome = 'error' AND OLD.error_code = 'network') THEN
        PERFORM 1 FROM collection_runs
            WHERE run_id = OLD.run_id AND status = 'running'
            FOR SHARE;
        IF FOUND THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'Sayfa sonucu değiştirilemez (tur % sayfa %)', OLD.run_id, OLD.listing_id
        USING ERRCODE = 'integrity_constraint_violation',
              HINT = 'Yalnızca çalışan turdaki sonuçsuz satıra veya network hatasına yazılabilir.';
END;
$$;
