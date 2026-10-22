# Analyse RGPD de l'entrepôt

## Données personnelles présentes

| Donnée | Table | Nature |
|---|---|---|
| `client_id`, `contrat_id`, `sinistre_id` | toutes | identifiants pseudonymes : renvoient à une personne dans le système d'origine |
| `email_hash` | `brut.clients`, `coeur.dim_client` | e-mail haché. Une même adresse donne toujours la même empreinte : les fiches restent rapprochables, c'est donc une donnée pseudonymisée et non anonyme |
| `date_naissance` | `brut.clients`, `coeur.dim_client` | quasi-identifiant, qui devient très identifiant combiné à la région et à la CSP |
| `region`, `csp` | idem | quasi-identifiants |
| `consentement` | idem | donnée de gestion du consentement marketing |
| contrats, sinistres, règlements, audits | `coeur.*` | données rattachées à une personne par `client_id` ; un audit de fraude est une donnée sensible au sens courant, même si ce n'est pas une catégorie particulière du RGPD |

Aucun nom ni aucune coordonnée n'est présent dans l'archive.

## Présence par couche

| Couche | Données personnelles | Remarque |
|---|---|---|
| `brut` | toutes, copie fidèle | à accès restreint |
| `prep` | toutes, typées | tables intermédiaires reconstruites à chaque lancement |
| `quarantaine` | lignes rejetées, avec leurs données | doivent être purgées comme le reste |
| `coeur` | toutes sauf les lignes rejetées | `dim_client` porte les attributs directs |
| `mart` | `valeur_client` : `client_id`, région, CSP, âge | le dashboard ne lit pas cette table ligne à ligne, seulement des agrégats (courbe de concentration, profils) |
| Dashboard | agrégats uniquement | aucun client identifiable à l'écran |

## Pseudonymisation et minimisation

- Déjà en place : identifiants numériques, e-mail haché, aucun nom.
- À faire : n'exposer à l'équipe d'analyse que `mart` ; limiter l'accès à `brut`, `prep` et `quarantaine` ; remplacer `date_naissance` par une tranche d'âge dans les couches d'analyse (déjà le cas pour `tranche_age` ; `mart.valeur_client` garde l'âge, à arrondir si besoin) ; conserver `email_hash` uniquement le temps de la déduplication, avec un secret de hachage géré hors de l'entrepôt.

## Durée de conservation (propositions à valider avec le délégué à la protection des données)

| Donnée | Durée proposée | Raison |
|---|---|---|
| Contrats et sinistres | durée du contrat, puis une durée liée aux délais de prescription | besoin de gestion et d'obligation légale |
| Données marketing (`consentement`) | durée de la relation, puis effacement ou anonymisation | finalité marketing |
| Couche `brut` | durée de réconciliation avec les sources (par exemple 13 mois) | la source reste la référence |
| Quarantaine | jusqu'à correction à la source, puis purge | finalité de contrôle qualité |
| Marts agrégés | sans limite si anonymes | pas de personne identifiable |

## Droit à l'effacement, couche par couche

1. **Source d'abord** : effacer ou anonymiser dans les fichiers d'origine, sinon le prochain chargement réintroduit la personne.
2. **`brut`** : supprimer les lignes de `brut.clients` et `brut.contrats` du client, puis celles de `brut.sinistres`, `brut.reglements` et `brut.audits` liées à ses contrats. C'est la seule couche où l'on modifie des lignes, sur demande légale.
3. **`quarantaine`** : mêmes suppressions.
4. **`prep`, `coeur`, `mart`** : relancer `lancer.py` après la purge du brut ; ces couches se reconstruisent. Pour `coeur`, supprimer aussi les lignes des dimensions et faits qui ne se reconstruisent pas (insertion seulement) : `dim_client`, `dim_contrat`, `fact_*`.
5. **Sauvegardes** : prévoir leur durée de rétention.
6. **Exception** : une obligation légale de conservation (contrat, sinistre en cours) peut limiter l'effacement ; on anonymise alors les attributs directs (`email_hash`, `date_naissance`, `region`, `csp`) tout en gardant les montants pour la comptabilité.

```sql
-- exemple pour un client donné (à exécuter après vérification de l'identité et de l'absence d'obligation de conservation)
DELETE FROM brut.reglements WHERE sinistre_id IN (SELECT sinistre_id FROM brut.sinistres WHERE contrat_id IN (SELECT contrat_id FROM brut.contrats WHERE client_id = '123'));
DELETE FROM brut.sinistres WHERE contrat_id IN (SELECT contrat_id FROM brut.contrats WHERE client_id = '123');
DELETE FROM brut.contrats WHERE client_id = '123';
DELETE FROM brut.clients WHERE client_id = '123';
```
