import altair as alt
import duckdb
import pandas as pd
import streamlit as st

from commun import BASE

BLEU, VERT, ROUGE, GRIS = "#1f4e79", "#2a9d8f", "#c0392b", "#9aa5b1"

st.set_page_config(page_title="Boréal Assurances · pilotage du portefeuille", layout="wide")


@st.cache_resource
def base():
    return duckdb.connect(BASE, read_only=True)


@st.cache_data(ttl=600, show_spinner=False)
def requete(sql):
    return base().execute(sql).df()


def eur(x):
    return f"{x:,.0f} €".replace(",", " ")


def pct(x, d=1):
    return f"{100 * x:.{d}f} %".replace(".", ",")


MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def f_pct(v, d=1):
    return "" if pd.isna(v) else pct(v, d)


def f_pts(v):
    return "" if pd.isna(v) else f"{v:+.1f}".replace(".", ",")


def f_nb(v, d=0):
    return "" if pd.isna(v) else f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


NOMS_AXES = {"zone_risque": "Zone de risque", "formule": "Formule", "canal": "Canal", "tranche_age": "Tranche d'âge",
             "produit": "Produit", "region": "Région"}


def liste(valeurs):
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in valeurs)


mois_dispo = requete("SELECT min(mois) AS a, max(mois) AS b FROM mart.portefeuille_mensuel").iloc[0]
annees = list(range(mois_dispo["a"].year, mois_dispo["b"].year + 1))
dernier_mois = mois_dispo["b"]

page = st.sidebar.radio("Page", ["Portefeuille", "Technique et clients", "Exploitation", "Définitions"])
avec_filtres = page in ("Portefeuille", "Technique et clients")
a0, a1 = annees[0], annees[-1]
choix = {c: [] for c in ("produit", "region", "canal", "zone_risque")}
choix.update({c + "_tous": True for c in ("produit", "region", "canal", "zone_risque")})
seuil = 0.70
if avec_filtres:
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Filtres**")
    a0, a1 = st.sidebar.select_slider("Période (années)", options=annees, value=(annees[0], annees[-1]))
    for col, nom in [("produit", "Produit"), ("region", "Région"), ("canal", "Canal"), ("zone_risque", "Zone de risque")]:
        options = requete(f"SELECT DISTINCT {col} AS v FROM mart.portefeuille_mensuel ORDER BY 1")["v"].tolist()
        choix[col] = st.sidebar.multiselect(nom, options, default=options)
        choix[col + "_tous"] = len(choix[col]) == len(options)
    seuil = st.sidebar.number_input("Seuil d'alerte du ratio sinistres/primes (%)", 30, 150, 70, step=5,
                                    help="Hypothèse de travail : au-delà de 70 %, il reste moins de 30 % des primes pour "
                                         "couvrir frais de gestion, commissions et marge. À valider avec la direction technique.") / 100


def clauses(avec_periode=True):
    c = []
    if avec_periode:
        c.append(f"year(mois) BETWEEN {a0} AND {a1}")
    for col in ("produit", "region", "canal", "zone_risque"):
        if not choix[col + "_tous"]:
            c.append(f"{col} IN ({liste(choix[col])})" if choix[col] else "1 = 0")
    return " AND ".join(c) if c else "1 = 1"


def entete(titre, sous_titre=None):
    st.title(titre)
    if sous_titre:
        st.caption(sous_titre)


def agregats(where, groupe=None):
    sel = f"{groupe} AS groupe, " if groupe else ""
    suite = f"GROUP BY {groupe}" if groupe else ""
    return requete(f"""
        SELECT {sel} sum(exposition) AS expo, sum(prime_acquise) AS primes, sum(nb_sinistres) AS n,
               sum(paye + reserve) AS charge, sum(paye) AS paye, sum(nb_resiliations) AS resil
        FROM mart.portefeuille_mensuel WHERE {where} {suite}""")


