# Catalogue des données

Généré par `outils/exporter_docs.py` à partir de l'entrepôt. Chaque table et chaque colonne des couches `coeur` et `mart` est définie.

## Couches `brut`, `prep` et `quarantaine`

- `brut.clients`, `brut.contrats`, `brut.sinistres`, `brut.reglements`, `brut.audits` : copie fidèle des fichiers sources, toutes colonnes en texte, plus `_fichier` (fichier d'origine) et `_charge_le` (date de chargement). Seuls les noms de colonnes sont harmonisés (un fichier de règlements a un ordre et un nom de colonne différents).
- `brut.journal` : un chargement de fichier par ligne (fichier, source, empreinte, lignes lues, rejetées, durée, statut, message).
- `prep.<source>_t` : lignes typées avec leur numéro `_ligne`. `prep.<source>_ok` : lignes retenues. `prep.rejets` : une ligne par règle déclenchée. `prep.regles` et `prep.qualite_regles` : catalogue des règles et volumes.
- `quarantaine.<source>` : lignes écartées, avec la colonne `motif` (règles déclenchées).

## Schéma `coeur`

### `coeur.controle_doublons`

Un groupe de clients fusionnés par ligne, avec contrôle de cohérence des attributs.

| Colonne | Type | Définition |
|---|---|---|
| `email_hash` | VARCHAR | Empreinte pseudonymisée de l'e-mail, clé de rapprochement des clients. |
| `nb_ids` | BIGINT | Nombre d'identifiants dans le groupe de doublons. |
| `client_retenu` | VARCHAR | Identifiant conservé pour le groupe de doublons. |
| `ids` | VARCHAR | Identifiants des clients du groupe, séparés par des virgules. |
| `memes_attributs` | BOOLEAN | Vrai si les attributs des clients du groupe concordent. |

### `coeur.correspondance_client`

Pour chaque identifiant client de la source, l'identifiant conservé après fusion.

| Colonne | Type | Définition |
|---|---|---|
| `client_id_source` | VARCHAR | Identifiant client tel qu'il figure dans la source. |
| `client_id` | VARCHAR | Identifiant client conservé. |

### `coeur.dim_client`

Un client par personne réelle, après fusion des doublons. Ligne 'INCONNU' pour les contrats sans client.

| Colonne | Type | Définition |
|---|---|---|
| `client_id` | VARCHAR | Identifiant client conservé. |
| `date_naissance` | DATE | Date de naissance, vide si absente ou invraisemblable. |
| `region` | VARCHAR | Région du client. |
| `csp` | VARCHAR | Catégorie socioprofessionnelle. |
| `consentement` | BOOLEAN | Consentement marketing (booléen). |
| `email_hash` | VARCHAR | Empreinte pseudonymisée de l'e-mail, clé de rapprochement des clients. |

### `coeur.dim_contrat`

Un contrat par ligne : attributs du contrat, client retenu, tranche d'âge à la souscription, segment de risque.

| Colonne | Type | Définition |
|---|---|---|
| `contrat_id` | VARCHAR | Identifiant du contrat. |
| `client_id` | VARCHAR | Identifiant client conservé. |
| `client_id_source` | VARCHAR | Identifiant client tel qu'il figure dans la source. |
| `produit` | VARCHAR | auto ou habitation. |
| `formule` | VARCHAR | Formule de garantie (essentielle, confort, premium). |
| `canal` | VARCHAR | Canal de distribution (agent, web, courtier). |
| `zone_risque` | VARCHAR | Zone de risque de 1 à 5. |
| `franchise` | DOUBLE | Franchise en euros. |
| `bonus_malus` | DOUBLE | Coefficient bonus-malus (auto), valide entre 0,5 et 3,5. |
| `puissance` | DOUBLE | Puissance fiscale en chevaux (auto). |
| `surface` | DOUBLE | Surface du logement en m² (habitation). |
| `prime` | DOUBLE | Prime annuelle du contrat, en euros. |
| `date_effet` | DATE | Date de début de couverture. |
| `date_resiliation` | DATE | Premier jour non couvert, vide si le contrat est en cours. |
| `age_souscription` | INTEGER | Âge du client à la date d'effet du contrat. |
| `tranche_age` | VARCHAR | Tranche d'âge à la souscription. |
| `cohorte` | INTEGER | Année de souscription du contrat. |
| `segment_id` | VARCHAR | Clé du segment : produit|zone|formule. |

### `coeur.dim_date`

Calendrier jour par jour de 2019 à 2026.

| Colonne | Type | Définition |
|---|---|---|
| `date_id` | DATE | Jour du calendrier. |
| `annee` | BIGINT | Année civile (vide = toute la période selon la table). |
| `trimestre` | BIGINT | Trimestre. |
| `mois` | BIGINT | Premier jour du mois. |
| `mois_debut` | DATE | Premier jour du mois de la date. |
| `jour_semaine` | BIGINT | Jour de la semaine (0 = dimanche). |

### `coeur.dim_garantie`

Garanties par produit (une garantie comme 'vol' existe en auto et en habitation).

| Colonne | Type | Définition |
|---|---|---|
| `garantie_id` | VARCHAR | Clé de la garantie : produit|garantie. |
| `garantie` | VARCHAR | Garantie sollicitée. |
| `produit` | VARCHAR | auto ou habitation. |

### `coeur.dim_segment_risque`

Combinaisons produit × zone de risque × formule.

| Colonne | Type | Définition |
|---|---|---|
| `segment_id` | VARCHAR | Clé du segment : produit|zone|formule. |
| `produit` | VARCHAR | auto ou habitation. |
| `zone_risque` | VARCHAR | Zone de risque de 1 à 5. |
| `formule` | VARCHAR | Formule de garantie (essentielle, confort, premium). |

### `coeur.fact_audit`

Grain : un sinistre audité (dernier audit conservé).

| Colonne | Type | Définition |
|---|---|---|
| `sinistre_id` | VARCHAR | Identifiant du sinistre. |
| `date_audit` | DATE | Date de l'audit antifraude. |
| `fraude` | BOOLEAN | Fraude confirmée par l'audit (booléen). |

### `coeur.fact_exposition`

Grain : un contrat × une année civile. Durée de couverture et prime acquise.

| Colonne | Type | Définition |
|---|---|---|
| `contrat_id` | VARCHAR | Identifiant du contrat. |
| `annee` | INTEGER | Année civile (vide = toute la période selon la table). |
| `jours` | INTEGER | Jours de couverture dans l'année. |
| `exposition` | DOUBLE | Années-police : jours couverts ÷ 365,25. |
| `prime_acquise` | DOUBLE | Prime annuelle × exposition, en euros. |

### `coeur.fact_reglement`

Grain : un paiement.

| Colonne | Type | Définition |
|---|---|---|
| `paiement_id` | VARCHAR | Identifiant du paiement. |
| `sinistre_id` | VARCHAR | Identifiant du sinistre. |
| `date_paiement` | DATE | Date du règlement. |
| `montant` | DOUBLE | Montant payé, en euros. |

### `coeur.fact_sinistre`

Grain : un sinistre. Attributs du dossier à la déclaration.

| Colonne | Type | Définition |
|---|---|---|
| `sinistre_id` | VARCHAR | Identifiant du sinistre. |
| `contrat_id` | VARCHAR | Identifiant du contrat. |
| `garantie_id` | VARCHAR | Clé de la garantie : produit|garantie. |
| `date_survenance` | DATE | Date de survenance du sinistre. |
| `date_declaration` | DATE | Date de déclaration du sinistre. |
| `statut` | VARCHAR | Statut du dossier (ouvert, cloture, rejete, sans_suite) ou statut d'exécution. |
| `retenu` | BOOLEAN | Vrai pour un sinistre ouvert ou clôturé. |
| `reserve_initiale` | DOUBLE | Réserve constituée à l'ouverture du dossier, en euros. |

### `coeur.sinistre_cout`

Vue : sinistre + règlements cumulés + reste à payer des dossiers ouverts.

| Colonne | Type | Définition |
|---|---|---|
| `sinistre_id` | VARCHAR | Identifiant du sinistre. |
| `contrat_id` | VARCHAR | Identifiant du contrat. |
| `garantie_id` | VARCHAR | Clé de la garantie : produit|garantie. |
| `statut` | VARCHAR | Statut du dossier (ouvert, cloture, rejete, sans_suite) ou statut d'exécution. |
| `retenu` | BOOLEAN | Vrai pour un sinistre ouvert ou clôturé. |
| `date_survenance` | DATE | Date de survenance du sinistre. |
| `date_declaration` | DATE | Date de déclaration du sinistre. |
| `reserve_initiale` | DOUBLE | Réserve constituée à l'ouverture du dossier, en euros. |
| `paye` | DOUBLE | Règlements payés, en euros. |
| `nb_reglements` | BIGINT | Nombre de paiements du sinistre. |
| `premier_reglement` | DATE | Date du premier paiement du sinistre. |
| `dernier_reglement` | DATE | Date du dernier paiement du sinistre. |
| `reste_a_payer` | DOUBLE | Réserve initiale moins règlements, pour les dossiers ouverts. |

## Schéma `mart`

### `mart.audits_criteres`

Taux d'audit et taux de confirmation de fraude selon plusieurs critères.

| Colonne | Type | Définition |
|---|---|---|
| `critere` | VARCHAR | Critère de découpage des audits. |
| `modalite` | VARCHAR | Valeur de l'axe de découpage. |
| `nb_sinistres` | BIGINT | Sinistres retenus (ouverts ou clôturés). |
| `nb_audites` | BIGINT | Sinistres audités. |
| `taux_audit` | DOUBLE | Sinistres audités ÷ sinistres. |
| `nb_fraudes` | BIGINT | Fraudes confirmées. |
| `taux_confirmation` | DOUBLE | Fraudes confirmées ÷ sinistres audités. |
| `ic_bas` | DOUBLE | Borne basse de l'intervalle de confiance à 95 %. |
| `ic_haut` | DOUBLE | Borne haute de l'intervalle de confiance à 95 %. |
| `paye_audites` | DOUBLE | Règlements des sinistres audités. |
| `paye_fraudes` | DOUBLE | Règlements des sinistres dont la fraude est confirmée. |

### `mart.audits_resume`

Synthèse des audits : population, montants, comparaison audités / non audités.

| Colonne | Type | Définition |
|---|---|---|
| `nb_sinistres` | BIGINT | Sinistres retenus (ouverts ou clôturés). |
| `nb_audites` | BIGINT | Sinistres audités. |
| `taux_audit` | DOUBLE | Sinistres audités ÷ sinistres. |
| `nb_fraudes_confirmees` | BIGINT | Fraudes confirmées parmi les audits. |
| `taux_confirmation_audites` | DOUBLE | Fraudes confirmées ÷ sinistres audités. |
| `paye_total` | DOUBLE | Règlements totaux. |
| `paye_audites` | DOUBLE | Règlements des sinistres audités. |
| `part_paye_audite` | DOUBLE | Part des règlements totaux portant sur des sinistres audités. |
| `paye_fraudes_confirmees` | DOUBLE | Règlements totaux des fraudes confirmées. |
| `part_paye_fraudes_dans_paye_audite` | DOUBLE | Part des règlements audités portant sur des fraudes confirmées. |
| `paye_fraudes_apres_audit` | DOUBLE | Règlements postérieurs à l'audit sur des fraudes confirmées. |
| `cout_moyen_audites` | DOUBLE | Coût moyen des sinistres audités. |
| `cout_moyen_non_audites` | DOUBLE | Coût moyen des sinistres non audités ayant une indemnité. |
| `cout_median_audites` | DOUBLE | Coût médian des sinistres audités. |
| `cout_median_non_audites` | DOUBLE | Coût médian des sinistres non audités ayant une indemnité. |

### `mart.chargements`

Copie du journal d'ingestion (un chargement de fichier par ligne).

| Colonne | Type | Définition |
|---|---|---|
| `fichier` | VARCHAR | Nom du fichier source. |
| `source` | VARCHAR | Source de données. |
| `lues` | INTEGER | Lignes lues dans le fichier. |
| `rejetees` | INTEGER | Lignes rejetées à la lecture du fichier. |
| `duree_s` | DOUBLE | Durée en secondes. |
| `statut` | VARCHAR | Statut du dossier (ouvert, cloture, rejete, sans_suite) ou statut d'exécution. |
| `message` | VARCHAR | Message d'erreur éventuel. |
| `charge_le` | TIMESTAMP | Horodatage du chargement. |

### `mart.concentration_resume`

Chiffres de synthèse de la concentration de la valeur client.

| Colonne | Type | Définition |
|---|---|---|
| `clients` | BIGINT | Nombre de clients. |
| `valeur_totale` | DOUBLE | Valeur cumulée de tous les clients. |
| `primes_totales` | DOUBLE | Primes acquises totales des clients. |
| `clients_deficitaires` | BIGINT | Clients dont la valeur est négative. |
| `part_deficitaires` | DOUBLE | Part des clients déficitaires. |
| `perte_totale` | DOUBLE | Somme des valeurs négatives. |
| `part_valeur_positive_top10` | DOUBLE | Part de la valeur positive apportée par les 10 % de clients les plus rentables. |
| `valeur_top10` | DOUBLE | Valeur cumulée des 10 % de clients les plus rentables. |
| `valeur_bottom10` | DOUBLE | Valeur cumulée des 10 % de clients les moins rentables. |

### `mart.decomposition_ratio`

Explication de la variation annuelle du ratio : fréquence, coût moyen, prime moyenne.

| Colonne | Type | Définition |
|---|---|---|
| `annee` | BIGINT | Année civile (vide = toute la période selon la table). |
| `annee_precedente` | BIGINT | Année servant de base de comparaison. |
| `base` | VARCHAR | Période comparée : année complète ou janvier à juin. |
| `ratio_precedent` | DOUBLE | Ratio de l'année de comparaison. |
| `ratio` | DOUBLE | Ratio sinistres / primes. |
| `variation_pts` | DOUBLE | Variation du ratio, en points. |
| `effet_frequence_pts` | DOUBLE | Points de ratio dus à la fréquence. |
| `effet_cout_pts` | DOUBLE | Points de ratio dus au coût moyen. |
| `effet_prime_pts` | DOUBLE | Points de ratio dus à la prime moyenne. |
| `frequence` | DOUBLE | Sinistres retenus ÷ années-police. |
| `frequence_precedente` | DOUBLE | Fréquence de l'année de comparaison. |
| `cout_moyen` | DOUBLE | Charge ÷ sinistres retenus, en euros. |
| `cout_moyen_precedent` | DOUBLE | Coût moyen de l'année de comparaison. |
| `prime_moyenne` | DOUBLE | Primes acquises ÷ années-police. |
| `prime_moyenne_precedente` | DOUBLE | Prime moyenne de l'année de comparaison. |
| `exposition` | DOUBLE | Années-police : jours couverts ÷ 365,25. |
| `exposition_precedente` | DOUBLE | Années-police de l'année de comparaison. |
| `annee_incomplete` | BOOLEAN | Vrai si l'année n'est observée que partiellement (2025 : six mois). |
| `precedente_en_montee` | BOOLEAN | Vrai si l'année de comparaison est 2020, année de montée en charge. |

### `mart.decomposition_resultat`

Variation du résultat technique en euros : effet volume et effet résultat unitaire.

| Colonne | Type | Définition |
|---|---|---|
| `annee` | BIGINT | Année civile (vide = toute la période selon la table). |
| `base` | VARCHAR | Période comparée : année complète ou janvier à juin. |
| `resultat_precedent` | DOUBLE | Résultat de l'année de comparaison. |
| `resultat` | DOUBLE | Primes acquises − charge, en euros. |
| `effet_volume` | DOUBLE | Variation du résultat due au volume (années-police), en euros. |
| `effet_resultat_unitaire` | DOUBLE | Variation du résultat due au résultat par année-police, en euros. |

### `mart.decomposition_segments`

Contribution de chaque segment à la variation du ratio.

| Colonne | Type | Définition |
|---|---|---|
| `annee` | BIGINT | Année civile (vide = toute la période selon la table). |
| `base` | VARCHAR | Période comparée : année complète ou janvier à juin. |
| `axe` | VARCHAR | Axe de découpage : produit, zone_risque, formule, canal, tranche_age, region ou global. |
| `modalite` | VARCHAR | Valeur de l'axe de découpage. |
| `contribution_pts` | DOUBLE | Points de ratio apportés par le segment à la variation annuelle. |
| `ratio_segment` | DOUBLE | Ratio du segment l'année analysée. |
| `ratio_segment_precedent` | DOUBLE | Ratio du segment l'année précédente. |
| `poids_primes` | DOUBLE | Part du segment dans les primes de l'année. |
| `nb_sinistres` | DOUBLE | Sinistres retenus (ouverts ou clôturés). |

### `mart.delais_garantie`

Délais de déclaration, de premier règlement et de clôture, par garantie, avec quantiles.

| Colonne | Type | Définition |
|---|---|---|
| `delai` | VARCHAR | Type de délai : declaration, premier_reglement, cloture. |
| `garantie` | VARCHAR | Garantie sollicitée. |
| `n` | BIGINT | Nombre de dossiers servant au calcul. |
| `n_sans_valeur` | BIGINT | Dossiers sans valeur pour ce délai (pas de paiement, date incohérente). |
| `mediane` | DOUBLE | Valeur médiane. |
| `q75` | DOUBLE | Troisième quartile. |
| `q90` | DOUBLE | Neuvième décile. |
| `q95` | DOUBLE | 95e centile. |
| `maximum` | BIGINT | Valeur maximale. |
| `seuil_jours` | BIGINT | Seuil de délai retenu, en jours. |
| `part_dans_seuil` | DOUBLE | Part des dossiers traités dans le seuil de jours. |

### `mart.doublons_clients`

Mesure du taux de doublons clients.

| Colonne | Type | Définition |
|---|---|---|
| `clients_source` | BIGINT | Nombre de clients dans la source, avant fusion. |
| `personnes_distinctes` | BIGINT | Personnes distinctes après fusion. |
| `groupes_en_double` | BIGINT | Nombre de groupes de clients en double. |
| `ids_fusionnes` | BIGINT | Identifiants clients écartés au profit d'un autre. |
| `groupes_attributs_identiques` | BIGINT | Groupes de doublons dont date de naissance, région et CSP concordent. |
| `taux_doublons_pct` | DOUBLE | Identifiants fusionnés en pourcentage des clients de la source. |

### `mart.executions`

Historique des exécutions du pipeline, étape par étape.

| Colonne | Type | Définition |
|---|---|---|
| `lance_le` | TIMESTAMP | Horodatage du lancement. |
| `etape` | VARCHAR | Étape du pipeline. |
| `duree_s` | DOUBLE | Durée en secondes. |
| `statut` | VARCHAR | Statut du dossier (ouvert, cloture, rejete, sans_suite) ou statut d'exécution. |
| `message` | VARCHAR | Message d'erreur éventuel. |

### `mart.fraicheur`

Date de la donnée la plus récente et dernier chargement par source.

| Colonne | Type | Définition |
|---|---|---|
| `source` | VARCHAR | Source de données. |
| `derniere_date_donnee` | DATE | Date de la donnée la plus récente de la source. |
| `dernier_chargement` | TIMESTAMP | Date du dernier chargement de la source. |

### `mart.ic_indicateurs`

Intervalles de confiance à 95 % des indicateurs clés.

| Colonne | Type | Définition |
|---|---|---|
| `perimetre` | VARCHAR | Périmètre : tous, auto ou habitation. |
| `periode` | VARCHAR | Année ou 'toutes'. |
| `indicateur` | VARCHAR | Nom de l'indicateur. |
| `valeur` | DOUBLE | Primes acquises − sinistres payés, en euros. |
| `ic_bas` | DOUBLE | Borne basse de l'intervalle de confiance à 95 %. |
| `ic_haut` | DOUBLE | Borne haute de l'intervalle de confiance à 95 %. |
| `methode` | VARCHAR | Méthode de calcul de l'intervalle. |

### `mart.indicateurs_segments`

Indicateurs techniques par axe de découpage et par année (annee vide = toute la période).

| Colonne | Type | Définition |
|---|---|---|
| `axe` | VARCHAR | Axe de découpage : produit, zone_risque, formule, canal, tranche_age, region ou global. |
| `modalite` | VARCHAR | Valeur de l'axe de découpage. |
| `annee` | BIGINT | Année civile (vide = toute la période selon la table). |
| `exposition` | DOUBLE | Années-police : jours couverts ÷ 365,25. |
| `prime_acquise` | DOUBLE | Prime annuelle × exposition, en euros. |
| `nb_sinistres` | DOUBLE | Sinistres retenus (ouverts ou clôturés). |
| `nb_sans_suite` | DOUBLE | Sinistres au statut 'sans suite'. |
| `nb_rejetes` | DOUBLE | Sinistres au statut 'rejeté'. |
| `paye` | DOUBLE | Règlements payés, en euros. |
| `reserve` | DOUBLE | Reste à payer des dossiers ouverts, en euros. |
| `nb_resiliations` | DOUBLE | Contrats résiliés pendant la période. |
| `charge` | DOUBLE | Règlements payés + réserve restante des dossiers ouverts, en euros. |
| `frequence` | DOUBLE | Sinistres retenus ÷ années-police. |
| `frequence_declaree` | DOUBLE | Tous les sinistres déclarés ÷ années-police. |
| `cout_moyen` | DOUBLE | Charge ÷ sinistres retenus, en euros. |
| `prime_moyenne` | DOUBLE | Primes acquises ÷ années-police. |
| `ratio_paye` | DOUBLE | Règlements payés ÷ primes acquises. |
| `ratio_charge` | DOUBLE | Charge ÷ primes acquises. |
| `taux_resiliation` | DOUBLE | Résiliations ÷ années-police. |
| `frequence_ic_bas` | DOUBLE | Borne basse de l'intervalle de confiance de la fréquence (loi de Poisson). |
| `frequence_ic_haut` | DOUBLE | Borne haute de l'intervalle de confiance de la fréquence (loi de Poisson). |
| `annee_incomplete` | BOOLEAN | Vrai si l'année n'est observée que partiellement (2025 : six mois). |

### `mart.multidetention_part`

Part de clients détenant auto et habitation.

| Colonne | Type | Définition |
|---|---|---|
| `clients` | BIGINT | Nombre de clients. |
| `clients_multi` | BIGINT | Clients ayant auto et habitation. |
| `part_multi` | DOUBLE | Part des clients détenant auto et habitation. |
| `clients_auto_seul` | BIGINT | Clients ayant seulement de l'auto. |
| `clients_habitation_seul` | BIGINT | Clients ayant seulement de l'habitation. |

### `mart.multidetention_retention`

Rétention des multi-détenteurs et des mono-détenteurs selon deux définitions.

| Colonne | Type | Définition |
|---|---|---|
| `definition` | VARCHAR | Définition de la multi-détention utilisée. |
| `groupe` | VARCHAR | Groupe d'appartenance (rentabilité, multi/mono-détenteur). |
| `annee_k` | BIGINT | Nombre d'années écoulées depuis la souscription (anniversaire mesuré). |
| `nb_observables` | BIGINT | Contrats dont l'anniversaire est observable avant l'extraction. |
| `nb_survivants` | BIGINT | Contrats encore en vigueur à l'anniversaire. |
| `taux` | DOUBLE | Part de contrats restants. |
| `ic_bas` | DOUBLE | Borne basse de l'intervalle de confiance à 95 %. |
| `ic_haut` | DOUBLE | Borne haute de l'intervalle de confiance à 95 %. |

### `mart.pareto_valeur`

Courbe de concentration de la valeur positive, de 1 à 100 % des clients.

| Colonne | Type | Définition |
|---|---|---|
| `pct_clients` | BIGINT | Part des clients, classés du plus au moins rentable. |
| `part_valeur_positive` | DOUBLE | Part cumulée de la valeur positive. |

### `mart.portefeuille_mensuel`

Grain : mois × produit × région × canal × zone × formule × tranche d'âge. Source du dashboard.

| Colonne | Type | Définition |
|---|---|---|
| `mois` | DATE | Premier jour du mois. |
| `produit` | VARCHAR | auto ou habitation. |
| `region` | VARCHAR | Région du client. |
| `canal` | VARCHAR | Canal de distribution (agent, web, courtier). |
| `zone_risque` | VARCHAR | Zone de risque de 1 à 5. |
| `formule` | VARCHAR | Formule de garantie (essentielle, confort, premium). |
| `tranche_age` | VARCHAR | Tranche d'âge à la souscription. |
| `exposition` | DOUBLE | Années-police : jours couverts ÷ 365,25. |
| `prime_acquise` | DOUBLE | Prime annuelle × exposition, en euros. |
| `contrats_actifs` | INTEGER | Contrats en cours le dernier jour du mois. |
| `nb_sinistres` | INTEGER | Sinistres retenus (ouverts ou clôturés). |
| `nb_sans_suite` | INTEGER | Sinistres au statut 'sans suite'. |
| `nb_rejetes` | INTEGER | Sinistres au statut 'rejeté'. |
| `paye` | DOUBLE | Règlements payés, en euros. |
| `reserve` | DOUBLE | Reste à payer des dossiers ouverts, en euros. |
| `nb_resiliations` | INTEGER | Contrats résiliés pendant la période. |

### `mart.profils_valeur`

Profil moyen des clients les plus et les moins rentables.

| Colonne | Type | Définition |
|---|---|---|
| `groupe` | VARCHAR | Groupe d'appartenance (rentabilité, multi/mono-détenteur). |
| `nb_clients` | BIGINT | Nombre de clients. |
| `valeur_moyenne` | DOUBLE | Valeur moyenne par client. |
| `primes_moyennes` | DOUBLE | Primes acquises moyennes par client. |
| `paye_moyen` | DOUBLE | Sinistres payés moyens par client. |
| `nb_contrats_moyen` | DOUBLE | Nombre moyen de contrats par client. |
| `age_moyen` | DOUBLE | Âge moyen à l'extraction. |
| `part_multi` | DOUBLE | Part des clients détenant auto et habitation. |
| `part_auto` | DOUBLE | Part des clients détenant de l'auto. |
| `part_habitation` | DOUBLE | Part des clients détenant de l'habitation. |
| `part_avec_sinistre_paye` | DOUBLE | Part des clients ayant un sinistre payé. |

### `mart.profils_valeur_csp`

Répartition par CSP dans chaque groupe de rentabilité.

| Colonne | Type | Définition |
|---|---|---|
| `groupe` | VARCHAR | Groupe d'appartenance (rentabilité, multi/mono-détenteur). |
| `csp` | VARCHAR | Catégorie socioprofessionnelle. |
| `nb` | BIGINT | Nombre de sinistres. |
| `part` | DOUBLE | Part du groupe. |

### `mart.qualite_regles`

Règles de qualité avec le nombre de lignes concernées.

| Colonne | Type | Définition |
|---|---|---|
| `regle` | VARCHAR | Identifiant de la règle de qualité. |
| `source` | VARCHAR | Source de données. |
| `famille` | VARCHAR | Famille de règle : complétude, unicité, validité, cohérence entre tables ou temporelle. |
| `gravite` | VARCHAR | Gravité : critique, majeure, moyenne, mineure. |
| `traitement` | VARCHAR | Traitement : exclure, corriger ou signaler. |
| `libelle` | VARCHAR | Description de la règle. |
| `volume` | BIGINT | Lignes concernées. |
| `lignes_source` | BIGINT | Nombre de lignes de la source contrôlée. |
| `part_pct` | DOUBLE | Lignes concernées en pourcentage de la source. |

### `mart.queue_couts`

Quantiles du coût des sinistres et poids des sinistres les plus chers.

| Colonne | Type | Définition |
|---|---|---|
| `perimetre` | VARCHAR | Périmètre : tous, auto ou habitation. |
| `indicateur` | VARCHAR | Nom de l'indicateur. |
| `valeur` | DOUBLE | Primes acquises − sinistres payés, en euros. |

### `mart.ratio_plafonne`

Ratio annuel observé et ratio avec sinistres plafonnés au 99e centile.

| Colonne | Type | Définition |
|---|---|---|
| `annee` | BIGINT | Année civile (vide = toute la période selon la table). |
| `charge` | DOUBLE | Règlements payés + réserve restante des dossiers ouverts, en euros. |
| `plafonne` | DOUBLE | Charge avec chaque sinistre ramené au plafond. |
| `nb_sinistres` | BIGINT | Sinistres retenus (ouverts ou clôturés). |
| `nb_au_dessus` | BIGINT | Sinistres plus coûteux que le plafond. |
| `primes` | DOUBLE | Primes acquises, en euros. |
| `ratio_charge` | DOUBLE | Charge ÷ primes acquises. |
| `ratio_plafonne` | DOUBLE | Ratio avec sinistres plafonnés. |
| `seuil_plafond` | DOUBLE | Montant du plafond (99e centile du coût des sinistres). |

### `mart.ratio_plafonne_segments`

Même calcul par segment, toute la période.

| Colonne | Type | Définition |
|---|---|---|
| `modalite` | VARCHAR | Valeur de l'axe de découpage. |
| `charge` | DOUBLE | Règlements payés + réserve restante des dossiers ouverts, en euros. |
| `plafonne` | DOUBLE | Charge avec chaque sinistre ramené au plafond. |
| `nb_sinistres` | BIGINT | Sinistres retenus (ouverts ou clôturés). |
| `nb_au_dessus` | BIGINT | Sinistres plus coûteux que le plafond. |
| `axe` | VARCHAR | Axe de découpage : produit, zone_risque, formule, canal, tranche_age, region ou global. |
| `primes` | DOUBLE | Primes acquises, en euros. |
| `ratio_charge` | DOUBLE | Charge ÷ primes acquises. |
| `ratio_plafonne` | DOUBLE | Ratio avec sinistres plafonnés. |

### `mart.resultats_tests`

Résultat de chaque test au dernier lancement.

| Colonne | Type | Définition |
|---|---|---|
| `nom` | VARCHAR | Nom du test. |
| `description` | VARCHAR | Ce que vérifie le test. |
| `attendu` | DOUBLE | Valeur attendue par le test. |
| `obtenu` | DOUBLE | Écart constaté par le test (0 attendu). |
| `statut` | VARCHAR | Statut du dossier (ouvert, cloture, rejete, sans_suite) ou statut d'exécution. |
| `execute_le` | TIMESTAMP | Horodatage de l'exécution. |

### `mart.retention_cohortes`

Rétention par cohorte annuelle de souscription, par produit et par anniversaire.

| Colonne | Type | Définition |
|---|---|---|
| `cohorte` | BIGINT | Année de souscription du contrat. |
| `produit` | VARCHAR | auto ou habitation. |
| `annee_k` | BIGINT | Nombre d'années écoulées depuis la souscription (anniversaire mesuré). |
| `nb_contrats` | BIGINT | Nombre de contrats. |
| `nb_observables` | BIGINT | Contrats dont l'anniversaire est observable avant l'extraction. |
| `nb_survivants` | BIGINT | Contrats encore en vigueur à l'anniversaire. |
| `taux` | DOUBLE | Part de contrats restants. |
| `complet` | BOOLEAN | Vrai si tous les contrats de la cohorte ont atteint l'anniversaire avant l'extraction. |

### `mart.tests_stats`

Deux comparaisons testées statistiquement.

| Colonne | Type | Définition |
|---|---|---|
| `test` | VARCHAR | Nom du test statistique. |
| `groupe_a` | VARCHAR | Premier groupe comparé. |
| `groupe_b` | VARCHAR | Second groupe comparé. |
| `valeur_a` | DOUBLE | Indicateur du groupe A. |
| `valeur_b` | DOUBLE | Indicateur du groupe B. |
| `nb_a` | BIGINT | Effectif du groupe A. |
| `nb_b` | BIGINT | Effectif du groupe B. |
| `p_valeur` | DOUBLE | Probabilité critique du test. |
| `conclusion` | VARCHAR | Lecture du test au seuil de 5 %. |

### `mart.valeur_client`

Un client par ligne : primes acquises, sinistres payés, valeur et groupe de rentabilité.

| Colonne | Type | Définition |
|---|---|---|
| `client_id` | VARCHAR | Identifiant client conservé. |
| `region` | VARCHAR | Région du client. |
| `csp` | VARCHAR | Catégorie socioprofessionnelle. |
| `nb_contrats` | BIGINT | Nombre de contrats. |
| `nb_produits` | BIGINT | Nombre de produits différents détenus. |
| `a_auto` | BOOLEAN | Le client détient au moins un contrat auto (booléen). |
| `a_hab` | BOOLEAN | Le client détient au moins un contrat habitation (booléen). |
| `primes` | DOUBLE | Primes acquises, en euros. |
| `paye` | DOUBLE | Règlements payés, en euros. |
| `valeur` | DOUBLE | Primes acquises − sinistres payés, en euros. |
| `rang_pct` | DOUBLE | Rang du client en proportion, du plus au moins rentable. |
| `groupe` | VARCHAR | Groupe d'appartenance (rentabilité, multi/mono-détenteur). |
| `age` | DOUBLE | Âge à la date d'extraction, en années. |
| `multi` | BOOLEAN | Le client détient auto et habitation (booléen). |
