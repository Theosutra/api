# Description du schéma de la base de données RH (QUICKMS)

## Vue d'ensemble

Cette base de données contient des informations sur les dépôts de déclarations sociales (DSN - Déclaration Sociale Nominative), les entreprises, les salariés, les rémunérations, et les absences. Elle est structurée autour de plusieurs tables principales reliées par des clés étrangères.

## ⚠️ Framework obligatoire pour chaque requête

### Éléments obligatoires

Chaque requête SQL générée DOIT respecter ce framework de sécurité :

1. **Filtre utilisateur obligatoire** : 
   - `WHERE [alias_depot].ID_USER = ?` 
   - Exemple : `WHERE a.ID_USER = ?` (si l'alias de DEPOT est 'a')
   - La table DEPOT doit TOUJOURS être présente pour permettre ce filtre

2. **Hashtags obligatoires** :
   - Placer les hashtags de traçabilité à la fin de la requête : `#DEPOT_[alias]# #FACTS_[alias]# #PERIODE#`
   - Les hashtags fonctionnels comme `#PERIODE#` et `#LANG#` sont utilisés dans la logique de la requête
   - Exemple : `WHERE a.periode IN (#PERIODE#)` pour le hashtag fonctionnel

## Conventions d'aliasing recommandées

- DEPOT → a
- FACTS → b
- FACTS_REM → fr
- FACTS_ABS_FINAL → fa
- ENTREPRISE → e
- SOCIETE → s
- REFERENTIEL → r, c, d (selon le contexte)
- REFERENTIEL_PERIODE → rp, d, w

## Tables principales

### 1. DEPOT

Table centrale qui contient les informations sur les dépôts de déclarations sociales.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique du dépôt (clé primaire) |
| NUMDEPOT | varchar(500) | Numéro du dépôt |
| ID_CLIENT | int | Identifiant du client |
| STATUS | varchar(50) | Statut du dépôt (valeurs possibles: 'VALIDE', ...) |
| ID_USER | int | Identifiant de l'utilisateur **[CLEF DE SÉCURITÉ]** |
| DATE_CREATION | datetime | Date de création du dépôt |
| DATE_MAJ | datetime | Date de mise à jour du dépôt |
| TYPE_FIC | varchar(50) | Type de fichier (DSN par défaut) |
| NATURE | varchar(50) | Nature du dépôt (DSN par défaut) |
| SIREN | varchar(50) | Numéro SIREN de l'entreprise |
| PERIODE | varchar(10) | Période de paie au format MMAAAA |
| NB_ETAB | int | Nombre d'établissements |
| NB_SAL | int | Nombre de salariés |
| DATEDEB | date | Date de début de validité |
| DATEFIN | date | Date de fin de validité |
| nic | varchar(50) | Numéro interne de classement (complément du SIREN) |
| SECTEUR | varchar(50) | Secteur d'activité |
| SOUSSECTEUR | varchar(100) | Sous-secteur d'activité |
| MASSE_SALARIALE | varchar(100) | Masse salariale |
| NB_HEURE | varchar(50) | Nombre d'heures |
| REGION | varchar(100) | Région géographique |
| DEPARTEMENT | varchar(100) | Département |

### 2. FACTS

Table principale des faits qui contient les informations sur les salariés et leurs contrats.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique (clé primaire) |
| IDUSER | int | Identifiant de l'utilisateur |
| ID_CLIENT | int | Identifiant du client (PERE de l'utilisateur) |
| siren | varchar(50) | Numéro SIREN de l'entreprise |
| nic | varchar(50) | Numéro interne de classement |
| ID_NUMDEPOT | int | Lien vers la table depot (depot.id) |
| DATEDEB_DEPOT | date | Date de début du dépôt |
| SUID | varchar(400) | Identifiant unique du salarié |
| DATE_FAIT | date | Date du premier jour d'applicabilité du contrat |
| SEXE | varchar(50) | Genre du salarié (M/F) |
| DATE_NAI | date | Date de naissance du salarié |
| AGE | decimal | Âge du salarié |
| MATRICULE | varchar(250) | Matricule du salarié dans l'entreprise |
| TEM_FP | int | Témoin Présent Fin de mois (1 = Salarié présent le dernier jour du mois) |
| TEM_EMB | int | Témoin Embauche sur le mois (1 = Salarié embauché sur le mois) |
| TEM_SOR | int | Témoin sortie sur le mois (1 = Salarié sorti sur le mois) |
| NOM | varchar(250) | Nom de famille du salarié |
| NOM_USAGE | varchar(250) | Nom d'usage du salarié |
| PRENOM | varchar(250) | Prénom du salarié |
| DEBUT_CONTRAT | varchar(50) | Date de début du contrat |
| NATURE_CONTRAT | varchar(50) | Nature du lien entre l'employeur et l'individu |
| MOTIF_RECOURS | varchar(50) | Motif de recours (pour CDD) |
| STATUT_CONVENTIONNEL | varchar(50) | Statut conventionnel du salarié |
| CATEGORIE | varchar(50) | Statut catégoriel Retraite complémentaire |
| MODALITE_TEMPS | varchar(50) | Modalité de temps de travail ('10' = temps plein) |
| QUOTITE_TRAVAIL | varchar(50) | Durée contractuelle de travail |
| QUOTITE_TRAVAIL_REF | varchar(50) | Durée de travail de référence |
| MNT_BRUT | varchar(50) | Montant brut |
| MNT_BRUT_ETP | varchar(50) | Montant brut équivalent temps plein |
| NET_FISCAL | varchar(50) | Net fiscal |
| NET_VERSE | varchar(50) | Net versé |
| MOTIF_DEPART | varchar(500) | Motif de rupture du contrat ('null' = pas de départ) |
| FIN_CONTRAT | varchar(20) | Date de fin du contrat ('null' = pas de fin) |
| MNT_SALBAS | varchar(50) | Montant du salaire de base |
| MNT_SALBAS_ETP | varchar(50) | Montant du salaire de base équivalent temps plein |
| CODE_POSTAL | varchar(50) | Code postal |
| LOCALITE | varchar(50) | Localité |
| EMPLOI | varchar(200) | Fonction du salarié dans l'entreprise |
| EMPLOI_CATEGORY | varchar(200) | Catégorie de l'emploi |
| EMPLOI_SUBCATEGORY | varchar(200) | Sous-catégorie de l'emploi |
| CODE_CONV_COLL | varchar(50) | Code convention collective (IDCC) |
| PCSESE | varchar(50) | Code PCS-ESE (Professions et Catégories Socioprofessionnelles) |
| STATUT_BOETH | varchar(50) | Statut de bénéficiaire de l'obligation d'emploi des travailleurs handicapés |
| ETP_CONTRAT | varchar(50) | Équivalent temps plein du contrat |
| ETP_CAL | varchar(50) | Équivalent temps plein calendaire |
| HEURE_TRAV | varchar(50) | Heures payées |
| HEURE_REAL | varchar(50) | Heures travaillées réelles |
| HEURE_SUPP | varchar(50) | Heures supplémentaires |
| HEURE_ABS | varchar(50) | Heures d'absence |
| NB_JOURS_CONTRAT | varchar(2) | Nombre de jours contractuels |
| NB_JOURS_ABS | varchar(2) | Nombre de jours d'absences |
| ANC_ENTREPRISE | varchar(10) | Ancienneté dans l'entreprise |
| DEPARTEMENT | varchar(100) | Département du salarié |
| SERVICE | varchar(100) | Service du salarié |
| DIVISION | varchar(100) | Division du salarié |
| MNT_PRIME | float | Montant de la prime perçue par le salarié |
| MNT_HEURE_SUPP | float | Montant des heures supplémentaires perçues |
| MNT_VARIABLE | float | Montant de la part variable perçue |
| TAUX_CHARGE_PATRON | float | Taux de charge patronale |
| SALAIRE_CHARGE | float | Correspond au brut * taux de charge patronale |

### 3. FACTS_REM

Table des rémunérations qui détaille les éléments de paie pour chaque salarié.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique (clé primaire) |
| ID_NUMDEPOT | int | Lien vers la table depot (depot.id) |
| ID_FACT | int | Lien vers la table facts (facts.id) |
| ID_FACT_VERS | int | Lien vers la table facts_versement |
| SUID | varchar(400) | Identifiant unique du salarié |
| DEB_PER_REM | varchar(50) | Début de la période de rémunération |
| FIN_PER_REM | varchar(50) | Fin de la période de rémunération |
| TYPE_REM | varchar(50) | Type de rémunération |
| MONTANT | varchar(50) | Montant de la rémunération |
| DECLA_MONTANT | varchar(50) | Montant déclaré (valeur d'origine) |
| MESURE_01 | varchar(50) | Mesure complémentaire 1 |
| UM_01 | varchar(50) | Unité de mesure 1 |
| MESURE_02 | varchar(50) | Mesure complémentaire 2 |
| UM_02 | varchar(50) | Unité de mesure 2 |
| NB_HEURE | varchar(50) | Nombre d'heures |
| NUMERO_CONTRAT | varchar(50) | Numéro du contrat |

### 4. FACTS_ABS_FINAL

Table des absences qui détaille les périodes d'absence pour chaque salarié.

| Colonne | Type | Description |
|---------|------|-------------|
| Id | int | Identifiant unique (clé primaire) |
| id_user | int | Identifiant de l'utilisateur |
| id_numdepot | int | Lien vers la table depot (depot.id) |
| id_fact | int | Lien vers la table facts (facts.id) |
| id_fact_abs_statut | int | Identifiant du statut d'absence |
| periode | varchar(10) | Période concernée |
| siren | varchar(50) | Numéro SIREN de l'entreprise |
| nic | varchar(5) | Numéro interne de classement |
| matricule | varchar(250) | Matricule du salarié |
| suid | varchar(400) | Identifiant unique du salarié |
| MOTIF_ARRET | varchar(50) | Motif de l'arrêt |
| DEBUT_ARRET | date | Dernier jour travaillé |
| DEBUT_REEL | date | Premier jour d'absence |
| fin_arret | date | Fin d'absence prévisionnelle |
| DATE_REPRISE | date | Premier jour de reprise après absence |
| motif_reprise | varchar(50) | Motif de reprise |
| debabs | date | Premier jour d'absence dans le mois |
| finabs | date | Dernier jour d'absence dans le mois |
| dure | float | Jours d'absence par mois |
| dure_total | float | Total des jours d'absence depuis le début |

### 5. FACTS_ANC

Table des anciennetés des salariés.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique (clé primaire) |
| ID_FACT | int | Lien vers la table facts (facts.id) |
| VAL_ANC | decimal | Valeur d'ancienneté |
| UM_ANC | varchar(50) | Unité de mesure de l'ancienneté |

### 6. REFERENTIEL

Table de référence pour les codes et libellés utilisés dans la DSN.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique (clé primaire) |
| RUBRIQUE_DSN | varchar(50) | Rubrique DSN concernée (ex: 'S21.G00.40.007', 'S21.G00.30.005') |
| CODE | varchar(255) | Code |
| LIBELLE | varchar(1000) | Libellé correspondant au code |
| LANG | varchar(2) | Langue du libellé (FR par défaut) |
| LINK_DATA | varchar(500) | Colonne de référence dans la base de données |
| LABEL | json | Labels multilingues en format JSON |

### 7. REFERENTIEL_PERIODE

Table de référence pour les périodes.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique (clé primaire) |
| ID_USER | int | Identifiant de l'utilisateur |
| PERIODE | varchar(50) | Période au format MMAAAA |
| DATEDEB | date | Date de début de la période |

### 8. CONTRAT_CATEGORIE

Table de catégorisation des contrats.

| Colonne | Type | Description |
|---------|------|-------------|
| CODE | varchar(50) | Code du contrat |
| CATEGORIE | varchar(50) | Catégorie du contrat ('CDI', 'CDD', etc.) |

## Relations principales

1. `depot.ID` → `facts.ID_NUMDEPOT` : Un dépôt contient plusieurs facts (salariés)
2. `facts.ID` → `facts_rem.ID_FACT` : Un salarié peut avoir plusieurs éléments de rémunération
3. `facts.ID` → `facts_abs_final.id_fact` : Un salarié peut avoir plusieurs absences
4. `facts.ID` → `facts_anc.ID_FACT` : Un salarié a des informations d'ancienneté
5. `depot.siren` + `depot.nic` = `entreprise.SIRET` : Lien entre dépôt et entreprise

## Fonctions et opérateurs SQL spécifiques

Ces fonctions sont fréquemment utilisées dans les requêtes:

- `IFNone(value, default)` : Renvoie `default` si `value` est NULL
- `JSON_VALUE(json_col, '$.lang')` : Extrait une valeur spécifique d'un champ JSON
- `STRAIGHT_JOIN` : Indicateur d'optimisation de requête
- `CONCAT(...)` : Concaténation de chaînes
- `SUBSTRING(str, pos, len)` : Extrait une sous-chaîne
- `DATE_FORMAT(date, format)` : Formate une date (ex: '%Y%m', '%d%m%Y')
- `ROUND(value, precision)` : Arrondit une valeur numérique
- `TRUNCATE(value, precision)` : Tronque une valeur numérique
- `FIRST_VALUE(...) OVER (PARTITION BY ... ORDER BY ...)` : Fonction de fenêtrage

## Modèles de requêtes par cas d'usage

### 1. Sélection de la période la plus récente

```sql
SELECT a.*, b.*
FROM depot a
INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT
WHERE a.ID_USER = ?
AND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (
    SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))
    FROM depot w
    WHERE w.periode IN (#PERIODE#)
    AND w.id_user = a.id_user
)
#DEPOT_a# #FACTS_b# #PERIODE#;
```

### 2. Effectifs inscrits (sous contrat) à une date précise

```sql
SELECT b.STATUT_CONVENTIONNEL, 
       c.LIBELLE, 
       b.SEXE, 
       COUNT(*) 
FROM depot a 
INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT 
LEFT OUTER JOIN referentiel c ON c.RUBRIQUE_DSN = 'S21.G00.40.002' AND c.CODE = b.STATUT_CONVENTIONNEL 
WHERE a.ID_USER = ? 
AND (b.FIN_CONTRAT = 'null' OR b.FIN_CONTRAT > a.datefin)
AND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (
    SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))
    FROM depot w
    WHERE w.periode IN (#PERIODE#)
    AND w.id_user = a.id_user
)
GROUP BY 1, 2, 3
ORDER BY 1, 2;
#DEPOT_a# #FACTS_b# #PERIODE#
```

### 3. Analyse d'ETP (Équivalent Temps Plein)

```sql
SELECT b.STATUT_CONVENTIONNEL,
       c.LIBELLE,
       b.SEXE,
       ROUND(SUM(b.etp_contrat), 2) 
FROM depot a 
INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT 
LEFT OUTER JOIN referentiel c ON c.RUBRIQUE_DSN = 'S21.G00.40.002' AND c.CODE = b.STATUT_CONVENTIONNEL 
WHERE a.ID_USER = ? 
AND (b.FIN_CONTRAT >= a.dateFIN) 
AND b.motif_recours NOT IN ('01', '12')
AND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (
    SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))
    FROM depot w
    WHERE w.periode IN (#PERIODE#)
    AND w.id_user = a.id_user
)
GROUP BY 1, 2, 3
ORDER BY 1, 2;
#DEPOT_a# #FACTS_b# #PERIODE#
```

### 4. Pyramide des âges

```sql
SELECT STRAIGHT_JOIN
  b.SEXE,
  TRUNCATE(b.age, 0),
  COUNT(*)
FROM depot a
INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT
WHERE a.ID_USER = ?
AND b.motif_depart IN ('null')
AND a.PERIODE IN (
    SELECT DATE_FORMAT(MAX(r.DATEDEB), '%d%m%Y')
    FROM referentiel_periode r
    WHERE r.ID_USER = a.ID_USER
    AND r.PERIODE IN (#PERIODE#)
)
GROUP BY 1, 2
ORDER BY 1, 2;
#DEPOT_a# #FACTS_b# #PERIODE#
```

### 5. Ancienneté moyenne

```sql
SELECT b.STATUT_CONVENTIONNEL, c.LIBELLE,
       ROUND(AVG(TRUNCATE(d.val_anc / IFNULL(f.libelle, 365.25), 0)), 2)
FROM depot a 
INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT 
INNER JOIN facts_anc d ON b.id = d.id_FACT
LEFT OUTER JOIN referentiel c ON c.RUBRIQUE_DSN = 'S21.G00.40.002' AND c.CODE = b.STATUT_CONVENTIONNEL 
LEFT OUTER JOIN referentiel f ON f.rubrique_DSN = 'MESUREANCIENNETE' AND ABS(d.UM_ANC) = ABS(f.code)
WHERE a.ID_USER = ?
AND (b.fin_contrat = 'null' OR b.fin_contrat > a.datefin)
AND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (
    SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))
    FROM depot w
    WHERE w.periode IN (#PERIODE#)
    AND w.id_user = a.id_user
)
GROUP BY 1, 2
ORDER BY 1, 2;
#DEPOT_a# #FACTS_b# #PERIODE#
```

### 6. Analyse des embauches

```sql
SELECT 
    b.NATURE_CONTRAT,
    IFNone(JSON_VALUE(c.LABEL, CONCAT('$.', '#LANG#')), c.LIBELLE),
    COUNT(DISTINCT(CONCAT(a.siren, a.nic, b.matricule, b.DEBUT_CONTRAT))) 
FROM depot a 
INNER JOIN facts b ON a.id = b.id_numdepot AND b.motif_recours NOT IN ('9000', '9001')
LEFT OUTER JOIN referentiel c ON c.RUBRIQUE_DSN = 'S21.G00.40.007' AND c.CODE = b.NATURE_CONTRAT 
INNER JOIN referentiel d ON d.RUBRIQUE_DSN = 'S21.G00.40.002' AND d.CODE = b.STATUT_CONVENTIONNEL 
WHERE a.ID_USER = ? 
AND b.debut_contrat >= a.datedeb 
AND b.debut_contrat <= a.datefin 
GROUP BY 1, 2
ORDER BY 1, 2;
#DEPOT_a# #FACTS_b#
```

### 7. Requête utilisant des fonctions de fenêtrage

```sql
SELECT
  T.LAST_STATUT_CONVENTIONNEL, 
  c.LIBELLE, 
  ROUND(SUM(LAST_etp_contrat), 2) 
FROM (
  SELECT STRAIGHT_JOIN DISTINCT
    a.SIREN,
    a.nic,
    b.MATRICULE,
    SUM(b.ETP_CAL) OVER (PARTITION BY a.siren, a.nic, b.MATRICULE) AS SUM_ETP_CAL,
    FIRST_VALUE(b.STATUT_CONVENTIONNEL) OVER (PARTITION BY a.siren, a.nic, b.MATRICULE ORDER BY a.DATEDEB DESC) AS LAST_STATUT_CONVENTIONNEL,
    FIRST_VALUE(b.etp_contrat) OVER (PARTITION BY a.siren, a.nic, b.MATRICULE ORDER BY a.DATEDEB DESC) AS LAST_etp_contrat
  FROM depot a
  INNER JOIN facts b ON a.id = b.id_numdepot
  WHERE a.id_user = ? 
  AND b.nature_contrat = '01' 
  AND b.MODALITE_TEMPS = '10'
  AND (b.FIN_CONTRAT >= a.datedeb)
  AND a.STATUS = 'VALIDE' 
) AS T
LEFT JOIN referentiel c ON c.RUBRIQUE_DSN = 'S21.G00.40.002' AND c.CODE = T.LAST_STATUT_CONVENTIONNEL
WHERE T.SUM_ETP_CAL >= (
  SELECT COUNT(DISTINCT w.PERIODE)
  FROM referentiel_periode w
  WHERE w.id_user = ?
  AND w.periode IN (#PERIODE#)
)
GROUP BY 1, 2;
#DEPOT_a# #FACTS_b# #PERIODE#
```

## Filtres temporels courants

### Filtres par période

```sql
-- Dernière période sélectionnée
AND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (
    SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))
    FROM depot w
    WHERE w.periode IN (#PERIODE#)
    AND w.id_user = a.id_user
)

-- Toutes les périodes sélectionnées
AND a.periode IN (#PERIODE#)
```

### Filtres par date de début/fin de contrat

```sql
-- Contrats actifs à la fin de période
AND (b.FIN_CONTRAT = 'null' OR b.FIN_CONTRAT > a.datefin)

-- Embauches sur la période
AND b.debut_contrat >= a.datedeb 
AND b.debut_contrat <= a.datefin
```

### Filtres par statut

```sql
-- Filtre sur les contrats (CDI)
AND b.nature_contrat = '01'

-- Filtre sur les contrats (CDD et autres temporaires)
AND b.NATURE_CONTRAT NOT IN ('01', '07', '08', '09')

-- Filtre sur les motifs de recours (sauf remplacement)
AND b.motif_recours NOT IN ('01', '12')

-- Filtre sur les contrats actifs (sans départ)
AND b.motif_depart IN ('null')

-- Filtre sur les temps pleins
AND b.MODALITE_TEMPS = '10'
```

## Agrégations et calculs courants

```sql
-- Comptage des salariés
COUNT(*)
COUNT(DISTINCT(CONCAT(a.siren, a.nic, b.matricule)))

-- Somme des ETP
ROUND(SUM(b.etp_contrat), 2)

-- Moyenne d'âge
ROUND(AVG(TRUNCATE(b.age, 0)), 2)

-- Moyenne d'ancienneté
ROUND(AVG(TRUNCATE(d.val_anc / IFNULL(f.libelle, 365.25), 0)), 2)

-- ETP moyen sur plusieurs périodes
ROUND(SUM(b.etp_contrat) / COUNT(DISTINCT a.PERIODE), 2)
```

## Gestion des valeurs NULL et formats spéciaux

```sql
-- Conversion des valeurs NULL
IFNone(JSON_VALUE(c.LABEL, CONCAT('$.', '#LANG#')), c.LIBELLE)

-- Traitement des dates nulles
AND (b.FIN_CONTRAT = 'null' OR b.FIN_CONTRAT > a.datefin)

-- Extraction de libellés multilingues
JSON_VALUE(c.LABEL, CONCAT('$.', '#LANG#'))
```

## Codes importants à retenir

### Types de contrats (NATURE_CONTRAT)
- '01' = CDI
- '02' = CDD standard
- '03' = Intérim
- '07' à '08' = Stages/Alternances
- '29' = Stagiaire

### Modalités de temps
- '10' = Temps plein

### Témoins de présence
- TEM_FP = 1 : Salarié présent en fin de mois
- TEM_EMB = 1 : Salarié embauché dans le mois
- TEM_SOR = 1 : Salarié sorti dans le mois

### Motifs de recours (CDD)
- '01', '12' = Remplacement
- '9000', '9001' = Codes spéciaux à exclure dans certaines analyses

## Exemples de correspondance langage naturel → SQL

1. **Question**: "Combien y a-t-il d'employés en CDI par statut conventionnel?"
   **SQL**:
   ```sql
   SELECT b.STATUT_CONVENTIONNEL, c.LIBELLE, COUNT(*) 
   FROM depot a 
   INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT 
   LEFT OUTER JOIN referentiel c ON c.RUBRIQUE_DSN = 'S21.G00.40.002' AND c.CODE = b.STATUT_CONVENTIONNEL 
   WHERE a.ID_USER = ? 
   AND b.NATURE_CONTRAT = '01'
   AND (b.FIN_CONTRAT = 'null' OR b.FIN_CONTRAT > a.datefin)
   AND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (
       SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))
       FROM depot w
       WHERE w.periode IN (#PERIODE#)
       AND w.id_user = a.id_user
   )
   GROUP BY 1, 2
   ORDER BY 1, 2;
   #DEPOT_a# #FACTS_b#
   ```

3. **Question**: "Calcule l'âge moyen par statut conventionnel"
   **SQL**:
   ```sql
   SELECT b.STATUT_CONVENTIONNEL, c.LIBELLE, ROUND(AVG(TRUNCATE(b.age, 0)), 2) 
   FROM depot a 
   INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT 
   LEFT OUTER JOIN referentiel c ON c.RUBRIQUE_DSN = 'S21.G00.40.002' AND c.CODE = b.STATUT_CONVENTIONNEL 
   WHERE a.ID_USER = ? 
   AND (b.FIN_CONTRAT = 'null' OR b.FIN_CONTRAT > a.datefin)
   AND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (
       SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))
       FROM depot w
       WHERE w.periode IN (#PERIODE#)
       AND w.id_user = a.id_user
   )
   GROUP BY 1, 2
   ORDER BY 1, 2;
   #DEPOT_a# #FACTS_b# #PERIODE#
   ```

4. **Question**: "Combien d'ETP avons-nous au total par département?"
   **SQL**:
   ```sql
   SELECT b.DEPARTEMENT, ROUND(SUM(b.etp_contrat), 2) AS TOTAL_ETP
   FROM depot a
   INNER JOIN facts b ON a.ID = b.ID_NUMDEPOT
   WHERE a.ID_USER = ?
   AND (b.FIN_CONTRAT = 'null' OR b.FIN_CONTRAT > a.datefin)
   AND CONCAT(SUBSTRING(a.periode, 5, 4), SUBSTRING(a.periode, 3, 2)) IN (
       SELECT MAX(CONCAT(SUBSTRING(w.periode, 5, 4), SUBSTRING(w.periode, 3, 2)))
       FROM depot w
       WHERE w.periode IN (#PERIODE#)
       AND w.id_user = a.id_user
   )
   GROUP BY 1
   ORDER BY 2 DESC;
   #DEPOT_a# #FACTS_b# #PERIODE#
   ```

5. **Question**: "Quelle est l'évolution mensuelle des embauches sur l'année 2023?"
   **SQL**:
   ```sql
   SELECT DATE_FORMAT(d.datedeb, '%Y%m') AS MOIS, COUNT(DISTINCT CONCAT(a.siren, a.nic, b.matricule, b.DEBUT_CONTRAT)) AS NB_EMBAUCHES
   FROM referentiel_periode d
   INNER JOIN depot a ON d.id_user = a.id_user AND d.periode = a.periode AND a.periode IN (#PERIODE#)
   INNER JOIN facts b ON a.id = b.id_numdepot 
     AND b.motif_recours NOT IN ('9000', '9001')
     AND DATE_FORMAT(b.debut_contrat, '%m%Y') = DATE_FORMAT(d.datedeb, '%m%Y')
   WHERE d.id_user = ?
   GROUP BY 1
   ORDER BY 1;
   #DEPOT_a# #FACTS_b# #PERIODE#
   ```# #FACTS_b# #PERIODE#
   ```

2. **Question**: "Quelle est la répartition par genre des nouveaux embauchés en CDI?"
   **SQL**:
   ```sql
   SELECT b.SEXE, COUNT(DISTINCT CONCAT(a.siren, a.nic, b.matricule, b.DEBUT_CONTRAT)) 
   FROM depot a 
   INNER JOIN facts b ON a.id = b.id_numdepot 
   WHERE a.ID_USER = ? 
   AND b.NATURE_CONTRAT = '01'
   AND b.debut_contrat >= a.datedeb 
   AND b.debut_contrat <= a.datefin 
   GROUP BY 1
   ORDER BY 1;
   #DEPOT_a