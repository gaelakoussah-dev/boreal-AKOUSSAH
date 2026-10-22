import sys

from commun import COUPURE, EXTRACTION, connexion

DDL = """
CREATE TABLE IF NOT EXISTS coeur.dim_client (
    client_id VARCHAR PRIMARY KEY, date_naissance DATE, region VARCHAR, csp VARCHAR,
    consentement BOOLEAN, email_hash VARCHAR);
CREATE TABLE IF NOT EXISTS coeur.dim_segment_risque (
    segment_id VARCHAR PRIMARY KEY, produit VARCHAR, zone_risque VARCHAR, formule VARCHAR);
CREATE TABLE IF NOT EXISTS coeur.dim_garantie (
    garantie_id VARCHAR PRIMARY KEY, garantie VARCHAR, produit VARCHAR);
CREATE TABLE IF NOT EXISTS coeur.dim_contrat (
    contrat_id VARCHAR PRIMARY KEY, client_id VARCHAR, client_id_source VARCHAR, produit VARCHAR,
    formule VARCHAR, canal VARCHAR, zone_risque VARCHAR, franchise DOUBLE, bonus_malus DOUBLE,
    puissance DOUBLE, surface DOUBLE, prime DOUBLE, date_effet DATE, date_resiliation DATE,
    age_souscription INTEGER, tranche_age VARCHAR, cohorte INTEGER, segment_id VARCHAR);
CREATE TABLE IF NOT EXISTS coeur.fact_sinistre (
    sinistre_id VARCHAR PRIMARY KEY, contrat_id VARCHAR, garantie_id VARCHAR, date_survenance DATE,
    date_declaration DATE, statut VARCHAR, retenu BOOLEAN, reserve_initiale DOUBLE);
CREATE TABLE IF NOT EXISTS coeur.fact_reglement (
    paiement_id VARCHAR PRIMARY KEY, sinistre_id VARCHAR, date_paiement DATE, montant DOUBLE);
CREATE TABLE IF NOT EXISTS coeur.fact_audit (
    sinistre_id VARCHAR PRIMARY KEY, date_audit DATE, fraude BOOLEAN);
CREATE TABLE IF NOT EXISTS coeur.fact_exposition (
    contrat_id VARCHAR, annee INTEGER, jours INTEGER, exposition DOUBLE, prime_acquise DOUBLE);
"""


