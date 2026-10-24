import sys

import pandas as pd

from commun import COUPURE, EXTRACTION, connexion, ecrire

E = f"DATE '{EXTRACTION}'"

TYPES = {
    "clients": f"""
        SELECT row_number() OVER (ORDER BY _fichier, rowid) AS _ligne, _fichier,
            vide(client_id) AS client_id,
            vers_date(date_naissance) AS date_naissance_lue,
            vide(date_naissance) AS date_naissance_brute,
            vide(region) AS region,
            vide(csp) AS csp,
            vide(consent_marketing) AS consentement_brut,
            CASE propre(consent_marketing)
                WHEN 'oui' THEN true WHEN 'o' THEN true WHEN '1' THEN true
                WHEN 'non' THEN false WHEN 'n' THEN false WHEN '0' THEN false END AS consentement,
            vide(email_hash) AS email_hash
        FROM brut.clients""",
    "contrats": f"""
        SELECT row_number() OVER (ORDER BY _fichier, rowid) AS _ligne, _fichier,
            vide(contrat_id) AS contrat_id,
            vide(client_id) AS client_id,
            propre(produit) AS produit,
            vers_date(date_effet) AS date_effet,
            vers_date(date_resiliation) AS date_resiliation_lue,
            propre(formule) AS formule,
            propre(canal_distribution) AS canal,
            vide(zone_risque) AS zone_risque,
            vers_nombre(franchise) AS franchise,
            vers_nombre(bonus_malus) AS bonus_malus_lu,
            vers_nombre(puissance_cv) AS puissance,
            vers_nombre(surface_m2) AS surface,
            vers_nombre(prime_annuelle) AS prime
        FROM brut.contrats""",
    "sinistres": f"""
        SELECT row_number() OVER (ORDER BY _fichier, rowid) AS _ligne, _fichier,
            vide(sinistre_id) AS sinistre_id,
            vide(contrat_id) AS contrat_id,
            vers_date(date_survenance) AS date_survenance,
            vers_date(date_declaration) AS date_declaration,
            propre(garantie) AS garantie,
            vide(statut) AS statut_brut,
            vers_nombre(reserve_initiale) AS reserve_lue
        FROM brut.sinistres""",
    "reglements": f"""
        SELECT row_number() OVER (ORDER BY _fichier, rowid) AS _ligne, _fichier,
            vide(paiement_id) AS paiement_id,
            vide(sinistre_id) AS sinistre_id,
            vers_date(date_paiement) AS date_paiement,
            vers_nombre(montant) AS montant
        FROM brut.reglements""",
    "audits": f"""
        SELECT row_number() OVER (ORDER BY _fichier, rowid) AS _ligne, _fichier,
            vide(sinistre_id) AS sinistre_id,
            vers_date(date_audit) AS date_audit,
            vide(fraude_confirmee) AS fraude_brute,
            CASE propre(fraude_confirmee)
                WHEN 'oui' THEN true WHEN 'o' THEN true WHEN '1' THEN true WHEN 'true' THEN true
                WHEN 'non' THEN false WHEN 'n' THEN false WHEN '0' THEN false WHEN 'false' THEN false
                END AS fraude
        FROM brut.audits""",
}

# colonnes corrigees ajoutees apres le typage : la valeur lue reste visible pour les regles
CORRECTIONS = {
    "clients": f"""
        SELECT *, CASE WHEN date_naissance_lue BETWEEN ({E} - INTERVAL 100 YEAR)::DATE
                       AND ({E} - INTERVAL 18 YEAR)::DATE THEN date_naissance_lue END AS date_naissance
        FROM prep.clients_t0""",
    "contrats": f"""
        SELECT *, CASE WHEN date_resiliation_lue <= {E} THEN date_resiliation_lue END AS date_resiliation,
            CASE WHEN bonus_malus_lu BETWEEN 0.5 AND 3.5 THEN bonus_malus_lu END AS bonus_malus
        FROM prep.contrats_t0""",
    "sinistres": """
        SELECT *, CASE WHEN reserve_lue >= 0 THEN reserve_lue END AS reserve_initiale,
            CASE WHEN replace(replace(lower(statut_brut), ' ', '_'), '-', '_') IN ('ouvert', 'cloture', 'rejete', 'sans_suite')
                 THEN replace(replace(lower(statut_brut), ' ', '_'), '-', '_') ELSE 'inconnu' END AS statut
        FROM prep.sinistres_t0""",
}

