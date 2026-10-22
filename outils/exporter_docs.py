"""Genere les documents qui contiennent des chiffres ou des listes issus de l'entrepot :
catalogue de donnees, regles de qualite, chiffres cles, brouillon de note executive."""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from commun import BASE  # noqa: E402
from outils.descriptions import COLONNES, TABLES  # noqa: E402

con = duckdb.connect(BASE, read_only=True)
DOCS = Path("docs")
DOCS.mkdir(exist_ok=True)


def q(sql):
    return con.execute(sql).df()


def un(sql):
    return con.execute(sql).fetchall()[0][0]


def eur(x):
    return f"{x:,.0f} €".replace(",", " ")


def pct(x, d=1):
    return f"{100 * x:.{d}f} %".replace(".", ",")


def pts(x):
    return f"{x:+.1f}".replace(".", ",")


def pv(x):
    return f"{x:.2g}".replace(".", ",")


def nb(x):
    return f"{x:,.0f}".replace(",", " ")


# ------------------------------------------------------------------------------------------- catalogue
def catalogue():
    out = ["# Catalogue des données", "",
           "Généré par `outils/exporter_docs.py` à partir de l'entrepôt. Chaque table et chaque colonne des couches `coeur` et `mart` est définie.", "",
           "## Couches `brut`, `prep` et `quarantaine`", "",
           "- `brut.clients`, `brut.contrats`, `brut.sinistres`, `brut.reglements`, `brut.audits` : copie fidèle des fichiers sources, toutes colonnes en texte, "
           "plus `_fichier` (fichier d'origine) et `_charge_le` (date de chargement). Seuls les noms de colonnes sont harmonisés (un fichier de règlements a un ordre et un nom de colonne différents).",
           "- `brut.journal` : un chargement de fichier par ligne (fichier, source, empreinte, lignes lues, rejetées, durée, statut, message).",
           "- `prep.<source>_t` : lignes typées avec leur numéro `_ligne`. `prep.<source>_ok` : lignes retenues. `prep.rejets` : une ligne par règle déclenchée. "
           "`prep.regles` et `prep.qualite_regles` : catalogue des règles et volumes.",
           "- `quarantaine.<source>` : lignes écartées, avec la colonne `motif` (règles déclenchées).", ""]
    ts = q("""SELECT table_schema, table_name FROM information_schema.tables
              WHERE table_schema IN ('coeur', 'mart') ORDER BY table_schema, table_name""")
    manque = set()
    for schema in ["coeur", "mart"]:
        out += [f"## Schéma `{schema}`", ""]
        for t in ts[ts["table_schema"] == schema]["table_name"]:
            cle = f"{schema}.{t}"
            out += [f"### `{cle}`", "", TABLES.get(cle, "(à définir)"), "", "| Colonne | Type | Définition |", "|---|---|---|"]
            if cle not in TABLES:
                manque.add(cle)
            cols = q(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = '{schema}' AND table_name = '{t}' ORDER BY ordinal_position")
            for c, ty in zip(cols["column_name"], cols["data_type"]):
                if c not in COLONNES:
                    manque.add(cle + "." + c)
                out.append(f"| `{c}` | {ty} | {COLONNES.get(c, '(à définir)')} |")
            out.append("")
    (DOCS / "catalogue_donnees.md").write_text("\n".join(out), encoding="utf-8")
    return manque


# ------------------------------------------------------------------------------------------- regles
def regles():
    r = q("SELECT r.*, p.requete FROM mart.qualite_regles r JOIN prep.regles p USING (regle, source) ORDER BY regle")
    out = ["# Règles de qualité", "",
           f"{len(r)} règles contrôlées ; {int((r['volume'] > 0).sum())} détectent au moins une ligne. "
           "Traitement : **exclure** = la ligne va en quarantaine avec son motif ; **corriger** = la valeur est mise à vide ou ramenée à une valeur sûre, la ligne reste ; "
           "**signaler** = la ligne reste telle quelle, l'anomalie est comptée.", "",
           "| Règle | Source | Famille | Gravité | Traitement | Constat | Lignes | % de la source |", "|---|---|---|---|---|---|---|---|"]
    for x in r.itertuples():
        out.append(f"| {x.regle} | {x.source} | {x.famille} | {x.gravite} | {x.traitement} | {x.libelle} | {x.volume} | {str(x.part_pct).replace('.', ',')} |")
    out += ["", "## Requêtes", "", "Chaque requête renvoie les lignes concernées (`_ligne`) dans la table typée `prep.<source>_t`.", ""]
    for x in r.itertuples():
        out += [f"**{x.regle}** · {x.libelle}", "```sql", x.requete, "```", ""]
    (DOCS / "regles_qualite.md").write_text("\n".join(out), encoding="utf-8")


# ------------------------------------------------------------------------------------------- chiffres
def chiffres():
    g = q("SELECT * FROM mart.indicateurs_segments WHERE axe = 'global' AND annee IS NULL").iloc[0]
    ic = q("SELECT * FROM mart.ic_indicateurs WHERE perimetre = 'tous' AND periode = 'toutes'").set_index(["indicateur", "methode"])
    pl = q("SELECT * FROM mart.ratio_plafonne ORDER BY annee").set_index("annee")
    gros = q("""SELECT k.sinistre_id, g.produit, g.garantie, k.date_survenance, k.paye + k.reste_a_payer AS charge
                FROM coeur.sinistre_cout k JOIN coeur.dim_garantie g USING (garantie_id) ORDER BY 5 DESC LIMIT 1""").iloc[0]
    an_gros = gros["date_survenance"].year
    primes_an = pl.loc[an_gros, "primes"]
    z = q("SELECT modalite, frequence, prime_moyenne, ratio_charge FROM mart.indicateurs_segments WHERE axe = 'zone_risque' AND annee IS NULL ORDER BY modalite")
    z1, z5 = z.iloc[0], z.iloc[-1]
    zp = q("SELECT modalite, ratio_plafonne FROM mart.ratio_plafonne_segments WHERE axe = 'zone_risque' ORDER BY modalite")
    tz = q("SELECT * FROM mart.tests_stats").iloc[0]
    tc = q("SELECT * FROM mart.tests_stats").iloc[1]
    qc = q("SELECT indicateur, valeur FROM mart.queue_couts WHERE perimetre = 'tous'").set_index("indicateur")["valeur"]
    ar = q("SELECT * FROM mart.audits_resume").iloc[0]
    ad = q("SELECT * FROM mart.audits_criteres WHERE critere = 'délai de déclaration'").set_index("modalite")
    ret1 = q("SELECT avg(taux) AS t FROM mart.retention_cohortes WHERE produit = 'tous' AND annee_k = 1 AND complet").iloc[0]["t"]
    mb = q("SELECT * FROM mart.multidetention_retention WHERE annee_k = 1 AND definition LIKE 'B%'").set_index("groupe")
    mp = q("SELECT * FROM mart.multidetention_part").iloc[0]
    cr = q("SELECT * FROM mart.concentration_resume").iloc[0]
    dl = q("SELECT * FROM mart.delais_garantie WHERE garantie = 'toutes'").set_index("delai")
    dd = q("SELECT * FROM mart.doublons_clients").iloc[0]
    qr = q("SELECT source, count(*) AS n FROM (SELECT 'contrats' AS source FROM quarantaine.contrats UNION ALL SELECT 'sinistres' FROM quarantaine.sinistres "
           "UNION ALL SELECT 'reglements' FROM quarantaine.reglements UNION ALL SELECT 'audits' FROM quarantaine.audits "
           "UNION ALL SELECT 'clients' FROM quarantaine.clients) GROUP BY source").set_index("source")["n"].to_dict()
    ds = q("SELECT * FROM mart.decomposition_ratio ORDER BY annee")
    nb_ok = un("SELECT count(*) FROM mart.resultats_tests WHERE statut = 'ok'")
    nb_tests = un("SELECT count(*) FROM mart.resultats_tests")

    v = {}
    f = ic.loc[("frequence", "loi de Poisson exacte")]
    c_ = ic.loc[("cout_moyen", "bootstrap par contrat (1000 tirages)")]
    r_ = ic.loc[("ratio_charge", "bootstrap par contrat (1000 tirages)")]
    lignes = [
        "# Chiffres clés", "", "Généré par `outils/exporter_docs.py`. Tous les chiffres viennent des tables `mart` et `coeur`.", "",
        "## Portefeuille, toute la période",
        f"- Exposition : {nb(g.exposition)} années-police ; primes acquises : {eur(g.prime_acquise)} ; sinistres retenus : {nb(g.nb_sinistres)}.",
        f"- Fréquence : {pct(g.frequence, 2)} (IC 95 % : {pct(f.ic_bas, 2)} à {pct(f.ic_haut, 2)}).",
        f"- Coût moyen : {eur(g.cout_moyen)} (IC 95 % : {eur(c_.ic_bas)} à {eur(c_.ic_haut)}). Médiane : {eur(qc['mediane'])}.",
        f"- Ratio sinistres/primes : {pct(g.ratio_charge)} (IC 95 % : {pct(r_.ic_bas)} à {pct(r_.ic_haut)}). Ratio sur les seuls règlements payés : {pct(g.ratio_paye)}.",
        f"- Les 1 % de sinistres les plus chers pèsent {pct(qc['part_cout_top_1pct'], 0)} du coût total ; les 10 %, {pct(qc['part_cout_top_10pct'], 0)}.", "",
        "## Évolution annuelle du ratio"]
    for r in ds.itertuples():
        lignes.append(f"- {r.annee}{' (janv.-juin)' if r.annee_incomplete else ''} : {pct(r.ratio_precedent)} → {pct(r.ratio)} ({pts(r.variation_pts)} points : "
                      f"fréquence {pts(r.effet_frequence_pts)}, coût moyen {pts(r.effet_cout_pts)}, prime {pts(r.effet_prime_pts)}).")
    lignes += ["",
        "## Sinistre le plus coûteux",
        f"- Sinistre n° {gros.sinistre_id} ({gros.produit}, {gros.garantie}), survenu le {gros.date_survenance:%d/%m/%Y} : {eur(gros.charge)}, soit {pct(gros.charge / primes_an, 0)} des primes acquises {an_gros}.",
        f"- Ratio {an_gros} observé : {pct(pl.loc[an_gros, 'ratio_charge'])} ; avec sinistres plafonnés à {eur(pl.loc[an_gros, 'seuil_plafond'])} : {pct(pl.loc[an_gros, 'ratio_plafonne'])}.", "",
        "## Zones de risque",
        f"- Zone {z1.modalite} : fréquence {pct(z1.frequence, 2)}, prime moyenne {eur(z1.prime_moyenne)}. Zone {z5.modalite} : fréquence {pct(z5.frequence, 2)}, prime moyenne {eur(z5.prime_moyenne)}.",
        f"- Écart de fréquence : {pct(z5.frequence / z1.frequence - 1, 0)} ; écart de prime : {pct(z5.prime_moyenne / z1.prime_moyenne - 1, 0)}.",
        f"- Test exact de Poisson : p = {pv(tz.p_valeur)} ({tz.conclusion}).",
        f"- Ratio avec sinistres plafonnés : " + ", ".join(f"zone {a} {pct(b)}" for a, b in zip(zp.modalite, zp.ratio_plafonne)) + ".",
        f"- Coût par sinistre entre {tc.groupe_a} et {tc.groupe_b} : médianes {eur(tc.valeur_a)} et {eur(tc.valeur_b)}, p = {pv(tc.p_valeur)} ({tc.conclusion}).", "",
        "## Clients",
        f"- Rétention à un an (cohortes entièrement observables) : {pct(ret1, 0)}.",
        f"- {pct(mp.part_multi, 0)} des clients détiennent auto et habitation. Rétention à un an, client déjà équipé à la souscription : {pct(mb.loc['multi-détenteur', 'taux'])} "
        f"(IC {pct(mb.loc['multi-détenteur', 'ic_bas'])}-{pct(mb.loc['multi-détenteur', 'ic_haut'])}) contre {pct(mb.loc['mono-détenteur', 'taux'])} "
        f"(IC {pct(mb.loc['mono-détenteur', 'ic_bas'])}-{pct(mb.loc['mono-détenteur', 'ic_haut'])}) pour les autres.",
        f"- {pct(cr.part_deficitaires)} des clients sont déficitaires ({nb(cr.clients_deficitaires)} clients, {eur(cr.perte_totale)}). Les 10 % les plus rentables apportent {pct(cr.part_valeur_positive_top10, 0)} de la valeur positive.", "",
        "## Délais de gestion",
        f"- Déclaration : médiane {dl.loc['declaration', 'mediane']:.0f} jours, {pct(dl.loc['declaration', 'part_dans_seuil'], 0)} dans les {dl.loc['declaration', 'seuil_jours']} jours.",
        f"- Premier règlement : médiane {dl.loc['premier_reglement', 'mediane']:.0f} jours, {pct(dl.loc['premier_reglement', 'part_dans_seuil'], 0)} dans les {dl.loc['premier_reglement', 'seuil_jours']} jours.",
        f"- Clôture (dernier paiement des dossiers clos) : médiane {dl.loc['cloture', 'mediane']:.0f} jours, {pct(dl.loc['cloture', 'part_dans_seuil'], 0)} dans les {dl.loc['cloture', 'seuil_jours']} jours.", "",
        "## Audits antifraude (dossiers audités uniquement)",
        f"- {nb(ar.nb_audites)} sinistres audités sur {nb(ar.nb_sinistres)} ({pct(ar.taux_audit)}) ; {nb(ar.nb_fraudes_confirmees)} fraudes confirmées ({pct(ar.taux_confirmation_audites)} des audités).",
        f"- Délai de déclaration de plus de 7 jours : {ad.loc['plus de 7 jours', 'nb_fraudes']:.0f} fraudes sur {ad.loc['plus de 7 jours', 'nb_audites']:.0f} audits ({pct(ad.loc['plus de 7 jours', 'taux_confirmation'])}) ; "
        f"de 0 à 2 jours : {ad.loc['0 à 2 jours', 'nb_fraudes']:.0f} sur {ad.loc['0 à 2 jours', 'nb_audites']:.0f} ; de 3 à 7 jours : {ad.loc['3 à 7 jours', 'nb_fraudes']:.0f} sur {ad.loc['3 à 7 jours', 'nb_audites']:.0f}.",
        f"- Les audités coûtent en moyenne {eur(ar.cout_moyen_audites)} contre {eur(ar.cout_moyen_non_audites)} pour les non audités : le choix des dossiers n'est pas aléatoire.",
        f"- Règlements sur fraudes confirmées : {eur(ar.paye_fraudes_confirmees)}, dont {eur(ar.paye_fraudes_apres_audit)} payés après la date d'audit.", "",
        "## Qualité des données",
        f"- Clients : {dd.ids_fusionnes:.0f} doublons fusionnés sur {nb(dd.clients_source)} lignes ({str(dd.taux_doublons_pct).replace('.', ',')} %), tous avec des attributs concordants.",
        f"- Lignes en quarantaine : contrats {qr.get('contrats', 0)}, sinistres {qr.get('sinistres', 0)}, règlements {qr.get('reglements', 0)}, audits {qr.get('audits', 0)}.",
        f"- Tests : {nb_ok} sur {nb_tests} réussis."]
    (DOCS / "chiffres_cles.md").write_text("\n".join(lignes), encoding="utf-8")

    note = f"""# Note de synthèse (brouillon à relire et personnaliser)

**À : Camille Roux, directrice technique · De : MarketSense · Objet : où le portefeuille gagne ou perd de l'argent**

Boréal Assurances compte {nb(un("select count(*) from coeur.dim_contrat"))} contrats exploitables et {nb(g.nb_sinistres)} sinistres retenus entre 2020 et juin 2025. Sur cette période, le ratio sinistres/primes est de {pct(g.ratio_charge, 0)} (plausible entre {pct(r_.ic_bas, 0)} et {pct(r_.ic_haut, 0)}). Tous les chiffres viennent de l'entrepôt unique mis en place pour cette mission.

## Trois constats

1. **Un seul sinistre fausse le ratio de {an_gros}.** Le dossier n° {gros.sinistre_id} ({gros.garantie.replace('_', ' ')}, {gros.produit}) a coûté {eur(gros.charge)}, soit {pct(gros.charge / primes_an, 0)} des primes de l'année. Le ratio {an_gros} est de {pct(pl.loc[an_gros, 'ratio_charge'], 0)} ; il tombe à {pct(pl.loc[an_gros, 'ratio_plafonne'], 0)} si l'on ramène chaque sinistre à {eur(pl.loc[an_gros, 'seuil_plafond'])} au maximum. Les 1 % de sinistres les plus chers pèsent {pct(qc['part_cout_top_1pct'], 0)} du coût total.
2. **La prime des zones à risque élevé augmente moins vite que leur sinistralité.** Un contrat de la zone {z5.modalite} déclare {pct(z5.frequence / z1.frequence - 1, 0)} de sinistres de plus qu'en zone {z1.modalite} ({pct(z5.frequence, 1)} contre {pct(z1.frequence, 1)} par année de couverture, écart très significatif), mais sa prime n'est supérieure que de {pct(z5.prime_moyenne / z1.prime_moyenne - 1, 0)}. Hors sinistres exceptionnels, le ratio de la zone {z5.modalite} est le plus élevé ({pct(zp.iloc[-1].ratio_plafonne, 0)} contre {pct(zp.iloc[0].ratio_plafonne, 0)} en zone {z1.modalite}).
3. **Les fraudes confirmées se concentrent sur les déclarations tardives.** Parmi les dossiers audités, {ad.loc['plus de 7 jours', 'nb_fraudes']:.0f} fraudes sur {ad.loc['plus de 7 jours', 'nb_audites']:.0f} audits concernent des déclarations faites plus de 7 jours après le sinistre ({pct(ad.loc['plus de 7 jours', 'taux_confirmation'], 0)}), contre {ad.loc['0 à 2 jours', 'nb_fraudes']:.0f} sur {ad.loc['0 à 2 jours', 'nb_audites']:.0f} pour les déclarations de moins de 3 jours. Sur les fraudes confirmées, {eur(ar.paye_fraudes_apres_audit)} ont été payés après la date de l'audit.

## Trois décisions proposées

1. Faire vérifier le dossier n° {gros.sinistre_id} par la direction des sinistres, et définir une règle pour les sinistres exceptionnels (suivi à part, couverture de réassurance) afin qu'ils ne masquent plus la tendance.
2. Réexaminer la tarification de la zone {z5.modalite} : l'écart de prime ne suit pas l'écart de fréquence.
3. Soumettre à audit les déclarations tardives avant tout paiement, et suspendre le règlement pendant l'audit.

## Limites

- Le premier constat repose sur un dossier unique : si le montant est une erreur de saisie, l'année {an_gros} est à recalculer.
- Les audits ne couvrent que {pct(ar.taux_audit, 0)} des sinistres, choisis par le service antifraude : le taux de fraude ({pct(ar.taux_confirmation_audites, 0)}) ne vaut que pour les dossiers audités, et {ar.nb_fraudes_confirmees:.0f} cas restent un effectif faible.
- Les données de 2025 s'arrêtent fin juin ; les dossiers récents peuvent encore évoluer. 2020 est une année de montée en charge du portefeuille.
- {qr.get('contrats', 0)} contrats (prime nulle ou négative, résiliation avant l'effet) et leurs {qr.get('sinistres', 0)} sinistres ont été écartés et restent consultables en quarantaine.
- Le seuil d'alerte du tableau de bord (70 % de ratio) est une hypothèse à valider avec vous.
"""
    (DOCS / "note_executive_brouillon.md").write_text(note, encoding="utf-8")


if __name__ == "__main__":
    manque = catalogue()
    regles()
    chiffres()
    print("documents generes dans docs/")
    if manque:
        print("definitions manquantes :", sorted(manque))