def executer(con):
    for ordre in DDL.split(";"):
        if ordre.strip():
            con.execute(ordre)

    # rapprochement des clients : meme empreinte d'e-mail = meme personne
    con.execute("""
        CREATE OR REPLACE TABLE coeur.correspondance_client AS
        SELECT c.client_id AS client_id_source,
               first_value(c.client_id) OVER (
                   PARTITION BY coalesce(c.email_hash, 'sans_email_' || c.client_id)
                   ORDER BY k.premier_effet NULLS LAST, c.client_id::BIGINT) AS client_id
        FROM prep.clients_ok c
        LEFT JOIN (SELECT client_id, min(date_effet) AS premier_effet
                   FROM prep.contrats_ok GROUP BY client_id) k USING (client_id)""")
    con.execute("""
        CREATE OR REPLACE TABLE coeur.controle_doublons AS
        SELECT c.email_hash, count(*) AS nb_ids, min(m.client_id) AS client_retenu,
               string_agg(c.client_id, ',' ORDER BY c.client_id::BIGINT) AS ids,
               count(DISTINCT coalesce(c.date_naissance_brute, '')) = 1 AND count(DISTINCT c.region) = 1
                   AND count(DISTINCT c.csp) = 1 AS memes_attributs
        FROM prep.clients_ok c JOIN coeur.correspondance_client m ON m.client_id_source = c.client_id
        WHERE c.email_hash IS NOT NULL GROUP BY c.email_hash HAVING count(*) > 1""")

    con.execute("""
        INSERT INTO coeur.dim_client
        SELECT c.client_id, c.date_naissance, coalesce(c.region, 'INCONNU'), coalesce(c.csp, 'INCONNU'),
               c.consentement, c.email_hash
        FROM prep.clients_ok c JOIN coeur.correspondance_client m ON m.client_id_source = c.client_id
        WHERE m.client_id = c.client_id
          AND NOT EXISTS (SELECT 1 FROM coeur.dim_client d WHERE d.client_id = c.client_id)""")
    con.execute("""
        INSERT INTO coeur.dim_client SELECT 'INCONNU', NULL, 'INCONNU', 'INCONNU', NULL, NULL
        WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_client WHERE client_id = 'INCONNU')""")
    con.execute("""
        UPDATE coeur.dim_client SET date_naissance = c.date_naissance,
            region = coalesce(c.region, 'INCONNU'), csp = coalesce(c.csp, 'INCONNU'), consentement = c.consentement
        FROM prep.clients_ok c WHERE c.client_id = coeur.dim_client.client_id""")

    con.execute("""
        INSERT INTO coeur.dim_contrat
        SELECT k.contrat_id, coalesce(d.client_id, 'INCONNU'), k.client_id, k.produit,
               coalesce(k.formule, 'inconnu'), coalesce(k.canal, 'inconnu'), coalesce(k.zone_risque, 'inconnu'),
               k.franchise, k.bonus_malus, k.puissance, k.surface, k.prime, k.date_effet, k.date_resiliation,
               a.age, CASE WHEN a.age IS NULL THEN 'inconnu' WHEN a.age < 25 THEN '18-24' WHEN a.age < 35 THEN '25-34'
                           WHEN a.age < 45 THEN '35-44' WHEN a.age < 55 THEN '45-54' WHEN a.age < 65 THEN '55-64'
                           ELSE '65+' END,
               year(k.date_effet),
               k.produit || '|' || coalesce(k.zone_risque, 'inconnu') || '|' || coalesce(k.formule, 'inconnu')
        FROM prep.contrats_ok k
        LEFT JOIN coeur.correspondance_client m ON m.client_id_source = k.client_id
        LEFT JOIN coeur.dim_client d ON d.client_id = m.client_id
        LEFT JOIN LATERAL (SELECT date_diff('year', d.date_naissance, k.date_effet) AS age) a ON true
        WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_contrat x WHERE x.contrat_id = k.contrat_id)""")
    con.execute("""
        UPDATE coeur.dim_contrat SET date_resiliation = k.date_resiliation, prime = k.prime
        FROM prep.contrats_ok k WHERE k.contrat_id = coeur.dim_contrat.contrat_id""")

    con.execute("""
        INSERT INTO coeur.dim_segment_risque
        SELECT DISTINCT segment_id, produit, zone_risque, formule FROM coeur.dim_contrat c
        WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_segment_risque s WHERE s.segment_id = c.segment_id)""")
    con.execute("""
        INSERT INTO coeur.dim_garantie
        SELECT DISTINCT c.produit || '|' || s.garantie, s.garantie, c.produit
        FROM prep.sinistres_ok s JOIN coeur.dim_contrat c USING (contrat_id)
        WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_garantie g WHERE g.garantie_id = c.produit || '|' || s.garantie)""")

    con.execute("""
        INSERT INTO coeur.fact_sinistre
        SELECT s.sinistre_id, s.contrat_id, c.produit || '|' || s.garantie, s.date_survenance, s.date_declaration,
               s.statut, s.statut IN ('ouvert', 'cloture'), coalesce(s.reserve_initiale, 0)
        FROM prep.sinistres_ok s JOIN coeur.dim_contrat c USING (contrat_id)
        WHERE NOT EXISTS (SELECT 1 FROM coeur.fact_sinistre f WHERE f.sinistre_id = s.sinistre_id)""")
    con.execute("""
        INSERT INTO coeur.fact_reglement
        SELECT s.paiement_id, s.sinistre_id, s.date_paiement, s.montant
        FROM prep.reglements_ok s
        WHERE NOT EXISTS (SELECT 1 FROM coeur.fact_reglement r WHERE r.paiement_id = s.paiement_id)""")
    con.execute("""
        INSERT INTO coeur.fact_audit
        SELECT a.sinistre_id, a.date_audit, a.fraude FROM prep.audits_ok a
        WHERE NOT EXISTS (SELECT 1 FROM coeur.fact_audit f WHERE f.sinistre_id = a.sinistre_id)""")

    annees = con.execute("SELECT min(year(date_effet)), year(DATE '%s') FROM coeur.dim_contrat" % EXTRACTION).fetchall()[0]
    con.execute("DELETE FROM coeur.fact_exposition")
    con.execute(f"""
        INSERT INTO coeur.fact_exposition
        SELECT contrat_id, annee, jours, jours / 365.25, prime * jours / 365.25 FROM (
            SELECT c.contrat_id, g.annee, c.prime,
                   least(coalesce(c.date_resiliation, DATE '{COUPURE}'), make_date(g.annee + 1, 1, 1), DATE '{COUPURE}')
                   - greatest(c.date_effet, make_date(g.annee, 1, 1)) AS jours
            FROM coeur.dim_contrat c, generate_series({annees[0]}, {annees[1]}) AS g(annee))
        WHERE jours > 0""")

    con.execute("""
        CREATE OR REPLACE VIEW coeur.sinistre_cout AS
        SELECT s.sinistre_id, s.contrat_id, s.garantie_id, s.statut, s.retenu, s.date_survenance, s.date_declaration,
               s.reserve_initiale,
               coalesce(sum(r.montant), 0) AS paye, count(r.paiement_id) AS nb_reglements,
               min(r.date_paiement) AS premier_reglement, max(r.date_paiement) AS dernier_reglement,
               CASE WHEN s.statut = 'ouvert' THEN greatest(s.reserve_initiale - coalesce(sum(r.montant), 0), 0)
                    ELSE 0 END AS reste_a_payer
        FROM coeur.fact_sinistre s LEFT JOIN coeur.fact_reglement r USING (sinistre_id)
        GROUP BY s.sinistre_id, s.contrat_id, s.garantie_id, s.statut, s.retenu, s.date_survenance,
                 s.date_declaration, s.reserve_initiale""")

    con.execute("""
        CREATE OR REPLACE TABLE coeur.dim_date AS
        SELECT d::DATE AS date_id, year(d) AS annee, quarter(d) AS trimestre, month(d) AS mois,
               date_trunc('month', d)::DATE AS mois_debut, dayofweek(d) AS jour_semaine
        FROM generate_series(DATE '2019-01-01', DATE '2026-12-31', INTERVAL 1 DAY) t(d)""")

    for t in ["dim_client", "dim_contrat", "dim_segment_risque", "dim_garantie", "fact_sinistre",
              "fact_reglement", "fact_audit", "fact_exposition"]:
        n = con.execute(f"SELECT count(*) FROM coeur.{t}").fetchall()[0][0]
        print(f"  coeur.{t}: {n} lignes")


def main():
    executer(connexion())
    return 0


if __name__ == "__main__":
    sys.exit(main())
