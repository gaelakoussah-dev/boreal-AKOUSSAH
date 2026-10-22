import sys

from commun import COUPURE, EXTRACTION, connexion

CLES = "mois, produit, region, canal, zone_risque, formule, tranche_age"

SEGMENTS = """
    SELECT c.contrat_id, c.produit, d.region, c.canal, c.zone_risque, c.formule, c.tranche_age,
           c.prime, c.date_effet, c.date_resiliation
    FROM coeur.dim_contrat c JOIN coeur.dim_client d USING (client_id)"""


def portefeuille_mensuel(con):
    debut, = con.execute("SELECT date_trunc('month', min(date_effet))::DATE FROM coeur.dim_contrat").fetchall()[0]
    fin = EXTRACTION.replace(day=1)
    con.execute(f"""
        CREATE OR REPLACE TABLE mart.portefeuille_mensuel AS
        WITH mois AS (
            SELECT m::DATE AS mois, (m + INTERVAL 1 MONTH)::DATE AS suivant
            FROM generate_series(DATE '{debut}', DATE '{fin}', INTERVAL 1 MONTH) t(m)),
        seg AS ({SEGMENTS}),
        expo AS (
            SELECT mois, produit, region, canal, zone_risque, formule, tranche_age,
                   sum(jours / 365.25) AS exposition, sum(jours / 365.25 * prime) AS prime_acquise,
                   count(*) FILTER (WHERE actif) AS contrats_actifs
            FROM (SELECT m.mois, s.*,
                         least(coalesce(s.date_resiliation, DATE '{COUPURE}'), m.suivant, DATE '{COUPURE}')
                         - greatest(s.date_effet, m.mois) AS jours,
                         s.date_effet <= m.suivant - 1
                         AND coalesce(s.date_resiliation, DATE '{COUPURE}') > m.suivant - 1 AS actif
                  FROM seg s CROSS JOIN mois m)
            WHERE jours > 0 GROUP BY {CLES}),
        sin AS (
            SELECT date_trunc('month', k.date_survenance)::DATE AS mois, s.produit, s.region, s.canal,
                   s.zone_risque, s.formule, s.tranche_age,
                   count(*) FILTER (WHERE k.retenu) AS nb_sinistres,
                   count(*) FILTER (WHERE k.statut = 'sans_suite') AS nb_sans_suite,
                   count(*) FILTER (WHERE k.statut = 'rejete') AS nb_rejetes,
                   sum(k.paye) AS paye, sum(k.reste_a_payer) AS reserve
            FROM coeur.sinistre_cout k JOIN seg s USING (contrat_id) GROUP BY {CLES}),
        resil AS (
            SELECT date_trunc('month', date_resiliation)::DATE AS mois, produit, region, canal, zone_risque,
                   formule, tranche_age, count(*) AS nb_resiliations
            FROM seg WHERE date_resiliation IS NOT NULL GROUP BY {CLES})
        SELECT {CLES},
               coalesce(sum(exposition), 0) AS exposition, coalesce(sum(prime_acquise), 0) AS prime_acquise,
               coalesce(sum(contrats_actifs), 0)::INTEGER AS contrats_actifs,
               coalesce(sum(nb_sinistres), 0)::INTEGER AS nb_sinistres,
               coalesce(sum(nb_sans_suite), 0)::INTEGER AS nb_sans_suite,
               coalesce(sum(nb_rejetes), 0)::INTEGER AS nb_rejetes,
               coalesce(sum(paye), 0) AS paye, coalesce(sum(reserve), 0) AS reserve,
               coalesce(sum(nb_resiliations), 0)::INTEGER AS nb_resiliations
        FROM (SELECT * FROM expo UNION ALL BY NAME SELECT * FROM sin UNION ALL BY NAME SELECT * FROM resil)
        GROUP BY {CLES}""")


