# Préparer la soutenance (25 minutes)

## Déroulé conseillé des 15 minutes

1. **1 min** : le problème de Camille Roux (chiffres non réconciliables, doublons clients) et ce que vous livrez.
2. **3 min** : architecture en couches, un schéma, une phrase par couche.
3. **4 min, démonstration** : `python test_rejeu.py` (les 4 cas s'affichent en `[ok]`), puis `python lancer.py --etapes ingestion,prep,coeur,tests`.
4. **3 min** : qualité des données : 3 défauts concrets (paiements livrés deux fois, résiliations avant l'effet, doublons clients) avec leur volume et leur traitement.
5. **4 min, dashboard** : page Portefeuille (alerte et filtres), page Technique (décomposition, sinistre n° 1129), page Exploitation (tests, règles, délais).

## Questions probables et réponses

**Que se passe-t-il si le fichier d'un mois est livré deux fois ?**
Trois cas, tous testés dans `test_rejeu.py`. Même fichier, même contenu : l'empreinte MD5 est déjà dans `brut.journal`, il est ignoré. Rechargement forcé (`--recharger`) : les lignes du fichier sont supprimées puis réinsérées dans une transaction, l'état final est identique. Même contenu sous un autre nom : les lignes entrent dans le brut mais la règle R01 les met en quarantaine (même `paiement_id`), le cœur ne change pas. En plus, `fact_reglement` a une clé primaire sur `paiement_id`.

**Comment prouvez-vous que l'entrepôt réconcilie avec les sources ?**
Les tests `reconciliation_*` : lignes brutes = lignes du cœur + lignes en quarantaine, pour chaque source, et pour les règlements aussi en montants (même somme). Ensuite `marts.py` vérifie que exposition, primes, nombre de sinistres et règlements du mart sont identiques à ceux du cœur. C'est possible parce qu'aucune ligne n'est supprimée.

**Pourquoi ce grain pour la table de faits d'exposition ?**
Un contrat couvert 6 mois ne compte pas comme un contrat couvert 3 ans : il faut une durée. Le grain contrat × année civile est le plus fin dont on a besoin pour les analyses annuelles, reste petit (65 081 lignes) et permet de rattacher prime acquise et exposition à une année. Pour l'évolution mensuelle, `marts.py` calcule le même découpage par mois et un test vérifie que les totaux sont égaux.

**Pourquoi DuckDB ?**
Sources de 2,7 Mo, entrepôt de 30 Mo, une personne qui lance le pipeline : aucun serveur n'est justifié. Il lit directement les types SQL dont j'ai besoin, gère les transactions et se lance en une commande. Avec 100 fois plus de données, voir `docs/architecture.md`.

**Pourquoi ne pas avoir supprimé les lignes invalides ?**
Une ligne supprimée ne laisse aucune trace : on ne pourrait plus expliquer un écart de total. Elles sont en quarantaine avec leur motif.

**Pourquoi type 1 pour l'historique ?**
La source est un cliché à une date, sans mouvements : il n'y a pas d'historique à conserver. Le type 2 demanderait des dates de validité et une clé de substitution, utiles si on recevait chaque mois les changements de formule ou de région.

**Comment avez-vous choisi la clé de rapprochement des clients ?**
L'empreinte d'e-mail, présente partout. La date de naissance ajoutée à la clé aurait fait manquer deux doublons dont la date est vide dans les deux fiches. Contrôle : dans les 200 groupes, date de naissance, région et CSP concordent. Le doublon n'a aucun contrat : on garde l'identifiant qui porte les contrats.

**Pourquoi un bootstrap ?**
Les sinistres sont rares (4 % par année-police) et très inégaux (1 % des sinistres = un tiers du coût) : la loi normale est mauvaise pour le coût moyen et le ratio. Le bootstrap rééchantillonne les contrats, ce qui garde ensemble les sinistres d'un même contrat. La fréquence est aussi donnée avec un intervalle exact de Poisson.

**Pourquoi Mann-Whitney pour comparer les coûts de deux canaux ?**
Les coûts sont très asymétriques, une moyenne ne serait pas fiable. Le test compare les distributions sans supposer une loi. Les canaux comparés sont les deux plus gros en nombre de sinistres, choisis avant de regarder les coûts.

**Pourquoi ces deux zones pour le test de fréquence ?**
La zone 1 et la zone 5 : les deux extrémités de l'échelle de risque, choisies avant de regarder les résultats. Choisir les zones après coup, d'après les écarts, fausserait le test.

**Votre rétention est-elle fiable pour la cohorte 2024 ?**
Elle n'est calculée que sur les cases entièrement observables : tous les contrats de la cohorte ont dépassé l'anniversaire avant le 30/06/2025. La cohorte 2024 n'a aucune case à 1 an, celle de 2025 aucune case du tout.

**À qui s'applique votre taux de fraude ?**
Aux 372 dossiers audités uniquement, qui ne sont pas un échantillon aléatoire : leur coût moyen est 5 fois celui des non audités. Il ne dit rien du taux de fraude des 2 428 autres sinistres.

## Points faibles à connaître avant que le jury les trouve

- **Contrats écartés** : les contrats à prime nulle ou négative (25) et à résiliation avant l'effet (26) sont mis en quarantaine, avec 5 sinistres et 1 paiement qui en dépendent. On aurait pu corriger la prime ; on ne sait pas par quelle valeur. Mesurer l'impact : `quarantaine.sinistres`.
- **Sinistre n° 1129** : 2,48 M€ sur un seul dossier. C'est peut-être une erreur de saisie. Vous ne le savez pas : dites-le, et montrez le ratio plafonné.
- **`REJETE` et `SANS_SUITE`** : comptés comme « sans suite » dans le ratio, ils ont tous deux une réserve nulle. C'est une interprétation, à dire.
- **Délai de clôture** : approché par le dernier paiement, la source n'a pas de date de clôture.
- **Seuils de délais et d'alerte** : hypothèses de travail, pas des règles du client.
- **Rattachement des sinistres** : par date de survenance. Les règlements sont rattachés à l'année du sinistre, pas à l'année du paiement.
- **Rétention au niveau du contrat**, pas du client. La comparaison multi/mono-détenteur est donnée avec deux définitions parce que la première (détenir les deux produits un jour) favorise mécaniquement les clients qui sont restés longtemps.
