import os
from datetime import date, timedelta
from pathlib import Path

import duckdb

SOURCES = Path(os.environ.get("BOREAL_SOURCES", "sources"))
BASE = os.environ.get("BOREAL_BASE", "boreal.duckdb")
EXTRACTION = date(2025, 6, 30)
COUPURE = EXTRACTION + timedelta(days=1)
SCHEMAS = ("brut", "prep", "quarantaine", "coeur", "mart")

MACROS = """
CREATE OR REPLACE MACRO vide(x) AS nullif(trim(x), '');
CREATE OR REPLACE MACRO propre(x) AS lower(trim(x));
CREATE OR REPLACE MACRO vers_date(x) AS
    coalesce(try_strptime(trim(x), '%Y-%m-%d'), try_strptime(trim(x), '%d/%m/%Y'))::DATE;
CREATE OR REPLACE MACRO vers_nombre(x) AS try_cast(replace(trim(x), ',', '.') AS DOUBLE);
"""


def connexion(chemin=None, lecture_seule=False):
    con = duckdb.connect(chemin or BASE, read_only=lecture_seule)
    if not lecture_seule:
        for s in SCHEMAS:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
        con.execute(MACROS)
    return con


def table_existe(con, schema, nom):
    return con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
        [schema, nom],
    ).fetchall()[0][0] > 0


def ecrire(con, schema, nom, df):
    con.register("tmp_df", df)
    con.execute(f"CREATE OR REPLACE TABLE {schema}.{nom} AS SELECT * FROM tmp_df")
    con.unregister("tmp_df")