# (id, source, famille, gravite, traitement, libelle, requete renvoyant les _ligne concernees)
REGLES = [
    ("C01", "clients", "unicité", "critique", "exclure", "identifiant client absent ou en double (on garde la première ligne)",
     """SELECT _ligne FROM (SELECT _ligne, client_id, row_number() OVER (PARTITION BY client_id ORDER BY _fichier, _ligne) AS rang
        FROM prep.clients_t) WHERE client_id IS NULL OR rang > 1"""),
    ("C02", "clients", "complétude", "mineure", "signaler", "date de naissance absente",
     "SELECT _ligne FROM prep.clients_t WHERE date_naissance_brute IS NULL"),
    ("C03", "clients", "validité", "mineure", "corriger",
     "date de naissance illisible ou hors de 18-100 ans, ou consentement illisible (valeur mise à vide)",
     """SELECT _ligne FROM prep.clients_t
        WHERE (date_naissance_brute IS NOT NULL AND date_naissance IS NULL)
           OR (consentement_brut IS NOT NULL AND consentement IS NULL)"""),
    ("C04", "clients", "cohérence entre tables", "moyenne", "signaler",
     "client sans aucun contrat valide (souvent le doublon d'un autre client)",
     "SELECT _ligne FROM prep.clients_t WHERE client_id NOT IN (SELECT client_id FROM prep.contrats_ok WHERE client_id IS NOT NULL)"),

    ("K01", "contrats", "unicité", "critique", "exclure", "identifiant contrat absent ou en double (on garde la première ligne)",
     """SELECT _ligne FROM (SELECT _ligne, contrat_id, row_number() OVER (PARTITION BY contrat_id ORDER BY _fichier, _ligne) AS rang
        FROM prep.contrats_t) WHERE contrat_id IS NULL OR rang > 1"""),
    ("K02", "contrats", "validité", "critique", "exclure",
     "produit inconnu, ou date d'effet absente, illisible ou après la date d'extraction",
     f"""SELECT _ligne FROM prep.contrats_t
        WHERE produit IS NULL OR produit NOT IN ('auto', 'habitation') OR date_effet IS NULL OR date_effet > {E}"""),
    ("K03", "contrats", "cohérence temporelle", "majeure", "exclure", "résiliation avant ou le jour de l'effet",
     "SELECT _ligne FROM prep.contrats_t WHERE date_effet IS NOT NULL AND date_resiliation_lue <= date_effet"),
    ("K04", "contrats", "validité", "critique", "exclure", "prime absente ou négative ou nulle",
     "SELECT _ligne FROM prep.contrats_t WHERE prime IS NULL OR prime <= 0"),
    ("K05", "contrats", "validité", "moyenne", "corriger",
     "résiliation après la date d'extraction (contrat considéré actif), ou bonus-malus hors de 0,5-3,5 (mis à vide)",
     f"""SELECT _ligne FROM prep.contrats_t
        WHERE date_resiliation_lue > {E} OR (bonus_malus_lu IS NOT NULL AND bonus_malus IS NULL)"""),
    ("K06", "contrats", "cohérence entre tables", "moyenne", "signaler",
     "client absent du CRM (rattaché au client INCONNU), ou puissance, surface, zone, formule ou canal absent",
     """SELECT _ligne FROM prep.contrats_t
        WHERE client_id IS NULL OR client_id NOT IN (SELECT client_id FROM prep.clients_ok)
           OR (produit = 'auto' AND puissance IS NULL) OR (produit = 'habitation' AND surface IS NULL)
           OR zone_risque IS NULL OR formule IS NULL OR canal IS NULL"""),

    ("S01", "sinistres", "unicité", "critique", "exclure", "identifiant sinistre absent ou en double (on garde la première ligne)",
     """SELECT _ligne FROM (SELECT _ligne, sinistre_id, row_number() OVER (PARTITION BY sinistre_id ORDER BY _fichier, _ligne) AS rang
        FROM prep.sinistres_t) WHERE sinistre_id IS NULL OR rang > 1"""),
    ("S02", "sinistres", "validité", "critique", "exclure", "date de survenance ou de déclaration illisible ou après la date d'extraction",
     f"SELECT _ligne FROM prep.sinistres_t WHERE date_survenance IS NULL OR date_declaration IS NULL OR date_survenance > {E} OR date_declaration > {E}"),
    ("S03", "sinistres", "cohérence entre tables", "critique", "exclure",
     "contrat absent ou écarté (sinistre orphelin)",
     "SELECT _ligne FROM prep.sinistres_t WHERE contrat_id IS NULL OR contrat_id NOT IN (SELECT contrat_id FROM prep.contrats_ok)"),
    ("S04", "sinistres", "cohérence temporelle", "moyenne", "signaler",
     "déclaration avant la survenance (délai exclu des calculs)",
     "SELECT _ligne FROM prep.sinistres_t WHERE date_declaration < date_survenance"),
    ("S05", "sinistres", "cohérence temporelle", "moyenne", "signaler",
     "survenance en dehors de la période de couverture du contrat",
     f"""SELECT s._ligne FROM prep.sinistres_t s JOIN prep.contrats_ok c USING (contrat_id)
        WHERE s.date_survenance < c.date_effet OR s.date_survenance >= coalesce(c.date_resiliation, DATE '{COUPURE}')"""),
    ("S06", "sinistres", "validité", "moyenne", "corriger",
     "réserve absente ou négative (mise à vide, comptée 0), ou statut hors liste (classé 'inconnu')",
     "SELECT _ligne FROM prep.sinistres_t WHERE reserve_initiale IS NULL OR statut = 'inconnu'"),

    ("R01", "reglements", "unicité", "majeure", "exclure",
     "identifiant paiement absent, ou paiement déjà reçu dans un autre fichier ou une autre ligne (on garde le premier)",
     """SELECT _ligne FROM (SELECT _ligne, paiement_id, row_number() OVER (PARTITION BY paiement_id ORDER BY _fichier, _ligne) AS rang
        FROM prep.reglements_t) WHERE paiement_id IS NULL OR rang > 1"""),
    ("R02", "reglements", "unicité", "majeure", "signaler", "même paiement avec des montants différents",
     """SELECT _ligne FROM (SELECT _ligne, min(montant) OVER (PARTITION BY paiement_id) AS mini,
        max(montant) OVER (PARTITION BY paiement_id) AS maxi FROM prep.reglements_t WHERE paiement_id IS NOT NULL)
        WHERE mini <> maxi"""),
    ("R03", "reglements", "validité", "critique", "exclure",
     "date de paiement illisible ou après la date d'extraction, ou montant absent, non numérique ou négatif ou nul",
     f"SELECT _ligne FROM prep.reglements_t WHERE date_paiement IS NULL OR date_paiement > {E} OR montant IS NULL OR montant <= 0"),
    ("R04", "reglements", "cohérence entre tables", "critique", "exclure",
     "sinistre absent ou écarté (paiement orphelin)",
     "SELECT _ligne FROM prep.reglements_t WHERE sinistre_id IS NULL OR sinistre_id NOT IN (SELECT sinistre_id FROM prep.sinistres_ok)"),
    ("R05", "reglements", "cohérence entre tables", "moyenne", "signaler",
     "paiement avant la survenance du sinistre, ou sur un sinistre rejeté ou sans suite",
     """SELECT r._ligne FROM prep.reglements_t r JOIN prep.sinistres_ok s USING (sinistre_id)
        WHERE r.date_paiement < s.date_survenance OR s.statut IN ('sans_suite', 'rejete')"""),

    ("A01", "audits", "cohérence entre tables", "majeure", "exclure", "sinistre audité absent ou écarté",
     "SELECT _ligne FROM prep.audits_t WHERE sinistre_id IS NULL OR sinistre_id NOT IN (SELECT sinistre_id FROM prep.sinistres_ok)"),
    ("A02", "audits", "unicité", "majeure", "exclure",
     "résultat d'audit illisible, ou plusieurs audits pour un sinistre (on garde le plus récent)",
     """SELECT _ligne FROM (SELECT _ligne, fraude, row_number() OVER (PARTITION BY sinistre_id
        ORDER BY date_audit DESC NULLS LAST, _ligne DESC) AS rang FROM prep.audits_t WHERE sinistre_id IS NOT NULL)
        WHERE fraude IS NULL OR rang > 1"""),
    ("A03", "audits", "cohérence temporelle", "mineure", "signaler", "audit avant la déclaration du sinistre",
     """SELECT a._ligne FROM prep.audits_t a JOIN prep.sinistres_ok s USING (sinistre_id)
        WHERE a.date_audit < s.date_declaration"""),
]

