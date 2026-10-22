import sys

from commun import connexion

# (nom, description, requete qui renvoie un nombre, valeur attendue)
TESTS = [
    ("unicite_client", "client_id unique dans dim_client",
     "SELECT count(*) - count(DISTINCT client_id) FROM coeur.dim_client", 0),
    ("unicite_contrat", "contrat_id unique dans dim_contrat",
     "SELECT count(*) - count(DISTINCT contrat_id) FROM coeur.dim_contrat", 0),
    ("unicite_sinistre", "sinistre_id unique dans fact_sinistre",
     "SELECT count(*) - count(DISTINCT sinistre_id) FROM coeur.fact_sinistre", 0),
    ("unicite_paiement", "paiement_id unique dans fact_reglement",
     "SELECT count(*) - count(DISTINCT paiement_id) FROM coeur.fact_reglement", 0),
    ("unicite_exposition", "un seul couple (contrat, annee) dans fact_exposition",
     "SELECT count(*) - count(DISTINCT (contrat_id, annee)) FROM coeur.fact_exposition", 0),
    ("integrite_contrat_client", "tout contrat pointe vers un client existant",
     "SELECT count(*) FROM coeur.dim_contrat c WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_client d WHERE d.client_id = c.client_id)", 0),
    ("integrite_sinistre_contrat", "tout sinistre pointe vers un contrat existant",
     "SELECT count(*) FROM coeur.fact_sinistre s WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_contrat c WHERE c.contrat_id = s.contrat_id)", 0),
    ("integrite_sinistre_garantie", "tout sinistre pointe vers une garantie existante",
     "SELECT count(*) FROM coeur.fact_sinistre s WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_garantie g WHERE g.garantie_id = s.garantie_id)", 0),
    ("integrite_reglement_sinistre", "tout reglement pointe vers un sinistre existant",
     "SELECT count(*) FROM coeur.fact_reglement r WHERE NOT EXISTS (SELECT 1 FROM coeur.fact_sinistre s WHERE s.sinistre_id = r.sinistre_id)", 0),
    ("integrite_audit_sinistre", "tout audit pointe vers un sinistre existant",
     "SELECT count(*) FROM coeur.fact_audit a WHERE NOT EXISTS (SELECT 1 FROM coeur.fact_sinistre s WHERE s.sinistre_id = a.sinistre_id)", 0),
    ("integrite_exposition_contrat", "toute exposition pointe vers un contrat existant",
     "SELECT count(*) FROM coeur.fact_exposition e WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_contrat c WHERE c.contrat_id = e.contrat_id)", 0),
    ("exposition_positive", "exposition strictement positive et au plus une annee",
     "SELECT count(*) FROM coeur.fact_exposition WHERE exposition <= 0 OR exposition > 366 / 365.25", 0),
    ("exposition_totale", "exposition totale = jours de couverture cumules des contrats / 365,25",
     """SELECT round(abs((SELECT sum(exposition) FROM coeur.fact_exposition) - (SELECT sum(
            least(coalesce(date_resiliation, DATE '2025-07-01'), DATE '2025-07-01') - date_effet) / 365.25
            FROM coeur.dim_contrat)), 6)""", 0),
    ("reconciliation_reglements_lignes", "reglements : lignes brutes = lignes du coeur + quarantaine (doublons compris)",
     """SELECT (SELECT count(*) FROM brut.reglements) - (SELECT count(*) FROM coeur.fact_reglement)
            - (SELECT count(*) FROM quarantaine.reglements)""", 0),
    ("reconciliation_reglements_montants", "reglements : montants bruts = montants du coeur + quarantaine",
     """SELECT round((SELECT sum(vers_nombre(montant)) FROM brut.reglements) - (SELECT sum(montant) FROM coeur.fact_reglement)
            - (SELECT coalesce(sum(montant), 0) FROM quarantaine.reglements), 2)""", 0),
    ("reconciliation_sinistres", "sinistres : lignes brutes = coeur + quarantaine",
     "SELECT (SELECT count(*) FROM brut.sinistres) - (SELECT count(*) FROM coeur.fact_sinistre) - (SELECT count(*) FROM quarantaine.sinistres)", 0),
    ("reconciliation_contrats", "contrats : lignes brutes = coeur + quarantaine",
     "SELECT (SELECT count(*) FROM brut.contrats) - (SELECT count(*) FROM coeur.dim_contrat) - (SELECT count(*) FROM quarantaine.contrats)", 0),
    ("reconciliation_audits", "audits : lignes brutes = coeur + quarantaine",
     "SELECT (SELECT count(*) FROM brut.audits) - (SELECT count(*) FROM coeur.fact_audit) - (SELECT count(*) FROM quarantaine.audits)", 0),
    ("reconciliation_clients", "clients : lignes brutes = clients conserves + doublons fusionnes + quarantaine",
     """SELECT (SELECT count(*) FROM brut.clients) - (SELECT count(*) - 1 FROM coeur.dim_client)
            - (SELECT count(*) FROM coeur.correspondance_client WHERE client_id <> client_id_source)
            - (SELECT count(*) FROM quarantaine.clients)""", 0),
    ("quarantaine_avec_motif", "toute ligne en quarantaine a un motif",
     """SELECT (SELECT count(*) FROM quarantaine.reglements WHERE motif IS NULL)
            + (SELECT count(*) FROM quarantaine.sinistres WHERE motif IS NULL)
            + (SELECT count(*) FROM quarantaine.contrats WHERE motif IS NULL)""", 0),
    ("pas_de_donnee_future", "aucune date de paiement ou de survenance apres l'extraction",
     """SELECT (SELECT count(*) FROM coeur.fact_reglement WHERE date_paiement > DATE '2025-06-30')
            + (SELECT count(*) FROM coeur.fact_sinistre WHERE date_survenance > DATE '2025-06-30')""", 0),
    ("journal_sans_erreur", "aucun fichier en erreur dans le dernier chargement de chaque fichier",
     """SELECT count(*) FROM (SELECT fichier, arg_max(statut, charge_le) AS dernier FROM brut.journal GROUP BY fichier)
        WHERE dernier <> 'ok'""", 0),
]


def executer(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS mart.resultats_tests (
            nom VARCHAR, description VARCHAR, attendu DOUBLE, obtenu DOUBLE, statut VARCHAR, execute_le TIMESTAMP)""")
    con.execute("DELETE FROM mart.resultats_tests")
    echecs = 0
    for nom, description, sql, attendu in TESTS:
        obtenu = con.execute(sql).fetchall()[0][0]
        obtenu = 0 if obtenu is None else obtenu
        ok = abs(obtenu - attendu) < 1e-9
        echecs += not ok
        con.execute("INSERT INTO mart.resultats_tests VALUES (?, ?, ?, ?, ?, now())",
                    [nom, description, attendu, obtenu, "ok" if ok else "echec"])
        print(f"  [{'ok' if ok else 'ECHEC'}] {nom}: {description} (obtenu {obtenu})")
    return echecs


def main():
    echecs = executer(connexion())
    if echecs:
        print(f"{echecs} test(s) en echec : chargement interrompu")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
