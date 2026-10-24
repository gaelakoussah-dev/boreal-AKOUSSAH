# Chiffres clés

Généré par `outils/exporter_docs.py`. Tous les chiffres viennent des tables `mart` et `coeur`.

## Portefeuille, toute la période
- Exposition : 45 166 années-police ; primes acquises : 19 979 938 € ; sinistres retenus : 1 957.
- Fréquence : 4,33 % (IC 95 % : 4,14 % à 4,53 %).
- Coût moyen : 6 005 € (IC 95 % : 4 407 € à 8 809 €). Médiane : 1 997 €.
- Ratio sinistres/primes : 58,8 % (IC 95 % : 42,6 % à 85,9 %). Ratio sur les seuls règlements payés : 56,2 %.
- Les 1 % de sinistres les plus chers pèsent 34 % du coût total ; les 10 %, 61 %.

## Évolution annuelle du ratio
- 2021 : 60,6 % → 41,1 % (-19,5 points : fréquence -9,3, coût moyen -10,2, prime +0,0).
- 2022 : 41,1 % → 52,2 % (+11,1 points : fréquence +3,3, coût moyen +7,7, prime +0,2).
- 2023 : 52,2 % → 92,7 % (+40,4 points : fréquence -7,9, coût moyen +48,2, prime +0,2).
- 2024 : 92,7 % → 49,6 % (-43,1 points : fréquence +0,2, coût moyen -43,4, prime +0,0).
- 2025 (janv.-juin) : 54,4 % → 44,6 % (-9,8 points : fréquence -0,2, coût moyen -9,7, prime +0,1).

## Sinistre le plus coûteux
- Sinistre n° 1129 (auto, collision), survenu le 31/03/2023 : 2 475 975 €, soit 53 % des primes acquises 2023.
- Ratio 2023 observé : 92,7 % ; avec sinistres plafonnés à 43 187 € : 39,3 %.

## Zones de risque
- Zone 1 : fréquence 3,42 %, prime moyenne 388 €. Zone 5 : fréquence 5,73 %, prime moyenne 503 €.
- Écart de fréquence : 68 % ; écart de prime : 30 %.
- Test exact de Poisson : p = 9,6e-10 (différence significative au seuil de 5 %).
- Ratio avec sinistres plafonnés : zone 1 41,3 %, zone 2 44,5 %, zone 3 44,9 %, zone 4 37,9 %, zone 5 50,3 %.
- Coût par sinistre entre canal agent et canal web : médianes 2 049 € et 2 008 €, p = 0,52 (pas de différence démontrée au seuil de 5 %).

## Clients
- Rétention à un an (cohortes entièrement observables) : 86 %.
- 35 % des clients détiennent auto et habitation. Rétention à un an, client déjà équipé à la souscription : 87,1 % (IC 85,8 %-88,2 %) contre 86,1 % (IC 85,5 %-86,7 %) pour les autres.
- 6,7 % des clients sont déficitaires (1 010 clients, -8 953 601 €). Les 10 % les plus rentables apportent 29 % de la valeur positive.

## Délais de gestion
- Déclaration : médiane 5 jours, 53 % dans les 5 jours.
- Premier règlement : médiane 49 jours, 27 % dans les 30 jours.
- Clôture (dernier paiement des dossiers clos) : médiane 83 jours, 54 % dans les 90 jours.

## Audits antifraude (dossiers audités uniquement)
- 372 sinistres audités sur 2 800 (13,3 %) ; 37 fraudes confirmées (9,9 % des audités).
- Délai de déclaration de plus de 7 jours : 36 fraudes sur 167 audits (21,6 %) ; de 0 à 2 jours : 1 sur 105 ; de 3 à 7 jours : 0 sur 100.
- Les audités coûtent en moyenne 17 570 € contre 3 250 € pour les non audités : le choix des dossiers n'est pas aléatoire.
- Règlements sur fraudes confirmées : 487 280 €, dont 397 791 € payés après la date d'audit.

## Qualité des données
- Clients : 200 doublons fusionnés sur 15 200 lignes (1,32 %), tous avec des attributs concordants.
- Lignes en quarantaine : contrats 51, sinistres 5, règlements 33, audits 0.
- Tests : 10 sur 10 réussis.