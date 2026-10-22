import argparse
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
from datetime import datetime

import pandas as pd

from commun import SOURCES, connexion, table_existe

ALIAS = {
    "clients": {}, "contrats": {}, "sinistres": {}, "audits": {},
    "reglements": {"montant_eur": "montant"},
}


def nom_colonne(c):
    c = unicodedata.normalize("NFKD", c.replace("\ufeff", "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", c.strip().lower()).strip("_")


def decoder(chemin):
    octets = chemin.read_bytes()
    try:
        return octets.decode("utf-8-sig")
    except UnicodeDecodeError:
        return octets.decode("latin-1")


def lire_csv(chemin):
    texte = decoder(chemin)
    lignes = [l for l in texte.splitlines() if l.strip()]
    entete = lignes[0]
    sep = max(",;\t|", key=entete.count)
    df = pd.read_csv(io.StringIO(texte), sep=sep, dtype=str, keep_default_na=False,
                     on_bad_lines="skip").fillna("")
    return df, len(lignes) - 1


def lire_jsonl(chemin):
    lignes = [l for l in decoder(chemin).splitlines() if l.strip()]
    lus = []
    for l in lignes:
        try:
            obj = json.loads(l)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            lus.append({k: "" if v is None else str(v) for k, v in obj.items()})
    return pd.DataFrame(lus).fillna(""), len(lignes)


def empreinte(chemin):
    return hashlib.md5(chemin.read_bytes()).hexdigest()


def preparer_journal(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS brut.journal (
            fichier VARCHAR, source VARCHAR, empreinte VARCHAR, lues INTEGER, rejetees INTEGER,
            duree_s DOUBLE, statut VARCHAR, message VARCHAR, charge_le TIMESTAMP)
    """)


def deja_charge(con, chemin):
    return con.execute(
        "SELECT count(*) FROM brut.journal WHERE fichier = ? AND empreinte = ? AND statut = 'ok'",
        [chemin.name, empreinte(chemin)],
    ).fetchall()[0][0] > 0


def charger(con, chemin, source, lecteur, force=False):
    if not force and deja_charge(con, chemin):
        print(f"  {chemin.name}: deja charge, ignore")
        return True
    debut = time.time()
    try:
        df, vues = lecteur(chemin)
        df.columns = [nom_colonne(c) for c in df.columns]
        df = df.rename(columns=ALIAS[source])
        df["_fichier"] = chemin.name
        df["_charge_le"] = datetime.now()
        con.register("tmp_df", df)
        con.execute("BEGIN")
        if not table_existe(con, "brut", source):
            con.execute(f"CREATE TABLE brut.{source} AS SELECT * FROM tmp_df")
        else:
            connues = {r[0] for r in con.execute(f"DESCRIBE brut.{source}").fetchall()}
            for c in df.columns:
                if c not in connues:
                    con.execute(f'ALTER TABLE brut.{source} ADD COLUMN "{c}" VARCHAR')
            con.execute(f"DELETE FROM brut.{source} WHERE _fichier = ?", [chemin.name])
            con.execute(f"INSERT INTO brut.{source} BY NAME SELECT * FROM tmp_df")
        con.execute("INSERT INTO brut.journal VALUES (?, ?, ?, ?, ?, ?, 'ok', NULL, now())",
                    [chemin.name, source, empreinte(chemin), len(df), vues - len(df), time.time() - debut])
        con.execute("COMMIT")
        con.unregister("tmp_df")
        print(f"  {chemin.name}: {len(df)} lignes, {vues - len(df)} rejetees")
        return True
    except Exception as e:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        con.execute("INSERT INTO brut.journal VALUES (?, ?, ?, 0, 0, ?, 'erreur', ?, now())",
                    [chemin.name, source, empreinte(chemin), time.time() - debut, str(e)[:300]])
        print(f"  {chemin.name}: ERREUR {e}")
        return False


def liste_fichiers(racine=SOURCES):
    fichiers = [
        (racine / "crm" / "clients.csv", "clients", lire_csv),
        (racine / "contrats" / "contrats.csv", "contrats", lire_csv),
        (racine / "sinistres" / "sinistres.jsonl", "sinistres", lire_jsonl),
        (racine / "antifraude" / "audits.csv", "audits", lire_csv),
    ]
    fichiers += [(f, "reglements", lire_csv) for f in sorted((racine / "reglements").glob("reglements_*.csv"))]
    return fichiers


def charger_tout(con, racine=SOURCES, recharger=None):
    preparer_journal(con)
    ok = True
    for chemin, source, lecteur in liste_fichiers(racine):
        if not chemin.exists():
            print(f"  {chemin}: introuvable")
            ok = False
            continue
        force = recharger is not None and chemin.name == recharger
        if recharger is not None and not force:
            continue
        ok &= charger(con, chemin, source, lecteur, force=force)
    return ok


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--recharger", help="nom d'un fichier a recharger de force, ex: reglements_2023_05.csv")
    args = p.parse_args(argv)
    con = connexion()
    ok = charger_tout(con, recharger=args.recharger)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
