import sys

import numpy as np
import pandas as pd

from commun import EXTRACTION, connexion, ecrire

SEUILS = {"declaration": 5, "premier_reglement": 30, "cloture": 90}


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


def contrats(con):
    d = con.execute("""
        SELECT contrat_id, client_id, produit, date_effet, date_resiliation, cohorte
        FROM coeur.dim_contrat WHERE client_id <> 'INCONNU'""").df()
    d["date_effet"] = pd.to_datetime(d["date_effet"])
    d["date_resiliation"] = pd.to_datetime(d["date_resiliation"])
    return d


def survie(d, k):
    seuil = d["date_effet"] + pd.DateOffset(years=k)
    observable = seuil <= pd.Timestamp(EXTRACTION)
    vivant = d["date_resiliation"].isna() | (d["date_resiliation"] > seuil)
    return observable, vivant


def retention(con):
    d = contrats(con)
    lignes = []
    for k in range(1, 6):
        obs, viv = survie(d, k)
        d2 = d.assign(observable=obs, vivant=viv)
        for produit, sub in [("tous", d2)] + [(p, g) for p, g in d2.groupby("produit")]:
            for cohorte, g in sub.groupby("cohorte"):
                o = g[g["observable"]]
                lignes.append({"cohorte": int(cohorte), "produit": produit, "annee_k": k, "nb_contrats": len(g),
                               "nb_observables": len(o), "nb_survivants": int(o["vivant"].sum()),
                               "taux": o["vivant"].mean() if len(o) else np.nan,
                               "complet": bool(len(o) == len(g))})
    ecrire(con, "mart", "retention_cohortes", pd.DataFrame(lignes))

    # multi-detention : clients (apres deduplication) ayant au moins un contrat auto et un contrat habitation
    par_client = d.groupby("client_id")["produit"].agg(lambda x: set(x))
    multi_un_jour = par_client.map(lambda s: {"auto", "habitation"} <= s)
    resume = pd.DataFrame([{
        "clients": len(par_client), "clients_multi": int(multi_un_jour.sum()),
        "part_multi": multi_un_jour.mean(),
        "clients_auto_seul": int(par_client.map(lambda s: s == {"auto"}).sum()),
        "clients_habitation_seul": int(par_client.map(lambda s: s == {"habitation"}).sum())}])
    ecrire(con, "mart", "multidetention_part", resume)

    # definition A : client multi-detenteur a un moment quelconque
    # definition B : client deja equipe de l'autre produit (contrat actif) a la souscription du contrat
    d["multi_a"] = d["client_id"].map(multi_un_jour)
    autres = d.merge(d[["client_id", "produit", "date_effet", "date_resiliation"]], on="client_id", suffixes=("", "_autre"))
    autres = autres[(autres["produit"] != autres["produit_autre"]) & (autres["date_effet_autre"] <= autres["date_effet"])
                    & (autres["date_resiliation_autre"].isna() | (autres["date_resiliation_autre"] > autres["date_effet"]))]
    d["multi_b"] = d["contrat_id"].isin(autres["contrat_id"])
    sortie = []
    for definition, col in [("A : multi-détenteur à un moment quelconque", "multi_a"),
                            ("B : déjà équipé de l'autre produit à la souscription", "multi_b")]:
        for k in (1, 2):
            obs, viv = survie(d, k)
            for groupe, masque in [("multi-détenteur", d[col]), ("mono-détenteur", ~d[col])]:
                m = obs & masque
                n, s = int(m.sum()), int((viv & m).sum())
                bas, haut = wilson(s, n)
                sortie.append({"definition": definition, "groupe": groupe, "annee_k": k, "nb_observables": n,
                               "nb_survivants": s, "taux": s / n if n else np.nan, "ic_bas": bas, "ic_haut": haut})
    ecrire(con, "mart", "multidetention_retention", pd.DataFrame(sortie))