# ---------------------------------------------------------------------------------------------- Portefeuille
if page == "Portefeuille":
    entete("Où le portefeuille gagne ou perd de l'argent",
           f"Données jusqu'à {dernier_mois.strftime('%m/%Y')} · période {a0}-{a1} · chiffres issus de l'entrepôt (couche mart)")
    k = agregats(clauses()).iloc[0]
    if not k["expo"] or k["expo"] != k["expo"]:
        st.warning("Aucune donnée pour cette sélection de filtres.")
        st.stop()
    actifs = requete(f"""SELECT sum(contrats_actifs) AS v FROM mart.portefeuille_mensuel
                         WHERE {clauses(False)} AND mois = (SELECT max(mois) FROM mart.portefeuille_mensuel
                                                            WHERE year(mois) <= {a1})""").iloc[0]["v"]
    ratio = k["charge"] / k["primes"]
    c = st.columns(3)
    c[0].metric("Primes acquises", eur(k["primes"]))
    c[1].metric("Contrats actifs (fin de période)", f_nb(actifs))
    c[2].metric("Ratio sinistres / primes", pct(ratio))
    c = st.columns(3)
    c[0].metric("Fréquence (sinistres par année-police)", pct(k["n"] / k["expo"], 2))
    c[1].metric("Coût moyen par sinistre", eur(k["charge"] / k["n"]))
    c[2].metric("Taux de résiliation (par année-police)", pct(k["resil"] / k["expo"]))
    if ratio > seuil:
        st.error(f"Le ratio sinistres/primes ({pct(ratio)}) dépasse le seuil d'alerte de {pct(seuil, 0)} sur cette sélection.")
    else:
        st.success(f"Le ratio sinistres/primes ({pct(ratio)}) reste sous le seuil d'alerte de {pct(seuil, 0)}.")

    st.subheader("Évolution mensuelle comparée à l'année précédente")
    annee = st.selectbox("Année analysée", annees[1:], index=len(annees[1:]) - 2 if len(annees) > 3 else 0)
    m = requete(f"""
        SELECT year(mois) AS annee, month(mois) AS mois_n, sum(paye + reserve) / sum(prime_acquise) AS ratio,
               sum(prime_acquise) AS primes, sum(paye + reserve) AS charge
        FROM mart.portefeuille_mensuel WHERE {clauses(False)} AND year(mois) IN ({annee}, {annee - 1})
        GROUP BY 1, 2 ORDER BY 1, 2""")
    m["annee"] = m["annee"].astype(str)
    cur = m[m["annee"] == str(annee)]
    nb_alertes = int((cur["ratio"] > seuil).sum())
    titre = (f"{annee} : {nb_alertes} mois sur {len(cur)} au-dessus du seuil de {pct(seuil, 0)}"
             if nb_alertes else f"{annee} : aucun mois au-dessus du seuil de {pct(seuil, 0)}")
    plafond = max(1.5, 2 * seuil)
    hors = m[m["ratio"] > plafond]
    ligne = alt.Chart(m).mark_line(point=True, clip=True).encode(
        x=alt.X("mois_n:O", title="Mois"),
        y=alt.Y("ratio:Q", title="Ratio sinistres / primes", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, plafond], clamp=True)),
        color=alt.Color("annee:N", title="Année", scale=alt.Scale(range=[GRIS, BLEU])),
        tooltip=[alt.Tooltip("annee:N", title="Année"), alt.Tooltip("mois_n:O", title="Mois"),
                 alt.Tooltip("ratio:Q", title="Ratio", format=".1%"), alt.Tooltip("primes:Q", title="Primes acquises (€)", format=",.0f"),
                 alt.Tooltip("charge:Q", title="Charge de sinistres (€)", format=",.0f")])
    regle = alt.Chart(pd.DataFrame({"s": [seuil]})).mark_rule(color=ROUGE, strokeDash=[5, 4]).encode(y="s:Q")
    st.altair_chart((ligne + regle).properties(title=titre, height=320), width="stretch")
    if len(hors):
        st.warning("Hors de l'échelle du graphique : " + ", ".join(
            f"{MOIS[int(r.mois_n) - 1]} {r.annee} ({pct(r.ratio, 0)})" for r in hors.itertuples())
            + ". Un seul sinistre très coûteux suffit à produire un tel pic (voir la page Technique et clients).")
    st.caption("La charge de sinistres = règlements payés + réserves restantes sur les dossiers ouverts, rattachée au mois de survenance. "
               "Les mois récents peuvent encore évoluer (dossiers ouverts, déclarations tardives).")

    st.subheader("Primes et charge par année")
    y = requete(f"""
        SELECT year(mois) AS annee, sum(prime_acquise) AS primes, sum(paye + reserve) AS charge
        FROM mart.portefeuille_mensuel WHERE {clauses(False)} AND year(mois) BETWEEN {a0} AND {a1} GROUP BY 1 ORDER BY 1""")
    y["annee"] = y["annee"].astype(str)
    y["Résultat technique"] = y["primes"] - y["charge"]
    long = y.melt("annee", ["primes", "charge"], "type", "montant")
    long["type"] = long["type"].map({"primes": "Primes acquises", "charge": "Charge de sinistres"})
    meilleure = y.loc[y["Résultat technique"].idxmax()]
    graph = alt.Chart(long).mark_bar().encode(
        x=alt.X("annee:N", title="Année"), xOffset="type:N", y=alt.Y("montant:Q", title="Montant (€)", axis=alt.Axis(format="~s")),
        color=alt.Color("type:N", title="", scale=alt.Scale(domain=["Primes acquises", "Charge de sinistres"], range=[BLEU, ROUGE])),
        tooltip=[alt.Tooltip("annee:N", title="Année"), alt.Tooltip("type:N", title=""), alt.Tooltip("montant:Q", title="Montant (€)", format=",.0f")])
    st.altair_chart(graph.properties(title=f"Le résultat technique est le plus élevé en {meilleure['annee']} ({eur(meilleure['Résultat technique'])})",
                                     height=300), width="stretch")
    if str(annees[-1]) in y["annee"].values:
        st.caption(f"{annees[-1]} ne couvre que les six premiers mois (données jusqu'à fin juin).")