TARDIVES = {"C04": "contrats"}
ORDRE = ["clients", "contrats", "sinistres", "reglements", "audits"]


def appliquer(con, regles):
    for id_, src, famille, gravite, traitement, libelle, sql in regles:
        con.execute(f"INSERT INTO prep.rejets SELECT ?, ?, ?, ?, _ligne FROM ({sql})",
                    [src, id_, traitement, libelle])


def traiter(con, source):
    con.execute(f"CREATE OR REPLACE TABLE prep.{source}_t0 AS {TYPES[source]}")
    if source in CORRECTIONS:
        con.execute(f"CREATE OR REPLACE TABLE prep.{source}_t AS {CORRECTIONS[source]}")
    else:
        con.execute(f"CREATE OR REPLACE TABLE prep.{source}_t AS SELECT * FROM prep.{source}_t0")
    appliquer(con, [r for r in REGLES if r[1] == source and r[0] not in TARDIVES])
    con.execute(f"""
        CREATE OR REPLACE TABLE quarantaine.{source} AS
        SELECT t.*, m.motif FROM prep.{source}_t t
        JOIN (SELECT _ligne, string_agg(regle || ' : ' || motif, ' | ' ORDER BY regle) AS motif
              FROM prep.rejets WHERE source = '{source}' AND traitement = 'exclure' GROUP BY _ligne) m
        USING (_ligne)""")
    con.execute(f"""
        CREATE OR REPLACE TABLE prep.{source}_ok AS
        SELECT * FROM prep.{source}_t t
        WHERE NOT EXISTS (SELECT 1 FROM quarantaine.{source} q WHERE q._ligne = t._ligne)""")


