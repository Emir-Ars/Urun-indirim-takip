"""catalog.json'u veritabanındaki kopyaya (platforms, products, listings) eşitler.

Asıl kaynak dosyadır. Yeni kayıt eklenir, değişebilen alanlar güncellenir,
katalogdan düşen kayıt silinmez, pasife alınır (geçmiş fiyatlar ona bağlıdır).
Kimlik alanı değişmiş ya da benzersiz bir değer başka kayıtla çakışıyorsa hiçbir
şey yazılmaz (CatalogConflict): geçmiş fiyatlar yanlış ürüne bağlanmamalı.
"""

from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from psycopg import errors, sql
from psycopg.rows import dict_row

from app.contracts import Catalog
from app.database.migrate import checksum


@dataclass(frozen=True)
class Table:
    name: str
    key: str
    identity: tuple[str, ...]  # değişemez alanlar
    mutable: tuple[str, ...]  # katalogla güncellenen alanlar
    unique: tuple[tuple[str, ...], ...] = ()  # anahtar dışındaki benzersiz alanlar

    @property
    def columns(self) -> tuple[str, ...]:
        return (self.key, *self.identity, *self.mutable)


# Sıra önemli: sayfalar ürünlere ve platformlara bağlıdır.
TABLES = (
    # Platformun `hosts` alanı veritabanına yazılmaz: tur, siteye gideceği alan
    # adlarını dosyadaki katalogdan alır. Veritabanındaki kopya yabancı anahtarlar
    # ve raporlama içindir (anahtar, ad, aktiflik).
    Table("platforms", "key", (), ("name", "active")),
    Table(
        "products",
        "product_id",
        ("product_key", "brand", "model", "storage_gb"),
        ("active",),
        unique=(("product_key",), ("brand", "model", "storage_gb")),
    ),
    Table(
        "listings",
        "listing_id",
        ("product_id", "platform"),
        ("url", "color", "active"),
        unique=(("platform", "url"),),
    ),
)

Rows = dict[str, dict[object, dict]]  # tablo -> anahtar -> satır


class CatalogConflict(Exception):
    """Katalog, veritabanındaki kopyayla güvenle birleştirilemiyor."""


@dataclass
class TableChanges:
    added: list[dict] = field(default_factory=list)
    # (anahtar, {alan: (eski, yeni)})
    updated: list[tuple[object, dict[str, tuple]]] = field(default_factory=list)
    deactivated: list[object] = field(default_factory=list)
    unchanged: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.deactivated)


@dataclass
class SyncPlan:
    tables: dict[str, TableChanges]

    @property
    def changed(self) -> bool:
        return any(changes.changed for changes in self.tables.values())


def read_catalog(path: Path) -> tuple[Catalog, str]:
    """Katalogu sözleşmeyle doğrulayarak okur; (katalog, parmak izi) döndürür."""
    text = path.read_text(encoding="utf-8-sig")  # BOM'lu dosya da okunur
    return Catalog.model_validate_json(text), checksum(text)


def catalog_rows(catalog: Catalog) -> Rows:
    records = {
        "platforms": catalog.platforms,
        "products": catalog.products,
        "listings": catalog.listings,
    }
    return {
        table.name: {
            getattr(record, table.key): {
                column: getattr(record, column) for column in table.columns
            }
            for record in records[table.name]
        }
        for table in TABLES
    }


def plan_sync(current: Rows, catalog: Catalog) -> SyncPlan:
    """Veritabanındaki kopya (`current`) ile katalog arasındaki farkı hesaplar.

    Veritabanına dokunmaz. Çakışmaların hepsini toplayıp tek CatalogConflict
    olarak bildirir.
    """
    wanted = catalog_rows(catalog)
    conflicts = []
    plan = SyncPlan({})
    for table in TABLES:
        existing = current.get(table.name, {})
        changes = plan.tables[table.name] = TableChanges()
        final = {}
        for key, row in wanted[table.name].items():
            old = existing.get(key)
            if old is None:
                changes.added.append(row)
            else:
                for column in table.identity:
                    if old[column] != row[column]:
                        conflicts.append(
                            f"{table.name} {key}: {column} değişemez "
                            f"({old[column]!r} → {row[column]!r})"
                        )
                diff = {
                    column: (old[column], row[column])
                    for column in table.mutable
                    if old[column] != row[column]
                }
                if diff:
                    changes.updated.append((key, diff))
                else:
                    changes.unchanged += 1
            final[key] = row
        for key, old in existing.items():
            if key in wanted[table.name]:
                continue
            if old["active"]:
                changes.deactivated.append(key)
            else:
                changes.unchanged += 1
            final[key] = old
        conflicts.extend(_unique_conflicts(table, final))
    if conflicts:
        raise CatalogConflict(
            "Katalog veritabanıyla eşitlenemedi; hiçbir şey yazılmadı:\n  "
            + "\n  ".join(conflicts)
        )
    return plan


