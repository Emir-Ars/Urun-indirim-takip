"""Test veritabanına doğrudan satır yazan yardımcılar (yalnız `_test` DB)."""

from psycopg import sql


def insert(conn, table, **values):
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, values)),
        sql.SQL(", ").join(sql.Placeholder() * len(values)),
    )
    conn.execute(query, list(values.values()))