def valeur_client(con):
    d = con.execute("""
        SELECT cl.client_id, cl.region, cl.csp, cl.date_naissance,
               count(DISTINCT c.contrat_id) AS nb_contrats,
               count(DISTINCT c.produit) AS nb_produits,
               bool_or(c.produit = 'auto') AS a_auto, bool_or(c.produit = 'habitation') AS a_hab,
               coalesce(sum(e.primes), 0) AS primes,
               coalesce(sum(s.paye), 0) AS paye
        FROM coeur.dim_client cl JOIN coeur.dim_contrat c USING (client_id)
        LEFT JOIN (SELECT contrat_id, sum(prime_acquise) AS primes FROM coeur.fact_exposition GROUP BY 1) e USING (contrat_id)
        LEFT JOIN (SELECT contrat_id, sum(paye) AS paye FROM coeur.sinistre_cout GROUP BY 1) s USING (contrat_id)
        WHERE cl.client_id <> 'INCONNU' GROUP BY cl.client_id, cl.region, cl.csp, cl.date_naissance""").df()
    d["valeur"] = d["primes"] - d["paye"]
    d = d.sort_values("valeur", ascending=False, kind="mergesort").reset_index(drop=True)
    d["rang_pct"] = (d.index + 1) / len(d)
    d["groupe"] = np.where(d["rang_pct"] <= .10, "10 % les plus rentables",
                           np.where(d["rang_pct"] > .90, "10 % les moins rentables", "80 % du milieu"))
    d["age"] = (pd.Timestamp(EXTRACTION) - pd.to_datetime(d["date_naissance"])).dt.days / 365.25
    d["multi"] = d["a_auto"] & d["a_hab"]
    ecrire(con, "mart", "valeur_client", d.drop(columns=["date_naissance"]))

    pos = d["valeur"].clip(lower=0)
    points = []
    for p in range(1, 101):
        n = int(np.ceil(len(d) * p / 100))
        points.append({"pct_clients": p, "part_valeur_positive": pos.iloc[:n].sum() / pos.sum()})
    ecrire(con, "mart", "pareto_valeur", pd.DataFrame(points))

    neg = d[d["valeur"] < 0]
    ecrire(con, "mart", "concentration_resume", pd.DataFrame([{
        "clients": len(d), "valeur_totale": d["valeur"].sum(), "primes_totales": d["primes"].sum(),
        "clients_deficitaires": len(neg), "part_deficitaires": len(neg) / len(d),
        "perte_totale": neg["valeur"].sum(),
        "part_valeur_positive_top10": pos.iloc[:int(np.ceil(len(d) * .1))].sum() / pos.sum(),
        "valeur_top10": d[d["groupe"] == "10 % les plus rentables"]["valeur"].sum(),
        "valeur_bottom10": d[d["groupe"] == "10 % les moins rentables"]["valeur"].sum()}]))

    profils = d.groupby("groupe").agg(
        nb_clients=("client_id", "size"), valeur_moyenne=("valeur", "mean"), primes_moyennes=("primes", "mean"),
        paye_moyen=("paye", "mean"), nb_contrats_moyen=("nb_contrats", "mean"), age_moyen=("age", "mean"),
        part_multi=("multi", "mean"), part_auto=("a_auto", "mean"), part_habitation=("a_hab", "mean"),
        part_avec_sinistre_paye=("paye", lambda x: (x > 0).mean())).reset_index()
    ecrire(con, "mart", "profils_valeur", profils)
    reg = d.groupby(["groupe", "csp"]).size().rename("nb").reset_index()
    reg["part"] = reg["nb"] / reg.groupby("groupe")["nb"].transform("sum")
    ecrire(con, "mart", "profils_valeur_csp", reg)


def delais(con):
    d = con.execute("""
        SELECT k.sinistre_id, g.garantie, g.produit, k.statut,
               date_diff('day', k.date_survenance, k.date_declaration) AS declaration,
               date_diff('day', k.date_declaration, k.premier_reglement) AS premier_reglement,
               CASE WHEN k.statut = 'cloture' THEN date_diff('day', k.date_declaration, k.dernier_reglement) END AS cloture
        FROM coeur.sinistre_cout k JOIN coeur.dim_garantie g USING (garantie_id)""").df()
    lignes = []
    for delai in ["declaration", "premier_reglement", "cloture"]:
        for garantie, sub in [("toutes", d)] + [(f"{p} - {g}", x) for (p, g), x in d.groupby(["produit", "garantie"])]:
            tot = len(sub)
            v = sub[delai].dropna()
            v = v[v >= 0]
            if len(v) == 0:
                continue
            lignes.append({"delai": delai, "garantie": garantie, "n": len(v), "n_sans_valeur": tot - len(v),
                           "mediane": v.median(), "q75": v.quantile(.75), "q90": v.quantile(.90),
                           "q95": v.quantile(.95), "maximum": v.max(), "seuil_jours": SEUILS[delai],
                           "part_dans_seuil": (v <= SEUILS[delai]).mean()})
    ecrire(con, "mart", "delais_garantie", pd.DataFrame(lignes))