def sync_catalog(
    conn: psycopg.Connection, catalog: Catalog, *, dry_run: bool = False
) -> SyncPlan:
    """Katalogu tek transaction'da yazar; `dry_run` ise sonunda geri alır."""
    with conn.transaction(force_rollback=dry_run):
        # Eşitleme sürerken başka bir yazıcı bu tablolara dokunamaz.
        conn.execute(
            "LOCK TABLE platforms, products, listings IN SHARE ROW EXCLUSIVE MODE"
        )
        plan = plan_sync(_read_current(conn), catalog)
        try:
            _apply(conn, plan)
        except errors.UniqueViolation as exc:
            # Son durum geçerli ama tek adımda uygulanamıyor (ör. iki sayfanın
            # adresi yer değiştirmiş). Transaction geri alınır, hiçbir şey yazılmaz.
            raise CatalogConflict(
                "Katalog tek adımda eşitlenemedi (benzersiz bir değer iki kayıt "
                "arasında yer değiştiriyor); hiçbir şey yazılmadı. Değişikliği iki "
                f"adımda yapın. Ayrıntı: {exc}"
            ) from exc
    return plan


def _unique_conflicts(table: Table, final: dict[object, dict]) -> list[str]:
    conflicts = []
    for columns in table.unique:
        seen = {}
        for key, row in final.items():
            value = tuple(_comparable(row[column]) for column in columns)
            if value in seen:
                conflicts.append(
                    f"{table.name} {key}: {'+'.join(columns)} değeri "
                    f"{seen[value]} kaydında da kullanılıyor"
                )
            else:
                seen[value] = key
    return conflicts


def _comparable(value):
    # Veritabanındaki benzersiz indeks marka/modeli lower() ile karşılaştırır.
    return value.lower() if isinstance(value, str) else value


def _read_current(conn: psycopg.Connection) -> Rows:
    current = {}
    with conn.cursor(row_factory=dict_row) as cursor:
        for table in TABLES:
            cursor.execute(
                sql.SQL("SELECT {} FROM {}").format(
                    sql.SQL(", ").join(map(sql.Identifier, table.columns)),
                    sql.Identifier(table.name),
                )
            )
            current[table.name] = {row[table.key]: row for row in cursor}
    return current


def _apply(conn: psycopg.Connection, plan: SyncPlan) -> None:
    # Her tabloda önce güncellemeler, sonra eklemeler: bir sayfanın adresi
    # değişip eski adres yeni bir sayfaya verildiyse ekleme çakışmasın.
    with conn.cursor() as cursor:
        for table in TABLES:
            changes = plan.tables[table.name]
            name, key = sql.Identifier(table.name), sql.Identifier(table.key)
            for row_key, diff in changes.updated:
                cursor.execute(
                    sql.SQL("UPDATE {} SET {} WHERE {} = %s").format(
                        name,
                        sql.SQL(", ").join(
                            sql.SQL("{} = %s").format(sql.Identifier(c)) for c in diff
                        ),
                        key,
                    ),
                    [new for _, new in diff.values()] + [row_key],
                )
            if changes.deactivated:
                cursor.execute(
                    sql.SQL("UPDATE {} SET active = false WHERE {} = ANY(%s)").format(
                        name, key
                    ),
                    [changes.deactivated],
                )
            if changes.added:
                cursor.executemany(
                    sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        name,
                        sql.SQL(", ").join(map(sql.Identifier, table.columns)),
                        sql.SQL(", ").join(sql.Placeholder() * len(table.columns)),
                    ),
                    [[row[c] for c in table.columns] for row in changes.added],
                )
