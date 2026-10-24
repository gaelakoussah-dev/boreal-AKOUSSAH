"""Prouve que rejouer un mois ne cree aucun doublon. Travaille sur une copie de la base : rien n'est modifie."""
import shutil
import sys
import tempfile
from pathlib import Path

import coeur
import ingestion
import prep
import tests
from commun import BASE, SOURCES, connexion

MOIS = "reglements_2023_05.csv"
TABLES = ["coeur.fact_reglement", "coeur.fact_sinistre", "coeur.dim_contrat", "coeur.dim_client", "coeur.fact_audit",
          "quarantaine.reglements", "brut.reglements"]


def photo(con):
    p = {t: con.execute(f"SELECT count(*) FROM {t}").fetchall()[0][0] for t in TABLES}
    p["montant_coeur"] = round(con.execute("SELECT sum(montant) FROM coeur.fact_reglement").fetchall()[0][0], 2)
    return p


def rejouer(con, racine, **kw):
    ingestion.charger_tout(con, racine, **kw)
    prep.executer(con)
    coeur.executer(con)


def comparer(nom, avant, apres, attendu_diff=None):
    attendu_diff = attendu_diff or {}
    ecarts = {k: apres[k] - avant[k] for k in avant if apres[k] != avant[k]}
    ok = ecarts == attendu_diff
    print(f"[{'ok' if ok else 'ECHEC'}] {nom} : ecarts {ecarts or 'aucun'}")
    return ok


def main():
    tmp = Path(tempfile.mkdtemp())
    copie = tmp / "copie.duckdb"
    shutil.copy(BASE, copie)
    con = connexion(str(copie))
    racine = tmp / "sources"
    shutil.copytree(SOURCES, racine)
    resultats = []
    ref = photo(con)
    print("Etat de reference :", ref)

    rejouer(con, racine)
    resultats.append(comparer("1. relancer le pipeline sans nouveau fichier", ref, photo(con)))

    rejouer(con, racine, recharger=MOIS)
    resultats.append(comparer(f"2. recharger de force {MOIS}", ref, photo(con)))

    nb = con.execute("SELECT count(*) FROM brut.reglements WHERE _fichier = ?", [MOIS]).fetchall()[0][0]
    shutil.copy(racine / "reglements" / MOIS, racine / "reglements" / "reglements_2023_05_livre_2_fois.csv")
    rejouer(con, racine)
    resultats.append(comparer("3. meme mois livre une deuxieme fois sous un autre nom", ref, photo(con),
                              {"brut.reglements": nb, "quarantaine.reglements": nb}))
    print(f"   -> les {nb} lignes en double sont en brut et en quarantaine (motif R01), le coeur ne bouge pas")

    con.execute("INSERT INTO coeur.fact_reglement VALUES ('999999', 'inexistant', DATE '2024-01-01', 10)")
    echecs = tests.executer(con)
    ok = echecs > 0
    print(f"[{'ok' if ok else 'ECHEC'}] 4. un reglement orphelin injecte fait echouer {echecs} test(s) : le chargement serait bloque")
    resultats.append(ok)

    con.close()
    shutil.rmtree(tmp)
    print("Tous les tests de rejeu sont reussis." if all(resultats) else "Au moins un test de rejeu a echoue.")
    return 0 if all(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
