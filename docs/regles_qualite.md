# Règles de qualité

24 règles contrôlées ; 10 détectent au moins une ligne. Traitement : **exclure** = la ligne va en quarantaine avec son motif ; **corriger** = la valeur est mise à vide ou ramenée à une valeur sûre, la ligne reste ; **signaler** = la ligne reste telle quelle, l'anomalie est comptée.

| Règle | Source | Famille | Gravité | Traitement | Constat | Lignes | % de la source |
|---|---|---|---|---|---|---|---|
| A01 | audits | cohérence entre tables | majeure | exclure | sinistre audité absent ou écarté | 0 | 0,0 |
| A02 | audits | unicité | majeure | exclure | résultat d'audit illisible, ou plusieurs audits pour un sinistre (on garde le plus récent) | 0 | 0,0 |
| A03 | audits | cohérence temporelle | mineure | signaler | audit avant la déclaration du sinistre | 0 | 0,0 |
| C01 | clients | unicité | critique | exclure | identifiant client absent ou en double (on garde la première ligne) | 0 | 0,0 |
| C02 | clients | complétude | mineure | signaler | date de naissance absente | 226 | 1,49 |
| C03 | clients | validité | mineure | corriger | date de naissance illisible ou hors de 18-100 ans, ou consentement illisible (valeur mise à vide) | 40 | 0,26 |
| C04 | clients | cohérence entre tables | moyenne | signaler | client sans aucun contrat valide (souvent le doublon d'un autre client) | 228 | 1,5 |
| K01 | contrats | unicité | critique | exclure | identifiant contrat absent ou en double (on garde la première ligne) | 0 | 0,0 |
| K02 | contrats | validité | critique | exclure | produit inconnu, ou date d'effet absente, illisible ou après la date d'extraction | 0 | 0,0 |
| K03 | contrats | cohérence temporelle | majeure | exclure | résiliation avant ou le jour de l'effet | 26 | 0,13 |
| K04 | contrats | validité | critique | exclure | prime absente ou négative ou nulle | 25 | 0,12 |
| K05 | contrats | validité | moyenne | corriger | résiliation après la date d'extraction (contrat considéré actif), ou bonus-malus hors de 0,5-3,5 (mis à vide) | 0 | 0,0 |
| K06 | contrats | cohérence entre tables | moyenne | signaler | client absent du CRM (rattaché au client INCONNU), ou puissance, surface, zone, formule ou canal absent | 0 | 0,0 |
| R01 | reglements | unicité | majeure | exclure | identifiant paiement absent, ou paiement déjà reçu dans un autre fichier ou une autre ligne (on garde le premier) | 32 | 1,0 |
| R02 | reglements | unicité | majeure | signaler | même paiement avec des montants différents | 0 | 0,0 |
| R03 | reglements | validité | critique | exclure | date de paiement illisible ou après la date d'extraction, ou montant absent, non numérique ou négatif ou nul | 0 | 0,0 |
| R04 | reglements | cohérence entre tables | critique | exclure | sinistre absent ou écarté (paiement orphelin) | 1 | 0,03 |
| R05 | reglements | cohérence entre tables | moyenne | signaler | paiement avant la survenance du sinistre, ou sur un sinistre rejeté ou sans suite | 0 | 0,0 |
| S01 | sinistres | unicité | critique | exclure | identifiant sinistre absent ou en double (on garde la première ligne) | 0 | 0,0 |
| S02 | sinistres | validité | critique | exclure | date de survenance ou de déclaration illisible ou après la date d'extraction | 0 | 0,0 |
| S03 | sinistres | cohérence entre tables | critique | exclure | contrat absent ou écarté (sinistre orphelin) | 5 | 0,18 |
| S04 | sinistres | cohérence temporelle | moyenne | signaler | déclaration avant la survenance (délai exclu des calculs) | 15 | 0,53 |
| S05 | sinistres | cohérence temporelle | moyenne | signaler | survenance en dehors de la période de couverture du contrat | 17 | 0,61 |
| S06 | sinistres | validité | moyenne | corriger | réserve absente ou négative (mise à vide, comptée 0), ou statut hors liste (classé 'inconnu') | 0 | 0,0 |

## Requêtes

Chaque requête renvoie les lignes concernées (`_ligne`) dans la table typée `prep.<source>_t`.

**A01** · sinistre audité absent ou écarté
```sql
SELECT _ligne FROM prep.audits_t WHERE sinistre_id IS NULL OR sinistre_id NOT IN (SELECT sinistre_id FROM prep.sinistres_ok)
```

**A02** · résultat d'audit illisible, ou plusieurs audits pour un sinistre (on garde le plus récent)
```sql
SELECT _ligne FROM (SELECT _ligne, fraude, row_number() OVER (PARTITION BY sinistre_id ORDER BY date_audit DESC NULLS LAST, _ligne DESC) AS rang FROM prep.audits_t WHERE sinistre_id IS NOT NULL) WHERE fraude IS NULL OR rang > 1
```

**A03** · audit avant la déclaration du sinistre
```sql
SELECT a._ligne FROM prep.audits_t a JOIN prep.sinistres_ok s USING (sinistre_id) WHERE a.date_audit < s.date_declaration
```

**C01** · identifiant client absent ou en double (on garde la première ligne)
```sql
SELECT _ligne FROM (SELECT _ligne, client_id, row_number() OVER (PARTITION BY client_id ORDER BY _fichier, _ligne) AS rang FROM prep.clients_t) WHERE client_id IS NULL OR rang > 1
```

**C02** · date de naissance absente
```sql
SELECT _ligne FROM prep.clients_t WHERE date_naissance_brute IS NULL
```

**C03** · date de naissance illisible ou hors de 18-100 ans, ou consentement illisible (valeur mise à vide)
```sql
SELECT _ligne FROM prep.clients_t WHERE (date_naissance_brute IS NOT NULL AND date_naissance IS NULL) OR (consentement_brut IS NOT NULL AND consentement IS NULL)
```

**C04** · client sans aucun contrat valide (souvent le doublon d'un autre client)
```sql
SELECT _ligne FROM prep.clients_t WHERE client_id NOT IN (SELECT client_id FROM prep.contrats_ok WHERE client_id IS NOT NULL)
```

**K01** · identifiant contrat absent ou en double (on garde la première ligne)
```sql
SELECT _ligne FROM (SELECT _ligne, contrat_id, row_number() OVER (PARTITION BY contrat_id ORDER BY _fichier, _ligne) AS rang FROM prep.contrats_t) WHERE contrat_id IS NULL OR rang > 1
```

**K02** · produit inconnu, ou date d'effet absente, illisible ou après la date d'extraction
```sql
SELECT _ligne FROM prep.contrats_t WHERE produit IS NULL OR produit NOT IN ('auto', 'habitation') OR date_effet IS NULL OR date_effet > DATE '2025-06-30'
```

**K03** · résiliation avant ou le jour de l'effet
```sql
SELECT _ligne FROM prep.contrats_t WHERE date_effet IS NOT NULL AND date_resiliation_lue <= date_effet
```

**K04** · prime absente ou négative ou nulle
```sql
SELECT _ligne FROM prep.contrats_t WHERE prime IS NULL OR prime <= 0
```

**K05** · résiliation après la date d'extraction (contrat considéré actif), ou bonus-malus hors de 0,5-3,5 (mis à vide)
```sql
SELECT _ligne FROM prep.contrats_t WHERE date_resiliation_lue > DATE '2025-06-30' OR (bonus_malus_lu IS NOT NULL AND bonus_malus IS NULL)
```

**K06** · client absent du CRM (rattaché au client INCONNU), ou puissance, surface, zone, formule ou canal absent
```sql
SELECT _ligne FROM prep.contrats_t WHERE client_id IS NULL OR client_id NOT IN (SELECT client_id FROM prep.clients_ok) OR (produit = 'auto' AND puissance IS NULL) OR (produit = 'habitation' AND surface IS NULL) OR zone_risque IS NULL OR formule IS NULL OR canal IS NULL
```

**R01** · identifiant paiement absent, ou paiement déjà reçu dans un autre fichier ou une autre ligne (on garde le premier)
```sql
SELECT _ligne FROM (SELECT _ligne, paiement_id, row_number() OVER (PARTITION BY paiement_id ORDER BY _fichier, _ligne) AS rang FROM prep.reglements_t) WHERE paiement_id IS NULL OR rang > 1
```

**R02** · même paiement avec des montants différents
```sql
SELECT _ligne FROM (SELECT _ligne, min(montant) OVER (PARTITION BY paiement_id) AS mini, max(montant) OVER (PARTITION BY paiement_id) AS maxi FROM prep.reglements_t WHERE paiement_id IS NOT NULL) WHERE mini <> maxi
```

**R03** · date de paiement illisible ou après la date d'extraction, ou montant absent, non numérique ou négatif ou nul
```sql
SELECT _ligne FROM prep.reglements_t WHERE date_paiement IS NULL OR date_paiement > DATE '2025-06-30' OR montant IS NULL OR montant <= 0
```

**R04** · sinistre absent ou écarté (paiement orphelin)
```sql
SELECT _ligne FROM prep.reglements_t WHERE sinistre_id IS NULL OR sinistre_id NOT IN (SELECT sinistre_id FROM prep.sinistres_ok)
```

**R05** · paiement avant la survenance du sinistre, ou sur un sinistre rejeté ou sans suite
```sql
SELECT r._ligne FROM prep.reglements_t r JOIN prep.sinistres_ok s USING (sinistre_id) WHERE r.date_paiement < s.date_survenance OR s.statut IN ('sans_suite', 'rejete')
```

**S01** · identifiant sinistre absent ou en double (on garde la première ligne)
```sql
SELECT _ligne FROM (SELECT _ligne, sinistre_id, row_number() OVER (PARTITION BY sinistre_id ORDER BY _fichier, _ligne) AS rang FROM prep.sinistres_t) WHERE sinistre_id IS NULL OR rang > 1
```

**S02** · date de survenance ou de déclaration illisible ou après la date d'extraction
```sql
SELECT _ligne FROM prep.sinistres_t WHERE date_survenance IS NULL OR date_declaration IS NULL OR date_survenance > DATE '2025-06-30' OR date_declaration > DATE '2025-06-30'
```

**S03** · contrat absent ou écarté (sinistre orphelin)
```sql
SELECT _ligne FROM prep.sinistres_t WHERE contrat_id IS NULL OR contrat_id NOT IN (SELECT contrat_id FROM prep.contrats_ok)
```

**S04** · déclaration avant la survenance (délai exclu des calculs)
```sql
SELECT _ligne FROM prep.sinistres_t WHERE date_declaration < date_survenance
```

**S05** · survenance en dehors de la période de couverture du contrat
```sql
SELECT s._ligne FROM prep.sinistres_t s JOIN prep.contrats_ok c USING (contrat_id) WHERE s.date_survenance < c.date_effet OR s.date_survenance >= coalesce(c.date_resiliation, DATE '2025-07-01')
```

**S06** · réserve absente ou négative (mise à vide, comptée 0), ou statut hors liste (classé 'inconnu')
```sql
SELECT _ligne FROM prep.sinistres_t WHERE reserve_initiale IS NULL OR statut = 'inconnu'
```