# ---------------------------------------------------------------------------------------- Technique et clients
elif page == "Technique et clients":
    entete("Comment le portefeuille se comporte, segment par segment",
           "Les blocs « ratio par segment » suivent les filtres. Décomposition, rétention et valeur client portent sur tout le portefeuille.")
    axes = {"Zone de risque": "zone_risque", "Formule": "formule", "Canal": "canal", "Tranche d'âge": "tranche_age",
            "Produit": "produit", "Région": "region"}
    nom_axe = st.selectbox("Découper le ratio par", list(axes))
    d = agregats(clauses(), axes[nom_axe])
    d = d[d["expo"] > 0].copy()
    d["ratio"] = d["charge"] / d["primes"]
    d["freq"] = d["n"] / d["expo"]
    d["cout"] = d["charge"] / d["n"]
    pire = d.loc[d["ratio"].idxmax()]
    graph = alt.Chart(d).mark_bar(color=BLEU).encode(
        y=alt.Y("groupe:N", sort="-x", title=nom_axe, axis=alt.Axis(labelOverlap=False)), x=alt.X("ratio:Q", title="Ratio sinistres / primes", axis=alt.Axis(format="%")),
        tooltip=[alt.Tooltip("groupe:N", title=nom_axe), alt.Tooltip("ratio:Q", title="Ratio", format=".1%"),
                 alt.Tooltip("freq:Q", title="Fréquence", format=".2%"), alt.Tooltip("cout:Q", title="Coût moyen (€)", format=",.0f"),
                 alt.Tooltip("expo:Q", title="Années-police", format=",.0f"), alt.Tooltip("n:Q", title="Sinistres")])
    regle = alt.Chart(pd.DataFrame({"s": [seuil]})).mark_rule(color=ROUGE, strokeDash=[5, 4]).encode(x="s:Q")
    st.altair_chart((graph + regle).properties(
        title=f"{nom_axe} : « {pire['groupe']} » a le ratio le plus élevé ({pct(pire['ratio'])}, {int(pire['n'])} sinistres)", height=60 + 34 * len(d)),
        width="stretch")
    st.caption("Avec peu de sinistres, un seul dossier très coûteux peut suffire à faire monter un ratio : vérifier le nombre de sinistres dans l'infobulle.")

    st.subheader("Pourquoi le ratio a bougé d'une année à l'autre")
    dec = requete("SELECT * FROM mart.decomposition_ratio ORDER BY annee")
    long = dec.melt(["annee", "base"], ["effet_frequence_pts", "effet_cout_pts", "effet_prime_pts"], "effet", "points")
    long["effet"] = long["effet"].map({"effet_frequence_pts": "Fréquence", "effet_cout_pts": "Coût moyen", "effet_prime_pts": "Prime moyenne"})
    long["annee"] = long["annee"].astype(str) + long["base"].map(lambda b: "" if b == "annee complete" else " (janv.-juin)")
    maxi = dec.loc[dec["variation_pts"].abs().idxmax()]
    cause = {"effet_frequence_pts": "la fréquence", "effet_cout_pts": "le coût moyen", "effet_prime_pts": "la prime moyenne"}[
        maxi[["effet_frequence_pts", "effet_cout_pts", "effet_prime_pts"]].abs().astype(float).idxmax()]
    st.altair_chart(alt.Chart(long).mark_bar().encode(
        x=alt.X("annee:N", title="Année comparée à la précédente"), y=alt.Y("points:Q", title="Points de ratio"),
        color=alt.Color("effet:N", title="Cause", scale=alt.Scale(range=[BLEU, ROUGE, VERT])),
        tooltip=[alt.Tooltip("annee:N", title="Année"), alt.Tooltip("effet:N", title="Cause"), alt.Tooltip("points:Q", title="Points de ratio", format="+.1f")]
    ).properties(title=f"La plus forte variation est en {int(maxi['annee'])} : {f_pts(maxi['variation_pts'])} points, portée par {cause}",
                 height=300), width="stretch")
    st.caption("Le volume de contrats n'apparaît pas : il joue autant sur les primes que sur les sinistres et s'annule dans le ratio. "
               "Il compte pour le résultat en euros (voir le détail repliable plus bas). 2025 est comparé à janvier-juin 2024. 2020 est une année de montée en charge.")
    an = st.selectbox("Segments qui contribuent le plus pour l'année", dec["annee"].tolist(), index=len(dec) - 2)
    seg = requete(f"SELECT axe, modalite, contribution_pts, ratio_segment_precedent, ratio_segment, nb_sinistres FROM mart.decomposition_segments WHERE annee = {an}")
    seg = seg[seg["axe"].isin(["zone_risque", "formule", "canal", "tranche_age", "produit"])].copy()
    seg["axe"] = seg["axe"].map(NOMS_AXES)
    c1, c2 = st.columns(2)
    cols = {"axe": "Axe", "modalite": "Segment", "contribution_pts": "Contribution (points)", "ratio_segment_precedent": "Ratio N-1", "ratio_segment": "Ratio N", "nb_sinistres": "Sinistres N"}
    fmt = {"Contribution (points)": f_pts, "Ratio N-1": f_pct, "Ratio N": f_pct, "Sinistres N": f_nb}
    c1.markdown("**Dégradation**")
    c1.dataframe(seg.nlargest(5, "contribution_pts").rename(columns=cols).style.format(fmt), hide_index=True, width="stretch")
    c2.markdown("**Amélioration**")
    c2.dataframe(seg.nsmallest(5, "contribution_pts").rename(columns=cols).style.format(fmt), hide_index=True, width="stretch")
    pl = requete("SELECT * FROM mart.ratio_plafonne ORDER BY annee")
    with st.expander("Effet des sinistres exceptionnels sur le ratio"):
        pl["Ratio observé"] = pl["ratio_charge"]
        pl["Ratio avec sinistres plafonnés"] = pl["ratio_plafonne"]
        st.dataframe(pl[["annee", "nb_sinistres", "nb_au_dessus", "Ratio observé", "Ratio avec sinistres plafonnés"]].rename(
            columns={"annee": "Année", "nb_sinistres": "Sinistres", "nb_au_dessus": "Sinistres au-dessus du plafond"}).style.format(
            {"Ratio observé": f_pct, "Ratio avec sinistres plafonnés": f_pct}), hide_index=True)
        st.caption(f"Plafond = coût du 99e centile des sinistres ({eur(pl['seuil_plafond'].iloc[0])}). Chaque sinistre plus cher est ramené à ce montant.")

    with st.expander("Variation du résultat technique en euros (volume et résultat par année-police)"):
        rs = requete("SELECT * FROM mart.decomposition_resultat ORDER BY annee")
        st.dataframe(rs.rename(columns={"annee": "Année", "base": "Base", "resultat_precedent": "Résultat précédent (€)", "resultat": "Résultat (€)",
                                        "effet_volume": "Effet volume (€)", "effet_resultat_unitaire": "Effet résultat par année-police (€)"}).style.format(
            {"Résultat précédent (€)": f_nb, "Résultat (€)": f_nb, "Effet volume (€)": f_nb, "Effet résultat par année-police (€)": f_nb}), hide_index=True, width="stretch")

    st.subheader("Combien de contrats restent après 1, 2, 3 ans")
    prod = st.radio("Produit", ["tous", "auto", "habitation"], horizontal=True)
    ret = requete(f"SELECT cohorte, annee_k, taux, nb_observables FROM mart.retention_cohortes WHERE produit = '{prod}' AND complet")
    if len(ret):
        ret["cohorte"] = ret["cohorte"].astype(str)
        base_c = alt.Chart(ret).encode(x=alt.X("annee_k:O", title="Années après la souscription"), y=alt.Y("cohorte:O", title="Cohorte de souscription"))
        carte = base_c.mark_rect().encode(color=alt.Color("taux:Q", scale=alt.Scale(scheme="blues", domain=[0.4, 0.9]), title="Contrats restants", legend=alt.Legend(format="%")),
                                          tooltip=[alt.Tooltip("cohorte:O", title="Cohorte"), alt.Tooltip("annee_k:O", title="Année"),
                                                   alt.Tooltip("taux:Q", title="Contrats restants", format=".1%"), alt.Tooltip("nb_observables:Q", title="Contrats observés")])
        texte = base_c.mark_text(fontSize=13).encode(text=alt.Text("taux:Q", format=".0%"), color=alt.condition(alt.datum.taux > 0.7, alt.value("white"), alt.value("black")))
        r1 = ret[ret["annee_k"] == 1]["taux"].mean()
        st.altair_chart((carte + texte).properties(title=f"Environ {pct(r1, 0)} des contrats sont encore là après un an, quelle que soit la cohorte", height=260), width="stretch")
        st.caption("Seules les cases entièrement observables sont affichées : tous les contrats de la cohorte ont eu le temps d'atteindre l'anniversaire avant fin juin 2025.")
    md = requete("SELECT * FROM mart.multidetention_part").iloc[0]
    mr = requete("SELECT * FROM mart.multidetention_retention WHERE annee_k = 1")
    st.markdown(f"**{pct(md['part_multi'], 0)}** des clients ({int(md['clients_multi']):,} sur {int(md['clients']):,}) détiennent à la fois auto et habitation.".replace(",", " "))
    mr = mr.rename(columns={"definition": "Définition", "groupe": "Groupe", "nb_observables": "Contrats observés", "taux": "Rétention à 1 an", "ic_bas": "IC bas", "ic_haut": "IC haut"})
    st.dataframe(mr[["Définition", "Groupe", "Contrats observés", "Rétention à 1 an", "IC bas", "IC haut"]].style.format(
        {"Rétention à 1 an": f_pct, "IC bas": f_pct, "IC haut": f_pct, "Contrats observés": f_nb}), hide_index=True)

    st.subheader("Concentration de la valeur client")
    cr = requete("SELECT * FROM mart.concentration_resume").iloc[0]
    par = requete("SELECT * FROM mart.pareto_valeur")
    ligne = alt.Chart(par).mark_line(color=BLEU).encode(
        x=alt.X("pct_clients:Q", title="Part des clients, des plus aux moins rentables (%)"),
        y=alt.Y("part_valeur_positive:Q", title="Part de la valeur positive cumulée", axis=alt.Axis(format="%")),
        tooltip=[alt.Tooltip("pct_clients:Q", title="Clients (%)"), alt.Tooltip("part_valeur_positive:Q", title="Valeur cumulée", format=".1%")])
    diag = alt.Chart(pd.DataFrame({"x": [0, 100], "y": [0, 1]})).mark_line(color=GRIS, strokeDash=[4, 4]).encode(x="x:Q", y="y:Q")
    st.altair_chart((ligne + diag).properties(
        title=f"Les 10 % de clients les plus rentables apportent {pct(cr['part_valeur_positive_top10'], 0)} de la valeur positive", height=300), width="stretch")
    st.markdown(f"{pct(cr['part_deficitaires'], 1)} des clients sont déficitaires (primes acquises inférieures aux sinistres payés) et cumulent {eur(abs(cr['perte_totale']))} de pertes.")
    pr = requete("SELECT * FROM mart.profils_valeur ORDER BY valeur_moyenne DESC")
    pr = pr.rename(columns={"groupe": "Groupe", "nb_clients": "Clients", "valeur_moyenne": "Valeur moyenne (€)", "primes_moyennes": "Primes (€)", "paye_moyen": "Sinistres payés (€)",
                            "nb_contrats_moyen": "Contrats", "age_moyen": "Âge moyen", "part_multi": "Auto + habitation", "part_auto": "Détient auto",
                            "part_habitation": "Détient habitation", "part_avec_sinistre_paye": "Avec sinistre payé"})
    st.dataframe(pr.style.format({"Clients": f_nb, "Valeur moyenne (€)": f_nb, "Primes (€)": f_nb, "Sinistres payés (€)": f_nb,
                                  "Contrats": lambda v: f_nb(v, 2), "Âge moyen": lambda v: f_nb(v, 1),
                                  "Auto + habitation": lambda v: f_pct(v, 0), "Détient auto": lambda v: f_pct(v, 0),
                                  "Détient habitation": lambda v: f_pct(v, 0), "Avec sinistre payé": lambda v: f_pct(v, 0)}), hide_index=True)

    with st.expander("Audits antifraude : qui est audité, et avec quel résultat"):
        ar = requete("SELECT * FROM mart.audits_resume").iloc[0]
        st.markdown(f"**{int(ar['nb_audites'])} sinistres audités** sur {int(ar['nb_sinistres'])} ({pct(ar['taux_audit'])}). "
                    f"Fraude confirmée pour **{int(ar['nb_fraudes_confirmees'])}** d'entre eux ({pct(ar['taux_confirmation_audites'])}). "
                    "Ce taux ne vaut que pour les dossiers audités, choisis par le service antifraude, pas pour l'ensemble des sinistres.")
        ac = requete("SELECT critere, modalite, nb_sinistres, nb_audites, taux_audit, nb_fraudes, taux_confirmation, ic_bas, ic_haut FROM mart.audits_criteres")
        st.dataframe(ac.rename(columns={"critere": "Critère", "modalite": "Modalité", "nb_sinistres": "Sinistres", "nb_audites": "Audités", "taux_audit": "Taux d'audit",
                                        "nb_fraudes": "Fraudes", "taux_confirmation": "Taux de confirmation", "ic_bas": "IC bas", "ic_haut": "IC haut"}).style.format(
            {"Taux d'audit": f_pct, "Taux de confirmation": f_pct, "IC bas": f_pct, "IC haut": f_pct, "Sinistres": f_nb, "Audités": f_nb}), hide_index=True)

