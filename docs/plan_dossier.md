# Plan du dossier PDF (20 à 30 pages)

Chaque chiffre cité doit renvoyer à une table ou à une requête. `docs/chiffres_cles.md` donne les valeurs à jour.

| Section | Pages | Contenu | Source dans le dépôt |
|---|---|---|---|
| 1. Contexte et démarche | 1 | mission, sources, périmètre | `README.md` |
| 2. Architecture (L1) | 3 | schéma, choix d'outils chiffrés, 100 fois plus de données | `docs/architecture.md` |
| 3. Ingestion (L1) | 3 | formats et défauts entre fichiers (encodage, colonne déplacée), journal, rechargement, test de rejeu | `ingestion.py`, `brut.journal`, `test_rejeu.py` |
| 4. Qualité (L2) | 4 | tableau des 24 règles avec requête, gravité, volume, traitement ; quarantaine ; impact des rejets | `docs/regles_qualite.md`, `prep.py` |
| 5. Déduplication et modèle (L2) | 3 | clé, taux, règle de survie ; schéma en étoile et grain ; historique | `docs/architecture.md`, `coeur.py` |
| 6. Tests (L2) | 1 | 10 tests, dont réconciliations | `tests.py`, `mart.resultats_tests` |
| 7. Indicateurs techniques (L3) | 3 | tableaux par produit, zone, formule, canal, âge, avec une phrase actionnable chacun | `mart.indicateurs_segments` |
| 8. Décomposition (L3) | 2 | fréquence, coût, prime ; segments ; années incomplètes ; sinistre n° 1129 | `mart.decomposition_*`, `mart.ratio_plafonne*` |
| 9. Rigueur statistique (L3) | 2 | intervalles, deux tests justifiés, queue des coûts | `mart.ic_indicateurs`, `mart.tests_stats`, `mart.queue_couts` |
| 10. Clients (L4) | 3 | rétention, multi-détention, valeur et concentration | `mart.retention_cohortes`, `mart.multidetention_*`, `mart.valeur_client` |
| 11. Délais et audits (L4) | 2 | quantiles par garantie, taux de confirmation et population | `mart.delais_garantie`, `mart.audits_*` |
| 12. Dashboard et exploitation (L5) | 2 | captures, orchestration, alertes, catalogue, lignage | `dashboard.py`, `docs/lignage.md`, `docs/catalogue_donnees.md` |
| 13. RGPD (L5) | 1 | présence par couche, conservation, effacement | `docs/rgpd.md` |
| Annexe | 1 | note exécutive d'une page | `docs/note_executive_brouillon.md` |

Conseils : une phrase de lecture sous chaque tableau ; dire à qui s'applique chaque chiffre (audités, cohortes observables, année incomplète) ; ne pas citer un chiffre sans sa requête ou sa table.
