# Règles de qualité

42 règles contrôlées ; 10 détectent au moins une ligne. Traitement : **exclure** = la ligne va en quarantaine avec son motif ; **corriger** = la valeur est mise à vide ou ramenée à une valeur sûre, la ligne reste ; **signaler** = la ligne reste telle quelle, l'anomalie est comptée.

| Règle | Source | Famille | Gravité | Traitement | Constat | Lignes | % de la source |
|---|---|---|---|---|---|---|---|
| A01 | audits | cohérence entre tables | majeure | exclure | sinistre audité absent ou écarté | 0 | 0,0 |
| A02 | audits | validité | majeure | exclure | résultat d'audit illisible | 0 | 0,0 |
| A03 | audits | unicité | moyenne | exclure | plusieurs audits pour un sinistre (on garde le plus récent) | 0 | 0,0 |
| A04 | audits | cohérence temporelle | mineure | signaler | audit avant la déclaration du sinistre | 0 | 0,0 |
| C01 | clients | complétude | critique | exclure | identifiant client absent | 0 | 0,0 |
| C02 | clients | unicité | majeure | exclure | identifiant client en double (on garde la première ligne) | 0 | 0,0 |
| C03 | clients | validité | mineure | corriger | date de naissance illisible (mise à vide) | 0 | 0,0 |
| C04 | clients | validité | mineure | corriger | âge hors de 18-100 ans à l'extraction (date mise à vide) | 40 | 0,26 |
| C05 | clients | complétude | mineure | signaler | date de naissance absente | 226 | 1,49 |
| C06 | clients | complétude | moyenne | signaler | empreinte e-mail absente (rapprochement impossible) | 0 | 0,0 |
| C07 | clients | validité | mineure | corriger | consentement illisible (mis à vide) | 0 | 0,0 |
| C08 | clients | cohérence entre tables | moyenne | signaler | client sans aucun contrat valide (souvent le doublon d'un autre client) | 228 | 1,5 |
| K01 | contrats | complétude | critique | exclure | identifiant contrat absent | 0 | 0,0 |
| K02 | contrats | unicité | majeure | exclure | identifiant contrat en double (on garde la première ligne) | 0 | 0,0 |
| K03 | contrats | validité | majeure | exclure | produit autre qu'auto ou habitation | 0 | 0,0 |
| K04 | contrats | validité | critique | exclure | date d'effet absente ou illisible | 0 | 0,0 |
| K05 | contrats | cohérence temporelle | majeure | exclure | date d'effet après la date d'extraction | 0 | 0,0 |
| K06 | contrats | cohérence temporelle | majeure | exclure | résiliation avant ou le jour de l'effet | 26 | 0,13 |
| K07 | contrats | cohérence temporelle | moyenne | corriger | résiliation après la date d'extraction (contrat considéré actif) | 0 | 0,0 |
| K08 | contrats | validité | critique | exclure | prime absente ou négative ou nulle | 25 | 0,12 |
| K09 | contrats | cohérence entre tables | majeure | signaler | client absent du CRM (rattaché au client INCONNU) | 0 | 0,0 |
| K10 | contrats | validité | mineure | corriger | bonus-malus hors de 0,5-3,5 (mis à vide) | 0 | 0,0 |
| K11 | contrats | complétude | mineure | signaler | puissance (auto) ou surface (habitation) absente | 0 | 0,0 |
| K12 | contrats | complétude | moyenne | signaler | zone, formule ou canal absent (rempli par 'inconnu') | 0 | 0,0 |
| R01 | reglements | complétude | critique | exclure | identifiant paiement absent | 0 | 0,0 |
| R02 | reglements | unicité | majeure | exclure | paiement déjà reçu dans un autre fichier ou une autre ligne (on garde le premier) | 32 | 1,0 |
| R03 | reglements | unicité | majeure | signaler | même paiement avec des montants différents | 0 | 0,0 |
| R04 | reglements | validité | critique | exclure | date de paiement illisible | 0 | 0,0 |
| R05 | reglements | validité | critique | exclure | montant absent, non numérique ou négatif ou nul | 0 | 0,0 |
| R06 | reglements | cohérence entre tables | critique | exclure | sinistre absent ou écarté (paiement orphelin) | 1 | 0,03 |
| R07 | reglements | cohérence temporelle | majeure | exclure | date de paiement après la date d'extraction | 0 | 0,0 |
| R08 | reglements | cohérence temporelle | moyenne | signaler | paiement avant la survenance du sinistre | 0 | 0,0 |
| R09 | reglements | cohérence entre tables | moyenne | signaler | paiement sur un sinistre rejeté ou sans suite | 0 | 0,0 |
| S01 | sinistres | complétude | critique | exclure | identifiant sinistre absent | 0 | 0,0 |
| S02 | sinistres | unicité | majeure | exclure | identifiant sinistre en double (on garde la première ligne) | 0 | 0,0 |
| S03 | sinistres | validité | critique | exclure | date de survenance ou de déclaration illisible | 0 | 0,0 |
| S04 | sinistres | cohérence temporelle | majeure | exclure | date après la date d'extraction | 0 | 0,0 |
| S05 | sinistres | cohérence entre tables | critique | exclure | contrat absent ou écarté (sinistre orphelin) | 5 | 0,18 |
| S06 | sinistres | cohérence temporelle | moyenne | signaler | déclaration avant la survenance (délai exclu des calculs) | 15 | 0,53 |
| S07 | sinistres | cohérence temporelle | moyenne | signaler | survenance en dehors de la période de couverture du contrat | 17 | 0,61 |
| S08 | sinistres | validité | moyenne | corriger | réserve absente ou négative (mise à vide, comptée 0) | 0 | 0,0 |
| S09 | sinistres | validité | mineure | signaler | statut hors liste (ouvert, cloture, rejete, sans_suite) | 0 | 0,0 |

## Requêtes

Chaque requête renvoie les lignes concernées (`_ligne`) dans la table typée `prep.<source>_t`.

**A01** · sinistre audité absent ou écarté
```sql
SELECT _ligne FROM prep.audits_t WHERE sinistre_id IS NULL OR sinistre_id NOT IN (SELECT sinistre_id FROM prep.sinistres_ok)
```

**A02** · résultat d'audit illisible
```sql
SELECT _ligne FROM prep.audits_t WHERE fraude IS NULL
```

**A03** · plusieurs audits pour un sinistre (on garde le plus récent)
```sql
SELECT _ligne FROM (SELECT _ligne, row_number() OVER (PARTITION BY sinistre_id ORDER BY date_audit DESC NULLS LAST, _ligne DESC) AS rang FROM prep.audits_t WHERE sinistre_id IS NOT NULL) WHERE rang > 1
```

**A04** · audit avant la déclaration du sinistre
```sql
SELECT a._ligne FROM prep.audits_t a JOIN prep.sinistres_ok s USING (sinistre_id) WHERE a.date_audit < s.date_declaration
```

**C01** · identifiant client absent
```sql
SELECT _ligne FROM prep.clients_t WHERE client_id IS NULL
```

**C02** · identifiant client en double (on garde la première ligne)
```sql
SELECT _ligne FROM (SELECT _ligne, row_number() OVER (PARTITION BY client_id ORDER BY _fichier, _ligne) AS rang FROM prep.clients_t WHERE client_id IS NOT NULL) WHERE rang > 1
```

**C03** · date de naissance illisible (mise à vide)
```sql
SELECT _ligne FROM prep.clients_t WHERE date_naissance_brute IS NOT NULL AND date_naissance_lue IS NULL
```

**C04** · âge hors de 18-100 ans à l'extraction (date mise à vide)
```sql
SELECT _ligne FROM prep.clients_t WHERE date_naissance_lue IS NOT NULL AND date_naissance IS NULL
```

**C05** · date de naissance absente
```sql
SELECT _ligne FROM prep.clients_t WHERE date_naissance_brute IS NULL
```

**C06** · empreinte e-mail absente (rapprochement impossible)
```sql
SELECT _ligne FROM prep.clients_t WHERE email_hash IS NULL
```

**C07** · consentement illisible (mis à vide)
```sql
SELECT _ligne FROM prep.clients_t WHERE consentement_brut IS NOT NULL AND consentement IS NULL
```

**C08** · client sans aucun contrat valide (souvent le doublon d'un autre client)
```sql
SELECT _ligne FROM prep.clients_t WHERE client_id NOT IN (SELECT client_id FROM prep.contrats_ok WHERE client_id IS NOT NULL)
```

**K01** · identifiant contrat absent
```sql
SELECT _ligne FROM prep.contrats_t WHERE contrat_id IS NULL
```

**K02** · identifiant contrat en double (on garde la première ligne)
```sql
SELECT _ligne FROM (SELECT _ligne, row_number() OVER (PARTITION BY contrat_id ORDER BY _fichier, _ligne) AS rang FROM prep.contrats_t WHERE contrat_id IS NOT NULL) WHERE rang > 1
```

**K03** · produit autre qu'auto ou habitation
```sql
SELECT _ligne FROM prep.contrats_t WHERE produit IS NULL OR produit NOT IN ('auto', 'habitation')
```

**K04** · date d'effet absente ou illisible
```sql
SELECT _ligne FROM prep.contrats_t WHERE date_effet IS NULL
```

**K05** · date d'effet après la date d'extraction
```sql
SELECT _ligne FROM prep.contrats_t WHERE date_effet > DATE '2025-06-30'
```

**K06** · résiliation avant ou le jour de l'effet
```sql
SELECT _ligne FROM prep.contrats_t WHERE date_effet IS NOT NULL AND date_resiliation_lue <= date_effet
```

**K07** · résiliation après la date d'extraction (contrat considéré actif)
```sql
SELECT _ligne FROM prep.contrats_t WHERE date_resiliation_lue > DATE '2025-06-30'
```

**K08** · prime absente ou négative ou nulle
```sql
SELECT _ligne FROM prep.contrats_t WHERE prime IS NULL OR prime <= 0
```

**K09** · client absent du CRM (rattaché au client INCONNU)
```sql
SELECT _ligne FROM prep.contrats_t WHERE client_id IS NULL OR client_id NOT IN (SELECT client_id FROM prep.clients_ok)
```

**K10** · bonus-malus hors de 0,5-3,5 (mis à vide)
```sql
SELECT _ligne FROM prep.contrats_t WHERE bonus_malus_lu IS NOT NULL AND bonus_malus IS NULL
```

**K11** · puissance (auto) ou surface (habitation) absente
```sql
SELECT _ligne FROM prep.contrats_t WHERE (produit = 'auto' AND puissance IS NULL) OR (produit = 'habitation' AND surface IS NULL)
```

**K12** · zone, formule ou canal absent (rempli par 'inconnu')
```sql
SELECT _ligne FROM prep.contrats_t WHERE zone_risque IS NULL OR formule IS NULL OR canal IS NULL
```

**R01** · identifiant paiement absent
```sql
SELECT _ligne FROM prep.reglements_t WHERE paiement_id IS NULL
```

**R02** · paiement déjà reçu dans un autre fichier ou une autre ligne (on garde le premier)
```sql
SELECT _ligne FROM (SELECT _ligne, row_number() OVER (PARTITION BY paiement_id ORDER BY _fichier, _ligne) AS rang FROM prep.reglements_t WHERE paiement_id IS NOT NULL) WHERE rang > 1
```

**R03** · même paiement avec des montants différents
```sql
SELECT _ligne FROM (SELECT _ligne, min(montant) OVER (PARTITION BY paiement_id) AS mini, max(montant) OVER (PARTITION BY paiement_id) AS maxi FROM prep.reglements_t WHERE paiement_id IS NOT NULL) WHERE mini <> maxi
```

**R04** · date de paiement illisible
```sql
SELECT _ligne FROM prep.reglements_t WHERE date_paiement IS NULL
```

**R05** · montant absent, non numérique ou négatif ou nul
```sql
SELECT _ligne FROM prep.reglements_t WHERE montant IS NULL OR montant <= 0
```

**R06** · sinistre absent ou écarté (paiement orphelin)
```sql
SELECT _ligne FROM prep.reglements_t WHERE sinistre_id IS NULL OR sinistre_id NOT IN (SELECT sinistre_id FROM prep.sinistres_ok)
```

**R07** · date de paiement après la date d'extraction
```sql
SELECT _ligne FROM prep.reglements_t WHERE date_paiement > DATE '2025-06-30'
```

**R08** · paiement avant la survenance du sinistre
```sql
SELECT r._ligne FROM prep.reglements_t r JOIN prep.sinistres_ok s USING (sinistre_id) WHERE r.date_paiement < s.date_survenance
```

**R09** · paiement sur un sinistre rejeté ou sans suite
```sql
SELECT r._ligne FROM prep.reglements_t r JOIN prep.sinistres_ok s USING (sinistre_id) WHERE s.statut IN ('sans_suite', 'rejete')
```

**S01** · identifiant sinistre absent
```sql
SELECT _ligne FROM prep.sinistres_t WHERE sinistre_id IS NULL
```

**S02** · identifiant sinistre en double (on garde la première ligne)
```sql
SELECT _ligne FROM (SELECT _ligne, row_number() OVER (PARTITION BY sinistre_id ORDER BY _fichier, _ligne) AS rang FROM prep.sinistres_t WHERE sinistre_id IS NOT NULL) WHERE rang > 1
```

**S03** · date de survenance ou de déclaration illisible
```sql
SELECT _ligne FROM prep.sinistres_t WHERE date_survenance IS NULL OR date_declaration IS NULL
```

**S04** · date après la date d'extraction
```sql
SELECT _ligne FROM prep.sinistres_t WHERE date_survenance > DATE '2025-06-30' OR date_declaration > DATE '2025-06-30'
```

**S05** · contrat absent ou écarté (sinistre orphelin)
```sql
SELECT _ligne FROM prep.sinistres_t WHERE contrat_id IS NULL OR contrat_id NOT IN (SELECT contrat_id FROM prep.contrats_ok)
```

**S06** · déclaration avant la survenance (délai exclu des calculs)
```sql
SELECT _ligne FROM prep.sinistres_t WHERE date_declaration < date_survenance
```

**S07** · survenance en dehors de la période de couverture du contrat
```sql
SELECT s._ligne FROM prep.sinistres_t s JOIN prep.contrats_ok c USING (contrat_id) WHERE s.date_survenance < c.date_effet OR s.date_survenance >= coalesce(c.date_resiliation, DATE '2025-07-01')
```

**S08** · réserve absente ou négative (mise à vide, comptée 0)
```sql
SELECT _ligne FROM prep.sinistres_t WHERE reserve_initiale IS NULL
```

**S09** · statut hors liste (ouvert, cloture, rejete, sans_suite)
```sql
SELECT _ligne FROM prep.sinistres_t WHERE statut = 'inconnu'
```
