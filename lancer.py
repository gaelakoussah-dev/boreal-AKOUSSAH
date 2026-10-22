import argparse
import sys
import time
import traceback
from datetime import datetime

import analyses_clients
import analyses_techniques
import coeur
import ingestion
import marts
import prep
import tests
from commun import SOURCES, connexion


def alerter(message):
    ligne = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
    with open("alertes.log", "a", encoding="utf-8") as f:
        f.write(ligne + "\n")
    print("ALERTE " + ligne, file=sys.stderr)


def etape_ingestion(con):
    if not ingestion.charger_tout(con, SOURCES):
        raise RuntimeError("au moins un fichier source n'a pas pu etre charge (voir brut.journal)")


def etape_tests(con):
    echecs = tests.executer(con)
    if echecs:
        raise RuntimeError(f"{echecs} test(s) en echec, marts non mis a jour")


ETAPES = [
    ("ingestion", etape_ingestion),
    ("prep", prep.executer),
    ("coeur", coeur.executer),
    ("tests", etape_tests),
    ("marts", marts.executer),
    ("analyses_techniques", analyses_techniques.executer),
    ("analyses_clients", analyses_clients.executer),
]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--etapes", help="liste d'etapes separees par des virgules (defaut : toutes)")
    args = p.parse_args(argv)
    voulues = args.etapes.split(",") if args.etapes else [e for e, _ in ETAPES]
    con = connexion()
    con.execute("""CREATE TABLE IF NOT EXISTS mart.executions (
        lance_le TIMESTAMP, etape VARCHAR, duree_s DOUBLE, statut VARCHAR, message VARCHAR)""")
    for nom, fonction in ETAPES:
        if nom not in voulues:
            continue
        print(f"== {nom}")
        debut = time.time()
        try:
            fonction(con)
            con.execute("INSERT INTO mart.executions VALUES (now(), ?, ?, 'ok', NULL)", [nom, time.time() - debut])
        except Exception as e:
            con.execute("INSERT INTO mart.executions VALUES (now(), ?, ?, 'echec', ?)", [nom, time.time() - debut, str(e)[:300]])
            traceback.print_exc()
            alerter(f"echec de l'etape {nom} : {e}")
            con.close()
            return 1
    con.close()
    print("Pipeline termine sans erreur.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