def exploitation(con):
    con.execute("""
        CREATE OR REPLACE TABLE mart.chargements AS
        SELECT fichier, source, lues, rejetees, round(duree_s, 3) AS duree_s, statut, message, charge_le
        FROM brut.journal""")
    con.execute("CREATE OR REPLACE TABLE mart.qualite_regles AS SELECT * FROM prep.qualite_regles")
    con.execute("""
        CREATE OR REPLACE TABLE mart.fraicheur AS
        SELECT 'contrats' AS source, max(date_effet) AS derniere_date_donnee,
               (SELECT max(charge_le) FROM brut.journal WHERE source = 'contrats') AS dernier_chargement
        FROM coeur.dim_contrat
        UNION ALL SELECT 'sinistres', max(date_declaration), (SELECT max(charge_le) FROM brut.journal WHERE source = 'sinistres')
        FROM coeur.fact_sinistre
        UNION ALL SELECT 'reglements', max(date_paiement), (SELECT max(charge_le) FROM brut.journal WHERE source = 'reglements')
        FROM coeur.fact_reglement
        UNION ALL SELECT 'audits', max(date_audit), (SELECT max(charge_le) FROM brut.journal WHERE source = 'audits')
        FROM coeur.fact_audit
        UNION ALL SELECT 'clients', NULL, (SELECT max(charge_le) FROM brut.journal WHERE source = 'clients')""")
    con.execute("""
        CREATE OR REPLACE TABLE mart.doublons_clients AS
        SELECT (SELECT count(*) FROM prep.clients_ok) AS clients_source,
               (SELECT count(*) FROM coeur.dim_client) - 1 AS personnes_distinctes,
               (SELECT count(*) FROM coeur.controle_doublons) AS groupes_en_double,
               (SELECT count(*) FROM coeur.correspondance_client WHERE client_id <> client_id_source) AS ids_fusionnes,
               (SELECT count(*) FROM coeur.controle_doublons WHERE memes_attributs) AS groupes_attributs_identiques,
               round(100.0 * (SELECT count(*) FROM coeur.correspondance_client WHERE client_id <> client_id_source)
                     / (SELECT count(*) FROM prep.clients_ok), 2) AS taux_doublons_pct""")


def verifier(con):
    a = con.execute("SELECT sum(exposition) FROM mart.portefeuille_mensuel").fetchall()[0][0]
    b = con.execute("SELECT sum(exposition) FROM coeur.fact_exposition").fetchall()[0][0]
    c = con.execute("SELECT sum(prime_acquise) FROM mart.portefeuille_mensuel").fetchall()[0][0]
    d = con.execute("SELECT sum(prime_acquise) FROM coeur.fact_exposition").fetchall()[0][0]
    e = con.execute("SELECT sum(nb_sinistres + nb_sans_suite + nb_rejetes) FROM mart.portefeuille_mensuel").fetchall()[0][0]
    f = con.execute("SELECT count(*) FROM coeur.fact_sinistre").fetchall()[0][0]
    g = con.execute("SELECT sum(paye) FROM mart.portefeuille_mensuel").fetchall()[0][0]
    h = con.execute("SELECT sum(montant) FROM coeur.fact_reglement").fetchall()[0][0]
    assert abs(a - b) < 1e-6, f"exposition mart {a} / coeur {b}"
    assert abs(c - d) < 1e-4, f"primes mart {c} / coeur {d}"
    assert e == f, f"sinistres mart {e} / coeur {f}"
    assert abs(g - h) < 1e-4, f"paye mart {g} / coeur {h}"
    print("  reconciliation mart / coeur : exposition, primes, sinistres, reglements identiques")


def executer(con):
    con.execute("BEGIN")
    try:
        portefeuille_mensuel(con)
        exploitation(con)
        verifier(con)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    n = con.execute("SELECT count(*) FROM mart.portefeuille_mensuel").fetchall()[0][0]
    print(f"  mart.portefeuille_mensuel: {n} lignes")


def main():
    executer(connexion())
    return 0


if __name__ == "__main__":
    sys.exit(main())