# ---------------------------------------------------------------------------------------------- Exploitation
elif page == "Exploitation":
    entete("Les chiffres sont-ils fiables et les délais tenus ?", "État de la chaîne de données et gestion des sinistres")
    ch = requete("SELECT source, count(*) FILTER (WHERE statut = 'ok') AS fichiers_ok, count(*) FILTER (WHERE statut <> 'ok') AS erreurs, "
                 "max(charge_le) AS dernier_chargement, sum(lues) FILTER (WHERE statut = 'ok') AS lignes_lues, sum(rejetees) FILTER (WHERE statut = 'ok') AS lignes_rejetees "
                 "FROM mart.chargements GROUP BY source ORDER BY source")
    fr = requete("SELECT source, derniere_date_donnee FROM mart.fraicheur")
    ch = ch.merge(fr, on="source", how="left")
    ch["dernier_chargement"] = pd.to_datetime(ch["dernier_chargement"]).dt.strftime("%d/%m/%Y %H:%M")
    ch["derniere_date_donnee"] = pd.to_datetime(ch["derniere_date_donnee"]).dt.strftime("%d/%m/%Y").fillna("sans date")
    st.subheader("Dernier chargement par source")
    st.dataframe(ch.rename(columns={"source": "Source", "fichiers_ok": "Fichiers chargés", "erreurs": "Erreurs", "dernier_chargement": "Dernier chargement",
                                    "lignes_lues": "Lignes lues", "lignes_rejetees": "Rejetées à la lecture", "derniere_date_donnee": "Donnée la plus récente"}), hide_index=True)
    te = requete("SELECT nom, description, obtenu, statut, execute_le FROM mart.resultats_tests ORDER BY statut DESC, nom")
    nb_ok = int((te["statut"] == "ok").sum())
    (st.success if nb_ok == len(te) else st.error)(f"{nb_ok} tests sur {len(te)} réussis au dernier lancement ({te['execute_le'].max():%d/%m/%Y %H:%M}).")
    with st.expander("Détail des tests"):
        st.dataframe(te.rename(columns={"nom": "Test", "description": "Ce qui est vérifié", "obtenu": "Écart constaté", "statut": "Résultat", "execute_le": "Exécuté le"}), hide_index=True)

    st.subheader("Lignes écartées ou corrigées, par règle de qualité")
    q = requete("SELECT * FROM mart.qualite_regles")
    vus = q[q["volume"] > 0].copy()
    vus["etiquette"] = vus["regle"] + " · " + vus["libelle"]
    graph = alt.Chart(vus).mark_bar().encode(
        y=alt.Y("etiquette:N", sort="-x", title=None, axis=alt.Axis(labelLimit=520, labelOverlap=False)), x=alt.X("volume:Q", title="Lignes concernées"),
        color=alt.Color("traitement:N", title="Traitement", scale=alt.Scale(domain=["exclure", "corriger", "signaler"], range=[ROUGE, VERT, GRIS])),
        tooltip=[alt.Tooltip("regle:N", title="Règle"), alt.Tooltip("libelle:N", title="Constat"), alt.Tooltip("volume:Q", title="Lignes"),
                 alt.Tooltip("part_pct:Q", title="% de la source"), alt.Tooltip("gravite:N", title="Gravité"), alt.Tooltip("traitement:N", title="Traitement")])
    exclues = int(q[q["traitement"] == "exclure"]["volume"].sum())
    st.altair_chart(graph.properties(title=f"{len(vus)} règles sur {len(q)} détectent des anomalies ; {exclues} lignes partent en quarantaine, aucune n'est supprimée",
                                     height=max(240, 36 * len(vus))), width="stretch")

    st.subheader("Délais de gestion des sinistres")
    dl = requete("SELECT * FROM mart.delais_garantie")
    noms = {"declaration": "Déclaration (survenance → déclaration)", "premier_reglement": "Premier règlement (déclaration → 1er paiement)",
            "cloture": "Clôture (déclaration → dernier paiement des dossiers clos)"}
    delai = st.radio("Délai", list(noms), format_func=noms.get, horizontal=True)
    s = dl[dl["delai"] == delai].copy()
    seuil_j = int(s["seuil_jours"].iloc[0])
    gl = s[s["garantie"] == "toutes"].iloc[0]
    par_g = s[s["garantie"] != "toutes"].melt(["garantie"], ["mediane", "q90"], "indicateur", "jours")
    par_g["indicateur"] = par_g["indicateur"].map({"mediane": "Médiane", "q90": "9 dossiers sur 10 sous"})
    if len(par_g):
        g = alt.Chart(par_g).mark_bar().encode(
            y=alt.Y("garantie:N", title=None, axis=alt.Axis(labelLimit=320, labelOverlap=False)), x=alt.X("jours:Q", title="Jours"), yOffset="indicateur:N",
            color=alt.Color("indicateur:N", title="", scale=alt.Scale(range=[BLEU, GRIS])),
            tooltip=[alt.Tooltip("garantie:N", title="Garantie"), alt.Tooltip("indicateur:N", title=""), alt.Tooltip("jours:Q", title="Jours", format=".0f")])
        r = alt.Chart(pd.DataFrame({"s": [seuil_j]})).mark_rule(color=ROUGE, strokeDash=[5, 4]).encode(x="s:Q")
        st.altair_chart((g + r).properties(
            title=f"Seuil de {seuil_j} jours tenu pour {pct(gl['part_dans_seuil'], 0)} des dossiers (médiane {gl['mediane']:.0f} jours)", height=60 + 44 * s[s["garantie"] != "toutes"].shape[0]), width="stretch")
    tab = s.rename(columns={"garantie": "Garantie", "n": "Dossiers", "n_sans_valeur": "Sans valeur", "mediane": "Médiane", "q75": "75 %", "q90": "90 %", "q95": "95 %",
                            "maximum": "Maximum", "part_dans_seuil": f"Dans les {seuil_j} jours"})
    st.dataframe(tab[["Garantie", "Dossiers", "Sans valeur", "Médiane", "75 %", "90 %", "95 %", "Maximum", f"Dans les {seuil_j} jours"]].style.format(
        {"Médiane": f_nb, "75 %": f_nb, "90 %": f_nb, "95 %": f_nb, "Maximum": f_nb, "Dossiers": f_nb, "Sans valeur": f_nb, f"Dans les {seuil_j} jours": lambda v: f_pct(v, 0)}), hide_index=True)
    st.caption("Les seuils (5, 30 et 90 jours) sont des hypothèses de travail à confirmer avec le client. Les sinistres sans règlement n'ont pas de délai de premier règlement. "
               "La source ne contient pas de date de clôture : la clôture est approchée par la date du dernier paiement.")

