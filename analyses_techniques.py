import sys

import numpy as np
import pandas as pd
from scipy import stats

from commun import EXTRACTION, connexion, ecrire

AXES = ["produit", "zone_risque", "formule", "canal", "tranche_age", "region"]
MESURES = ["exposition", "prime_acquise", "nb_sinistres", "nb_sans_suite", "nb_rejetes", "paye", "reserve",
           "nb_resiliations"]
SOMMES = ", ".join(f"sum({m}) AS {m}" for m in MESURES)
PAIRES = [(2021, 2020, 12), (2022, 2021, 12), (2023, 2022, 12), (2024, 2023, 12), (2025, 2024, 6)]


def poisson_ic(n, e, alpha=0.05):
    bas = stats.chi2.ppf(alpha / 2, 2 * n) / 2 / e if n > 0 else 0.0
    haut = stats.chi2.ppf(1 - alpha / 2, 2 * n + 2) / 2 / e
    return bas, haut


def ajouter_ratios(d):
    d["charge"] = d["paye"] + d["reserve"]
    d["frequence"] = d["nb_sinistres"] / d["exposition"]
    d["frequence_declaree"] = (d["nb_sinistres"] + d["nb_sans_suite"] + d["nb_rejetes"]) / d["exposition"]
    d["cout_moyen"] = d["charge"] / d["nb_sinistres"].replace(0, np.nan)
    d["prime_moyenne"] = d["prime_acquise"] / d["exposition"]
    d["ratio_paye"] = d["paye"] / d["prime_acquise"]
    d["ratio_charge"] = d["charge"] / d["prime_acquise"]
    d["taux_resiliation"] = d["nb_resiliations"] / d["exposition"]
    return d


def indicateurs_segments(con):
    parts = []
    for axe in ["global"] + AXES:
        col = "'tous'" if axe == "global" else axe
        for annee in ["year(mois)", "CAST(NULL AS INTEGER)"]:
            parts.append(f"SELECT '{axe}' AS axe, CAST({col} AS VARCHAR) AS modalite, {annee} AS annee, {SOMMES} "
                         f"FROM mart.portefeuille_mensuel GROUP BY 1, 2, 3")
    d = con.execute(" UNION ALL ".join(parts)).df()
    d = ajouter_ratios(d)
    ic = [poisson_ic(n, e) if e > 0 else (np.nan, np.nan) for n, e in zip(d["nb_sinistres"], d["exposition"])]
    d["frequence_ic_bas"] = [x[0] for x in ic]
    d["frequence_ic_haut"] = [x[1] for x in ic]
    d["annee_incomplete"] = d["annee"] == EXTRACTION.year
    ecrire(con, "mart", "indicateurs_segments", d)
    return d


def base_periode(con, annee, mois_max, axe):
    col = "'tous'" if axe == "global" else axe
    return con.execute(f"""
        SELECT CAST({col} AS VARCHAR) AS modalite, sum(exposition) AS exposition, sum(prime_acquise) AS prime_acquise,
               sum(nb_sinistres) AS nb_sinistres, sum(paye + reserve) AS charge, sum(paye) AS paye
        FROM mart.portefeuille_mensuel WHERE year(mois) = {annee} AND month(mois) <= {mois_max} GROUP BY 1""").df()


def decomposition(con):
    lignes, segments, resultats = [], [], []
    for n, p, mmax in PAIRES:
        base = "annee complete" if mmax == 12 else "janvier a juin"
        a = base_periode(con, n, mmax, "global").iloc[0]
        b = base_periode(con, p, mmax, "global").iloc[0]
        f1, f0 = a.nb_sinistres / a.exposition, b.nb_sinistres / b.exposition
        c1, c0 = a.charge / a.nb_sinistres, b.charge / b.nb_sinistres
        p1, p0 = a.prime_acquise / a.exposition, b.prime_acquise / b.exposition
        r1, r0 = a.charge / a.prime_acquise, b.charge / b.prime_acquise
        logs = {"frequence": np.log(f1 / f0), "cout": np.log(c1 / c0), "prime": -np.log(p1 / p0)}
        total = sum(logs.values())
        lignes.append({
            "annee": n, "annee_precedente": p, "base": base, "ratio_precedent": r0, "ratio": r1, "variation_pts": 100 * (r1 - r0),
            "effet_frequence_pts": 100 * (r1 - r0) * logs["frequence"] / total,
            "effet_cout_pts": 100 * (r1 - r0) * logs["cout"] / total,
            "effet_prime_pts": 100 * (r1 - r0) * logs["prime"] / total,
            "frequence": f1, "frequence_precedente": f0, "cout_moyen": c1, "cout_moyen_precedent": c0,
            "prime_moyenne": p1, "prime_moyenne_precedente": p0,
            "exposition": a.exposition, "exposition_precedente": b.exposition,
            "annee_incomplete": mmax < 12, "precedente_en_montee": p == 2020})
        res0, res1 = b.prime_acquise - b.charge, a.prime_acquise - a.charge
        u0, u1 = res0 / b.exposition, res1 / a.exposition
        resultats.append({"annee": n, "base": base, "resultat_precedent": res0, "resultat": res1,
                          "effet_volume": (a.exposition - b.exposition) * u0,
                          "effet_resultat_unitaire": a.exposition * (u1 - u0)})
        for axe in AXES:
            sa, sb = base_periode(con, n, mmax, axe), base_periode(con, p, mmax, axe)
            m = sa.merge(sb, on="modalite", how="outer", suffixes=("", "_p")).fillna(0)
            m["contribution_pts"] = 100 * (m["charge"] / a.prime_acquise - m["charge_p"] / b.prime_acquise)
            m["ratio_segment"] = m["charge"] / m["prime_acquise"].replace(0, np.nan)
            m["ratio_segment_precedent"] = m["charge_p"] / m["prime_acquise_p"].replace(0, np.nan)
            m["poids_primes"] = m["prime_acquise"] / a.prime_acquise
            for r in m.itertuples():
                segments.append({"annee": n, "base": base, "axe": axe, "modalite": r.modalite,
                                 "contribution_pts": r.contribution_pts, "ratio_segment": r.ratio_segment,
                                 "ratio_segment_precedent": r.ratio_segment_precedent, "poids_primes": r.poids_primes,
                                 "nb_sinistres": r.nb_sinistres})
    ecrire(con, "mart", "decomposition_ratio", pd.DataFrame(lignes))
    ecrire(con, "mart", "decomposition_segments", pd.DataFrame(segments))
    ecrire(con, "mart", "decomposition_resultat", pd.DataFrame(resultats))