def executer(con):
    con.execute("CREATE OR REPLACE TABLE prep.rejets (source VARCHAR, regle VARCHAR, traitement VARCHAR, motif VARCHAR, _ligne BIGINT)")
    for source in ORDRE:
        traiter(con, source)
        appliquer(con, [r for r in REGLES if TARDIVES.get(r[0]) == source])
    regles = pd.DataFrame(REGLES, columns=["regle", "source", "famille", "gravite", "traitement", "libelle", "requete"])
    regles["requete"] = regles["requete"].str.split().str.join(" ")
    ecrire(con, "prep", "regles", regles)
    con.execute("""
        CREATE OR REPLACE TABLE prep.qualite_regles AS
        SELECT r.regle, r.source, r.famille, r.gravite, r.traitement, r.libelle,
               count(j._ligne) AS volume, b.total AS lignes_source,
               round(100.0 * count(j._ligne) / b.total, 2) AS part_pct
        FROM prep.regles r
        LEFT JOIN prep.rejets j ON j.regle = r.regle
        JOIN (SELECT 'clients' AS source, count(*) AS total FROM prep.clients_t
              UNION ALL SELECT 'contrats', count(*) FROM prep.contrats_t
              UNION ALL SELECT 'sinistres', count(*) FROM prep.sinistres_t
              UNION ALL SELECT 'reglements', count(*) FROM prep.reglements_t
              UNION ALL SELECT 'audits', count(*) FROM prep.audits_t) b ON b.source = r.source
        GROUP BY r.regle, r.source, r.famille, r.gravite, r.traitement, r.libelle, b.total
        ORDER BY r.regle""")
    for s in ORDRE:
        n = con.execute(f"SELECT count(*) FROM prep.{s}_ok").fetchall()[0][0]
        q = con.execute(f"SELECT count(*) FROM quarantaine.{s}").fetchall()[0][0]
        print(f"  {s}: {n} lignes conservees, {q} en quarantaine")


def main():
    con = connexion()
    executer(con)
    return 0


if __name__ == "__main__":
    sys.exit(main())