# ------------------------------------------------------------------------------------------------ Définitions
else:
    entete("Définitions des indicateurs")
    st.markdown("""
**Année-police (exposition)** : durée de couverture d'un contrat, exprimée en années (jours couverts ÷ 365,25). Un contrat couvert 6 mois compte 0,5. Toute fréquence est rapportée à cette durée, jamais au nombre de contrats.

**Primes acquises** : prime annuelle × exposition. C'est la part de la prime qui correspond à la période réellement couverte.

**Contrats actifs** : contrats en cours le dernier jour du mois (effet passé, pas encore résiliés).

**Sinistre retenu** : sinistre ouvert ou clôturé. Les dossiers « rejeté » et « sans suite » n'ont ni réserve ni règlement et sont comptés à part.

**Fréquence** : sinistres retenus ÷ années-police, rattachés à la date de survenance.

**Charge de sinistres** : règlements payés + réserve restante des dossiers ouverts (réserve initiale moins ce qui est déjà payé, sans passer sous zéro).

**Coût moyen** : charge ÷ sinistres retenus.

**Prime moyenne** : primes acquises ÷ années-police.

**Ratio sinistres / primes** : charge ÷ primes acquises. Il ne tient pas compte des frais de gestion et de distribution.

**Taux de résiliation** : résiliations de la période ÷ années-police.

**Décomposition du ratio** : ratio = fréquence × coût moyen ÷ prime moyenne. La variation entre deux années est répartie entre ces trois causes à l'aide des logarithmes ; la somme des effets égale la variation totale.

**Contribution d'un segment** : charge du segment ÷ primes totales de l'année, comparée à l'année précédente. La somme des contributions des segments d'un même axe égale la variation du ratio.

**Rétention** : part des contrats encore en vigueur à l'anniversaire de leur souscription (1, 2, 3 ans...). Calculée seulement sur les contrats dont l'anniversaire tombe avant le 30/06/2025.

**Valeur client** : primes acquises − sinistres payés, sur tous les contrats du client (après fusion des doublons).

**Taux de confirmation de fraude** : fraudes confirmées ÷ dossiers audités. Ne s'applique qu'aux dossiers audités.
""")