def audits(con):
    d = con.execute("""
        SELECT k.sinistre_id, g.garantie, g.produit, k.statut, k.paye, k.paye + k.reste_a_payer AS charge,
               date_diff('day', k.date_survenance, k.date_declaration) AS delai_decl,
               a.fraude IS NOT NULL AS audite, a.fraude, a.date_audit, k.premier_reglement
        FROM coeur.sinistre_cout k JOIN coeur.dim_garantie g USING (garantie_id)
        LEFT JOIN coeur.fact_audit a USING (sinistre_id)""").df()
    d["fraude"] = d["fraude"].astype("boolean")
    d["tranche_charge"] = pd.cut(d["charge"], [-1, 0, 1000, 5000, 20000, np.inf],
                                 labels=["0 (sans indemnité)", "1 - 1 000", "1 000 - 5 000", "5 000 - 20 000", "plus de 20 000"]).astype(str)
    d["tranche_delai"] = pd.cut(d["delai_decl"], [-100, 2, 7, np.inf], labels=["0 à 2 jours", "3 à 7 jours", "plus de 7 jours"]).astype(str)
    criteres = [("garantie", "garantie"), ("produit", "produit"), ("tranche_charge", "tranche de coût du sinistre"),
                ("tranche_delai", "délai de déclaration"), ("statut", "statut du sinistre")]
    lignes = []
    for col, nom in criteres:
        for modalite, g in d.groupby(col):
            a = g[g["audite"]]
            k, n = int(a["fraude"].sum()), len(a)
            bas, haut = wilson(k, n)
            lignes.append({"critere": nom, "modalite": modalite, "nb_sinistres": len(g), "nb_audites": n,
                           "taux_audit": n / len(g), "nb_fraudes": k, "taux_confirmation": k / n if n else np.nan,
                           "ic_bas": bas, "ic_haut": haut, "paye_audites": a["paye"].sum(),
                           "paye_fraudes": a[a["fraude"] == True]["paye"].sum()})
    ecrire(con, "mart", "audits_criteres", pd.DataFrame(lignes))

    a = d[d["audite"]]
    nan = d[~d["audite"]]
    f = a[a["fraude"] == True]
    apres = con.execute("""
        SELECT coalesce(sum(r.montant), 0) FROM coeur.fact_audit a JOIN coeur.fact_reglement r USING (sinistre_id)
        WHERE a.fraude AND r.date_paiement > a.date_audit""").fetchall()[0][0]
    ecrire(con, "mart", "audits_resume", pd.DataFrame([{
        "nb_sinistres": len(d), "nb_audites": len(a), "taux_audit": len(a) / len(d),
        "nb_fraudes_confirmees": len(f), "taux_confirmation_audites": len(f) / len(a),
        "paye_total": d["paye"].sum(), "paye_audites": a["paye"].sum(), "part_paye_audite": a["paye"].sum() / d["paye"].sum(),
        "paye_fraudes_confirmees": f["paye"].sum(), "part_paye_fraudes_dans_paye_audite": f["paye"].sum() / a["paye"].sum(),
        "paye_fraudes_apres_audit": apres,
        "cout_moyen_audites": a["charge"].mean(), "cout_moyen_non_audites": nan[nan["charge"] > 0]["charge"].mean(),
        "cout_median_audites": a["charge"].median(), "cout_median_non_audites": nan[nan["charge"] > 0]["charge"].median()}]))


def executer(con):
    retention(con)
    valeur_client(con)
    delais(con)
    audits(con)
    print("  analyses clients et sinistres ecrites dans mart")


def main():
    executer(connexion())
    return 0


if __name__ == "__main__":
    sys.exit(main())
