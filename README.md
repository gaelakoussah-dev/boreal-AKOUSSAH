# Boréal Assurances : entrepôt de données et analyse du portefeuille

Pipeline reproductible (ingestion, qualité, schéma en étoile, tests bloquants), analyses descriptives et dashboard Streamlit branché sur l'entrepôt.

## Lancer le projet en 5 commandes

```bash
pip install -r requirements.txt                       # 1. dépendances (Python 3.10+)
unzip sources_boreal.zip -d sources                   # 2. déposer les sources dans ./sources
python lancer.py                                      # 3. pipeline complet : ingestion → tests → marts → analyses (≈ 10 s)
python test_rejeu.py                                  # 4. preuve qu'un mois rejoué ne crée aucun doublon
streamlit run dashboard.py                            # 5. dashboard sur http://localhost:8501
```

Pour régénérer les documents chiffrés (catalogue, règles, chiffres clés, brouillon de note) : `python outils/exporter_docs.py`.
Exécution mensuelle automatique : `python surveiller.py` (boucle) ou, pour un planificateur, `python surveiller.py --une-fois` (voir `docs/architecture.md`).

Variables d'environnement facultatives : `BOREAL_SOURCES` (dossier des sources, défaut `sources`) et `BOREAL_BASE` (fichier de l'entrepôt, défaut `boreal.duckdb`).

## Organisation du dépôt

| Fichier | Rôle |
|---|---|
| `commun.py` | connexion, date d'extraction (30/06/2025), fonctions SQL de conversion |
| `ingestion.py` | sources → schéma `brut`, journal d'ingestion, rechargement d'un mois (`--recharger`) |
| `prep.py` | typage, 24 règles de qualité, quarantaine avec motif |
| `coeur.py` | déduplication des clients, schéma en étoile, exposition |
| `tests.py` | 10 tests bloquants, résultats dans `mart.resultats_tests` |
| `marts.py` | table du dashboard (`mart.portefeuille_mensuel`), tables d'exploitation, réconciliation mart/cœur |
| `analyses_techniques.py` | indicateurs, décomposition du ratio, intervalles de confiance, tests, queue des coûts (livrable 3) |
| `analyses_clients.py` | rétention, valeur client, délais, audits (livrable 4) |
| `lancer.py` | enchaîne les étapes, journalise, alerte (`alertes.log`) et s'arrête au premier échec |
| `surveiller.py` | déclenche `lancer.py` quand un fichier source arrive ou change |
| `test_rejeu.py` | rejeu d'un mois sur une copie de la base |
| `dashboard.py` | application Streamlit (lit uniquement le schéma `mart`) |
| `docs/` | architecture, lignage, RGPD, catalogue de données, règles de qualité, chiffres clés, note, préparation de la soutenance |

## Couches de l'entrepôt

`brut` (copie fidèle + fichier d'origine + date de chargement) → `prep` (typage, règles) → `quarantaine` (lignes écartées + motif) → `coeur` (étoile) → `mart` (tables du dashboard). Détail et schémas dans `docs/architecture.md`.

## Choix de méthode à connaître

- **Exposition** : durée de couverture en années (jours ÷ 365,25) par contrat et par année. Toutes les fréquences et taux de résiliation sont rapportés à cette durée.
- **Ratio sinistres/primes** : (règlements payés + réserves restantes des dossiers ouverts) ÷ primes acquises, sinistres rattachés à leur date de survenance.
- **Sinistres sans suite** : les statuts `REJETE` et `SANS_SUITE` (réserve nulle, aucun règlement) sont comptés à part.
- **Aucune ligne supprimée** : tout rejet va en quarantaine avec son motif, et `tests.py` vérifie que brut = cœur + quarantaine.

## Limites connues

- La source n'a pas de date de clôture : le délai de clôture est approché par la date du dernier paiement des dossiers clos.
- Les seuils de délais (5, 30 et 90 jours) et le seuil d'alerte du ratio (70 %) sont des hypothèses de travail, modifiables (`SEUILS` dans `analyses_clients.py`, champ de la barre latérale du dashboard).
- Le dashboard a été vérifié avec l'outil de test de Streamlit (aucune erreur, pages chargées en moins d'une seconde) mais n'a pas été relu visuellement dans un navigateur.
- Pour repartir de zéro (par exemple après un test volontairement faux), supprimer `boreal.duckdb` : le cœur ne se purge pas tout seul, il reçoit seulement de nouvelles lignes.
