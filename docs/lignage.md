# Lignage d'un indicateur : le ratio sinistres/primes

```mermaid
flowchart LR
    A[contrats.csv] --> B1[brut.contrats]
    B[sinistres.jsonl] --> B2[brut.sinistres]
    C[reglements_AAAA_MM.csv] --> B3[brut.reglements]
    B1 --> P1[prep.contrats_t / contrats_ok]
    B2 --> P2[prep.sinistres_t / sinistres_ok]
    B3 --> P3[prep.reglements_t / reglements_ok]
    P1 --> D[coeur.dim_contrat]
    D --> E[coeur.fact_exposition\nprime acquise]
    P2 --> F[coeur.fact_sinistre]
    P3 --> G[coeur.fact_reglement]
    F --> H[coeur.sinistre_cout\npayé + reste à payer]
    G --> H
    E --> M[mart.portefeuille_mensuel]
    H --> M
    M --> V[dashboard : ratio mensuel\nratio par segment]
    M --> I[mart.indicateurs_segments\nmart.decomposition_ratio]
```

| Étape | Table | Calcul |
|---|---|---|
| Source | `contrats.csv` | `prime_annuelle`, `date_effet`, `date_resiliation` |
| Préparation | `prep.contrats_ok` | conversions de types ; contrats à prime ≤ 0 ou à résiliation ≤ effet en quarantaine |
| Cœur | `coeur.fact_exposition` | `jours / 365,25` et `prime × jours / 365,25` par contrat et par année |
| Source | `sinistres.jsonl`, `reglements_*.csv` | réserve initiale, statut, paiements |
| Cœur | `coeur.sinistre_cout` | `paye` = somme des règlements ; `reste_a_payer` = réserve − payé pour les dossiers ouverts |
| Mart | `mart.portefeuille_mensuel` | somme par mois et segment de `prime_acquise`, `paye`, `reserve` |
| Dashboard | page Portefeuille | `(paye + reserve) / prime_acquise` |

Contrôles sur ce chemin : `exposition_totale`, `reconciliation_reglements_*` (tests) et la réconciliation mart/cœur à la fin de `marts.py`.
