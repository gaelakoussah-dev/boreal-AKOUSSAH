import pathlib
import sys

REGLES = r'''REGLES = [
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

'''

TESTS = r'''TESTS = [
    ("unicite_cles", "clés uniques : client, contrat, sinistre, paiement, et couple (contrat, année) de l'exposition",
     """SELECT (SELECT count(*) - count(DISTINCT client_id) FROM coeur.dim_client)
            + (SELECT count(*) - count(DISTINCT contrat_id) FROM coeur.dim_contrat)
            + (SELECT count(*) - count(DISTINCT sinistre_id) FROM coeur.fact_sinistre)
            + (SELECT count(*) - count(DISTINCT paiement_id) FROM coeur.fact_reglement)
            + (SELECT count(*) - count(DISTINCT (contrat_id, annee)) FROM coeur.fact_exposition)""", 0),
    ("integrite_referentielle", "chaque clé étrangère pointe vers une ligne existante (contrat, sinistre, garantie, règlement, audit, exposition)",
     """SELECT (SELECT count(*) FROM coeur.dim_contrat c WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_client d WHERE d.client_id = c.client_id))
            + (SELECT count(*) FROM coeur.fact_sinistre s WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_contrat c WHERE c.contrat_id = s.contrat_id))
            + (SELECT count(*) FROM coeur.fact_sinistre s WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_garantie g WHERE g.garantie_id = s.garantie_id))
            + (SELECT count(*) FROM coeur.fact_reglement r WHERE NOT EXISTS (SELECT 1 FROM coeur.fact_sinistre s WHERE s.sinistre_id = r.sinistre_id))
            + (SELECT count(*) FROM coeur.fact_audit a WHERE NOT EXISTS (SELECT 1 FROM coeur.fact_sinistre s WHERE s.sinistre_id = a.sinistre_id))
            + (SELECT count(*) FROM coeur.fact_exposition e WHERE NOT EXISTS (SELECT 1 FROM coeur.dim_contrat c WHERE c.contrat_id = e.contrat_id))""", 0),
    ("exposition_positive", "exposition strictement positive et au plus une année",
     "SELECT count(*) FROM coeur.fact_exposition WHERE exposition <= 0 OR exposition > 366 / 365.25", 0),
    ("exposition_totale", "exposition totale = jours de couverture cumulés des contrats / 365,25",
     """SELECT round(abs((SELECT sum(exposition) FROM coeur.fact_exposition) - (SELECT sum(
            least(coalesce(date_resiliation, DATE '2025-07-01'), DATE '2025-07-01') - date_effet) / 365.25
            FROM coeur.dim_contrat)), 6)""", 0),
    ("reconciliation_reglements_lignes", "règlements : lignes brutes = lignes du cœur + quarantaine (doublons compris)",
     """SELECT (SELECT count(*) FROM brut.reglements) - (SELECT count(*) FROM coeur.fact_reglement)
            - (SELECT count(*) FROM quarantaine.reglements)""", 0),
    ("reconciliation_reglements_montants", "règlements : montants bruts = montants du cœur + quarantaine",
     """SELECT round((SELECT sum(vers_nombre(montant)) FROM brut.reglements) - (SELECT sum(montant) FROM coeur.fact_reglement)
            - (SELECT coalesce(sum(montant), 0) FROM quarantaine.reglements), 2)""", 0),
    ("reconciliation_autres_sources", "contrats, sinistres, audits, clients : lignes brutes = cœur + quarantaine (+ doublons fusionnés pour les clients)",
     """SELECT abs((SELECT count(*) FROM brut.contrats) - (SELECT count(*) FROM coeur.dim_contrat) - (SELECT count(*) FROM quarantaine.contrats))
            + abs((SELECT count(*) FROM brut.sinistres) - (SELECT count(*) FROM coeur.fact_sinistre) - (SELECT count(*) FROM quarantaine.sinistres))
            + abs((SELECT count(*) FROM brut.audits) - (SELECT count(*) FROM coeur.fact_audit) - (SELECT count(*) FROM quarantaine.audits))
            + abs((SELECT count(*) FROM brut.clients) - (SELECT count(*) - 1 FROM coeur.dim_client)
                  - (SELECT count(*) FROM coeur.correspondance_client WHERE client_id <> client_id_source)
                  - (SELECT count(*) FROM quarantaine.clients))""", 0),
    ("quarantaine_avec_motif", "toute ligne en quarantaine a un motif",
     """SELECT (SELECT count(*) FROM quarantaine.reglements WHERE motif IS NULL)
            + (SELECT count(*) FROM quarantaine.sinistres WHERE motif IS NULL)
            + (SELECT count(*) FROM quarantaine.contrats WHERE motif IS NULL)""", 0),
    ("pas_de_donnee_future", "aucune date de paiement ou de survenance après l'extraction",
     """SELECT (SELECT count(*) FROM coeur.fact_reglement WHERE date_paiement > DATE '2025-06-30')
            + (SELECT count(*) FROM coeur.fact_sinistre WHERE date_survenance > DATE '2025-06-30')""", 0),
    ("journal_sans_erreur", "aucun fichier en erreur dans le dernier chargement de chaque fichier",
     """SELECT count(*) FROM (SELECT fichier, arg_max(statut, charge_le) AS dernier FROM brut.journal GROUP BY fichier)
        WHERE dernier <> 'ok'""", 0),
]


'''


def lire(f):
    return pathlib.Path(f).read_text(encoding="utf-8")


def ecrire(f, s):
    pathlib.Path(f).write_text(s, encoding="utf-8")


def bloc(f, debut, fin, nouveau):
    s = lire(f)
    i, j = s.index(debut), s.index(fin)
    ecrire(f, s[:i] + nouveau + s[j:])


def remplacer(f, paires):
    if not pathlib.Path(f).exists():
        print("  ignore (absent) :", f)
        return
    s = lire(f)
    for a, b in paires:
        s = s.replace(a, b)
    ecrire(f, s)


if "identifiant client absent ou en double" in lire("prep.py"):
    print("Deja applique : rien a faire.")
    sys.exit(0)

for f in ("prep.py", "tests.py", "test_rejeu.py"):
    ecrire(f + ".avant", lire(f))
bloc("prep.py", "REGLES = [", "TARDIVES = ", REGLES)
remplacer("prep.py", [('TARDIVES = {"C08": "contrats"}', 'TARDIVES = {"C04": "contrats"}')])
bloc("tests.py", "TESTS = [", "def executer(con):", TESTS)
remplacer("test_rejeu.py", [("(motif R02)", "(motif R01)")])
remplacer("README.md", [("typage, 42 règles de qualité", "typage, 24 règles de qualité"), ("| 22 tests bloquants", "| 10 tests bloquants")])
remplacer("docs/architecture.md", [("typage + 42 règles", "typage + 24 règles"), ("22 bloquants", "10 bloquants"), ("(règle R02)", "(règle R01)")])
remplacer("docs/plan_dossier.md", [("tableau des 42 règles", "tableau des 24 règles"), ("| 22 tests, dont réconciliations", "| 10 tests, dont réconciliations")])
remplacer("docs/soutenance.md", [("R02", "R01")])
print("Termine : 24 regles et 10 tests. Anciens fichiers gardes en *.avant")