def matrices(con):
    d = con.execute("""
        SELECT c.contrat_id, c.produit, e.annee,
               e.exposition, e.prime_acquise,
               coalesce(s.nb, 0) AS nb, coalesce(s.charge, 0) AS charge, coalesce(s.paye, 0) AS paye,
               CASE WHEN year(c.date_resiliation) = e.annee THEN 1 ELSE 0 END AS resil
        FROM coeur.fact_exposition e JOIN coeur.dim_contrat c USING (contrat_id)
        LEFT JOIN (SELECT contrat_id, year(date_survenance) AS annee, count(*) FILTER (WHERE retenu) AS nb,
                          sum(paye + reste_a_payer) AS charge, sum(paye) AS paye
                   FROM coeur.sinistre_cout GROUP BY 1, 2) s ON s.contrat_id = e.contrat_id AND s.annee = e.annee""").df()
    return d


def intervalles(con, B=1000):
    d = matrices(con)
    annees = sorted(d["annee"].unique())
    cols = ["exposition", "prime_acquise", "nb", "charge", "paye", "resil"]
    rng = np.random.default_rng(42)
    out = []
    for perimetre in ["tous", "auto", "habitation"]:
        sub = d if perimetre == "tous" else d[d["produit"] == perimetre]
        ids = sub["contrat_id"].unique()
        pos = {c: i for i, c in enumerate(ids)}
        X = np.zeros((len(ids), len(cols) * len(annees)))
        for j, c in enumerate(cols):
            for k, a in enumerate(annees):
                t = sub[sub["annee"] == a]
                X[[pos[x] for x in t["contrat_id"]], j * len(annees) + k] = t[c].to_numpy()
        reps = []
        for _ in range(B):
            w = rng.multinomial(len(ids), np.full(len(ids), 1 / len(ids)))
            reps.append(w @ X)
        reps = np.array(reps)
        obs = X.sum(axis=0)

        def lire(v, c, k):
            return v[..., cols.index(c) * len(annees) + k]

        for k, a in enumerate(list(annees) + ["toutes"]):
            def agr(v, c):
                if a == "toutes":
                    return sum(lire(v, c, i) for i in range(len(annees)))
                return lire(v, c, k)
            for nom, num, den in [("frequence", "nb", "exposition"), ("ratio_charge", "charge", "prime_acquise"),
                                  ("ratio_paye", "paye", "prime_acquise"), ("prime_moyenne", "prime_acquise", "exposition"),
                                  ("taux_resiliation", "resil", "exposition"), ("cout_moyen", "charge", "nb")]:
                valeur = agr(obs, num) / agr(obs, den)
                tirages = agr(reps, num) / agr(reps, den)
                out.append({"perimetre": perimetre, "periode": str(a), "indicateur": nom, "valeur": valeur,
                            "ic_bas": np.nanpercentile(tirages, 2.5), "ic_haut": np.nanpercentile(tirages, 97.5),
                            "methode": "bootstrap par contrat (1000 tirages)"})
            n, e = agr(obs, "nb"), agr(obs, "exposition")
            bas, haut = poisson_ic(n, e)
            out.append({"perimetre": perimetre, "periode": str(a), "indicateur": "frequence", "valeur": n / e,
                        "ic_bas": bas, "ic_haut": haut, "methode": "loi de Poisson exacte"})
    ecrire(con, "mart", "ic_indicateurs", pd.DataFrame(out))


def sinistres_detail(con):
    return con.execute("""
        SELECT k.sinistre_id, c.produit, c.canal, c.zone_risque, c.formule, c.tranche_age, d.region,
               k.paye + k.reste_a_payer AS charge
        FROM coeur.sinistre_cout k JOIN coeur.dim_contrat c USING (contrat_id) JOIN coeur.dim_client d USING (client_id)
        WHERE k.retenu""").df()


