BEGIN;
SET LOCAL lock_timeout = '3s';

DO $setup$
DECLARE
    database_name text := current_database();
    reader_name text;
    reader record;
    relation_name text;
    relations text[] := ARRAY[
        'schema_migrations', 'platforms', 'products', 'listings',
        'collection_runs', 'listing_checks', 'product_run_prices', 'market_history'
    ];
BEGIN
    IF database_name = 'fiyat_takip' THEN
        reader_name := 'fiyat_takip_api';
    ELSIF database_name LIKE '%\_test' ESCAPE '\' THEN
        reader_name := 'fiyat_takip_api_test';
    ELSE
        RAISE EXCEPTION 'API okuma rolü yalnız fiyat_takip veya _test veritabanında kurulabilir';
    END IF;

    FOREACH relation_name IN ARRAY relations LOOP
        IF to_regclass(format('public.%I', relation_name)) IS NULL THEN
            RAISE EXCEPTION 'Önce 001–004 uygulanmalı; eksik nesne: %', relation_name;
        END IF;
    END LOOP;

    SELECT * INTO reader FROM pg_roles WHERE rolname = reader_name;
    IF NOT FOUND THEN
        EXECUTE format(
            'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
            reader_name
        );
        SELECT * INTO reader FROM pg_roles WHERE rolname = reader_name;
    END IF;

    IF NOT reader.rolcanlogin OR reader.rolsuper OR reader.rolcreatedb
       OR reader.rolcreaterole OR reader.rolinherit OR reader.rolreplication
       OR reader.rolbypassrls THEN
        RAISE EXCEPTION 'Mevcut API rolünün yetkileri uygun değil: %', reader_name;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = reader.oid)
       OR EXISTS (SELECT 1 FROM pg_database WHERE datdba = reader.oid)
       OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner = reader.oid)
       OR EXISTS (SELECT 1 FROM pg_class WHERE relowner = reader.oid) THEN
        RAISE EXCEPTION 'API rolü başka role üye veya nesne sahibi olamaz: %', reader_name;
    END IF;

    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', database_name, reader_name);
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', reader_name);
    FOREACH relation_name IN ARRAY relations LOOP
        EXECUTE format('GRANT SELECT ON TABLE public.%I TO %I', relation_name, reader_name);
    END LOOP;

    IF has_database_privilege(reader_name, database_name, 'CREATE')
       OR has_schema_privilege(reader_name, 'public', 'CREATE')
       OR EXISTS (
           SELECT 1 FROM pg_class AS c
           JOIN pg_namespace AS n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
           AND has_table_privilege(
               reader_name, c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
           )
       ) THEN
        RAISE EXCEPTION 'API rolünde yazma veya nesne oluşturma yetkisi var: %', reader_name;
    END IF;

    IF NOT coalesce(reader.rolconfig, ARRAY[]::text[])
           @> ARRAY['default_transaction_read_only=on'] THEN
        EXECUTE format('ALTER ROLE %I SET default_transaction_read_only = on', reader_name);
    END IF;
    RAISE NOTICE 'API okuma rolü hazır: % / %. Şifreyi psql içindeki \password ile belirleyin.',
        reader_name, database_name;
END
$setup$;

COMMIT;