def tests_et_queue(con):
    g = con.execute("""SELECT modalite, exposition, nb_sinistres FROM mart.indicateurs_segments
                       WHERE axe = 'zone_risque' AND annee IS NULL ORDER BY modalite""").df()
    za, zb = g.iloc[0], g.iloc[-1]
    p_attendu = za.exposition / (za.exposition + zb.exposition)
    res = stats.binomtest(int(za.nb_sinistres), int(za.nb_sinistres + zb.nb_sinistres), p_attendu)
    tests = [{"test": "fréquence entre deux zones (test exact conditionnel de Poisson)",
              "groupe_a": f"zone {za.modalite}", "groupe_b": f"zone {zb.modalite}",
              "valeur_a": za.nb_sinistres / za.exposition, "valeur_b": zb.nb_sinistres / zb.exposition,
              "nb_a": int(za.nb_sinistres), "nb_b": int(zb.nb_sinistres), "p_valeur": res.pvalue}]
    s = sinistres_detail(con)
    top = s["canal"].value_counts().index[:2]
    a, b = s[s["canal"] == top[0]]["charge"], s[s["canal"] == top[1]]["charge"]
    mw = stats.mannwhitneyu(a, b, alternative="two-sided")
    tests.append({"test": "coût par sinistre entre deux canaux (Mann-Whitney)", "groupe_a": f"canal {top[0]}",
                  "groupe_b": f"canal {top[1]}", "valeur_a": a.median(), "valeur_b": b.median(),
                  "nb_a": len(a), "nb_b": len(b), "p_valeur": mw.pvalue})
    t = pd.DataFrame(tests)
    t["conclusion"] = np.where(t["p_valeur"] < 0.05, "différence significative au seuil de 5 %",
                               "pas de différence démontrée au seuil de 5 %")
    ecrire(con, "mart", "tests_stats", t)

    lignes = []
    for perimetre in ["tous", "auto", "habitation"]:
        x = (s if perimetre == "tous" else s[s["produit"] == perimetre])["charge"].sort_values(ascending=False)
        tot = x.sum()
        vals = {"nb_sinistres": len(x), "moyenne": x.mean(), "mediane": x.median(), "q75": x.quantile(.75),
                "q90": x.quantile(.90), "q95": x.quantile(.95), "q99": x.quantile(.99), "maximum": x.max()}
        for q in (0.01, 0.05, 0.10):
            vals[f"part_cout_top_{int(q * 100)}pct"] = x.iloc[:max(1, int(round(len(x) * q)))].sum() / tot
        lignes += [{"perimetre": perimetre, "indicateur": k, "valeur": float(v)} for k, v in vals.items()]
    ecrire(con, "mart", "queue_couts", pd.DataFrame(lignes))

    seuil = s["charge"].quantile(.99)
    an = con.execute("""
        SELECT year(k.date_survenance) AS annee, k.paye + k.reste_a_payer AS charge
        FROM coeur.sinistre_cout k WHERE k.retenu""").df()
    an["plafonne"] = an["charge"].clip(upper=seuil)
    primes = con.execute("SELECT year(mois) AS annee, sum(prime_acquise) AS primes FROM mart.portefeuille_mensuel GROUP BY 1").df()
    r = an.groupby("annee").agg(charge=("charge", "sum"), plafonne=("plafonne", "sum"),
                                nb_sinistres=("charge", "size"), nb_au_dessus=("charge", lambda x: int((x > seuil).sum()))).reset_index()
    r = r.merge(primes, on="annee")
    r["ratio_charge"] = r["charge"] / r["primes"]
    r["ratio_plafonne"] = r["plafonne"] / r["primes"]
    r["seuil_plafond"] = seuil
    ecrire(con, "mart", "ratio_plafonne", r)

    s["plafonne"] = s["charge"].clip(upper=seuil)
    prim = con.execute("SELECT axe, modalite, prime_acquise AS primes FROM mart.indicateurs_segments WHERE annee IS NULL").df()
    segs = []
    for axe in AXES:
        g = s.groupby(axe).agg(charge=("charge", "sum"), plafonne=("plafonne", "sum"), nb_sinistres=("charge", "size"),
                               nb_au_dessus=("charge", lambda x: int((x > seuil).sum()))).reset_index().rename(columns={axe: "modalite"})
        g["axe"] = axe
        segs.append(g)
    segs = pd.concat(segs).merge(prim, on=["axe", "modalite"])
    segs["ratio_charge"] = segs["charge"] / segs["primes"]
    segs["ratio_plafonne"] = segs["plafonne"] / segs["primes"]
    ecrire(con, "mart", "ratio_plafonne_segments", segs)


def executer(con):
    indicateurs_segments(con)
    decomposition(con)
    intervalles(con)
    tests_et_queue(con)
    print("  analyses techniques ecrites dans mart")


def main():
    executer(connexion())
    return 0


if __name__ == "__main__":
    sys.exit(main())
