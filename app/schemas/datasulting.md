# Description du schéma de la base de données RH (QUICKMS)

## Vue d'ensemble

Cette base de données contient des informations sur les dépôts de déclarations sociales (DSN - Déclaration Sociale Nominative), les entreprises, les salariés, les rémunérations, et les absences. Elle est structurée autour de plusieurs tables principales reliées par des clés étrangères.

## ⚠️ Framework obligatoire pour chaque requête

### Éléments obligatoires

Chaque requête SQL générée DOIT respecter ce framework de sécurité :

1. **Filtre utilisateur obligatoire** : 
   - `WHERE [alias_depot].ID_USER = ?` 
   - Exemple : `WHERE d.ID_USER = ?` (si l'alias de DEPOT est 'd')
   - La table DEPOT doit TOUJOURS être présente pour permettre ce filtre

2. **Hashtags obligatoires** (selon le contexte) :
   - `#DEPOT_[alias]#` : Quand on utilise la table DEPOT avec un alias
   - `#FACTS_[alias]#` : Quand on utilise la table FACTS avec un alias  
   - `#PERIODE#` : Pour les requêtes avec critères temporels

### Exemple de requête conforme

```sql
SELECT f.NOM, f.PRENOM, f.MNT_BRUT
FROM FACTS f
JOIN DEPOT d ON f.ID_NUMDEPOT = d.ID  
WHERE d.ID_USER = ? 
  AND f.NATURE_CONTRAT = '01'
ORDER BY f.NOM; #DEPOT_d# #FACTS_f#
```

## Tables principales

### 1. DEPOT

Table centrale qui contient les informations sur les dépôts de déclarations sociales.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique du dépôt (clé primaire) |
| NUMDEPOT | varchar(500) | Numéro du dépôt |
| ID_CLIENT | int | Identifiant du client |
| STATUS | varchar(50) | Statut du dépôt |
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
| SEXE | varchar(50) | Genre du salarié |
| DATE_NAI | date | Date de naissance du salarié |
| MATRICULE | varchar(250) | Matricule du salarié dans l'entreprise |
| TEM_FP | int | Témoin Présent Fin de mois (1 = Salarié présent le dernier jour du mois) |
| TEM_EMB | int | Témoin Embauche sur le mois (1 = Salarié embauché sur le mois) |
| TEM_SOR | int | Témoin sortie sur le mois (1 = Salarié sorti sur le mois) |
| NOM | varchar(250) | Nom de famille du salarié |
| NOM_USAGE | varchar(250) | Nom d'usage du salarié |
| PRENOM | varchar(250) | Prénom du salarié |
| DEBUT_CONTRAT | varchar(50) | Date de début du contrat |
| NATURE_CONTRAT | varchar(50) | Nature du lien entre l'employeur et l'individu |
| CATEGORIE | varchar(50) | Statut catégoriel Retraite complémentaire |
| MODALITE_TEMPS | varchar(50) | Modalité de temps de travail (temps plein ou partiel) |
| QUOTITE_TRAVAIL | varchar(50) | Durée contractuelle de travail |
| QUOTITE_TRAVAIL_REF | varchar(50) | Durée de travail de référence |
| MNT_BRUT | varchar(50) | Montant brut |
| MNT_BRUT_ETP | varchar(50) | Montant brut équivalent temps plein |
| NET_FISCAL | varchar(50) | Net fiscal |
| NET_VERSE | varchar(50) | Net versé |
| MOTIF_DEPART | varchar(500) | Motif de rupture du contrat |
| FIN_CONTRAT | varchar(20) | Date de fin du contrat |
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

### 5. ENTREPRISE

Table qui contient les informations sur les entreprises.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique (clé primaire) |
| CODE | varchar(50) | Code de l'entreprise |
| SIREN | varchar(50) | Numéro SIREN |
| SIRET_SIEGE | varchar(50) | SIRET du siège social |
| SIRET | varchar(50) | SIRET de l'établissement |
| DENOMINATION | text | Nom de la société |
| ADRESSE1 | varchar(1000) | Adresse ligne 1 |
| ADRESSE2 | text | Libellé de l'établissement |
| TYPE | varchar(200) | Type d'entreprise |
| EFFECTIF | varchar(200) | Effectif de l'entreprise |
| CA | varchar(500) | Chiffre d'affaires |
| ETAB_DENOMINATION | varchar(500) | Dénomination de l'établissement |
| ETAB_NIC | varchar(5) | NIC de l'établissement |
| SIEGE | tinyint(1) | Indicateur si l'établissement est le siège |
| datedeb | date | Date de début de validité |
| datefin | date | Date de fin de validité |

### 6. SOCIETE

Table simplifiée des informations sur les sociétés.

| Colonne | Type | Description |
|---------|------|-------------|
| siren | varchar(50) | Numéro SIREN (lien vers depot.siren) |
| denomination | varchar(500) | Nom de la société |

### 7. FACTS_AUTREREM et FACTS_PGI

Tables de rémunérations complémentaires.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique (clé primaire) |
| ID_NUMDEPOT | int | Lien vers la table depot (depot.id) |
| ID_FACT | int | Lien vers la table facts (facts.id) |
| ID_FACT_VERS | int | Lien vers la table facts_vers |
| SUID | varchar(400) | Identifiant unique du salarié |
| TYPE | varchar(50) | Type de rémunération |
| MONTANT | varchar(50) | Montant |
| DECLA_MONTANT | varchar(50) | Montant déclaré |
| DEB_PER_RATT | varchar(50) | Début de la période de rattachement |
| FIN_PER_RATT | varchar(50) | Fin de la période de rattachement |

### 8. REFERENTIEL

Table de référence pour les codes et libellés utilisés dans la DSN.

| Colonne | Type | Description |
|---------|------|-------------|
| ID | int | Identifiant unique (clé primaire) |
| RUBRIQUE_DSN | varchar(50) | Rubrique DSN concernée |
| CODE | varchar(255) | Code |
| LIBELLE | varchar(1000) | Libellé correspondant au code |
| LANG | varchar(2) | Langue du libellé (FR par défaut) |
| LINK_DATA | varchar(500) | Colonne de référence dans la base de données |

### 9. HASHTAG_MODELE

Table de référence pour les hashtags utilisés dans les requêtes SQL générées.

| Colonne | Type | Description |
|---------|------|-------------|
| HASHTAG | varchar(50) | Code HashTag présent dans les requêtes SQL |
| LIBELLE | varchar(255) | Libellé du HashTag |
| DESCRIPTION | varchar(2000) | Description du HashTag |
| TABLE_REF | varchar(50) | Table de référentiel pour cet axe/filtre |
| TABLE_DATA | varchar(50) | Table de donnée où se retrouve cet axe ou filtre |
| COLONNE_DATA | varchar(50) | Colonne correspondant à cet axe ou filtre |
| RUBRIQUE_DSN | varchar(50) | Rubrique DSN correspondant à ce HASHTAG |

## Hashtags disponibles et leur utilisation

### Hashtags principaux
- `#PERIODE#` : Période de paie (colonne PERIODE dans depot)
- `#DEPOT_[alias]#` : Table DEPOT avec son alias (obligatoire)
- `#FACTS_[alias]#` : Table FACTS avec son alias
- `#TYPECONTRAT#` : Nature du contrat (NATURE_CONTRAT dans facts)
- `#SEXE#` : Sexe du salarié (SEXE dans facts)
- `#CATEGORIE#` : Statut catégoriel (CATEGORIE dans facts)
- `#EMPLOI#` : Emploi/fonction (EMPLOI dans facts)
- `#AGE#` : Age du salarié (AGE dans facts)
- `#MATRICULE#` : Matricule du salarié
- `#ABSENCE#` : Motif d'arrêt (pour table facts_abs_final)

### Hashtags géographiques
- `#REGION#` : Région
- `#DEPARTEMENT#` : Département  
- `#SIREN#` : Numéro SIREN
- `#SIRET#` : Numéro SIRET

### Hashtags spécifiques clients (ORANO)
- `#PAYSORANO#`, `#EXPERT#`, `#TALENT#`, `#CSP#`, `#ORGA#`, `#METIER#`
- `#PLANFORM#`, `#THEMEFORM#`, `#ACTIONFORM#` (formation)

### Hashtags techniques
- `?` : Identifiant Client/Utilisateur (utilisé pour ID_USER)
- `#VALEUR#` : Valeur dynamique pour les drill-down

## Relations principales

1. `depot.ID` → `facts.ID_NUMDEPOT` : Un dépôt contient plusieurs facts (salariés)
2. `facts.ID` → `facts_rem.ID_FACT` : Un salarié peut avoir plusieurs éléments de rémunération
3. `facts.ID` → `facts_abs_final.id_fact` : Un salarié peut avoir plusieurs absences
4. `depot.siren` + `depot.nic` = `entreprise.SIRET` : Lien entre dépôt et entreprise
5. `depot.siren` → `societe.siren` : Lien entre dépôt et société

## Exemples de cas d'utilisation pour les requêtes

1. **Analyse de la masse salariale** : Utiliser les tables `depot`, `facts` et `facts_rem`
2. **Suivi des absences** : Utiliser les tables `facts` et `facts_abs_final`
3. **Analyse des effectifs** : Utiliser les tables `depot`, `facts`, et `entreprise`
4. **Analyse des rémunérations** : Utiliser les tables `facts`, `facts_rem`, `facts_autrerem`, et `facts_pgi`
5. **Reporting RH par département/service** : Utiliser les tables `facts` et `depot`
6. **Analyse des embauches et départs** : Utiliser les indicateurs `TEM_EMB` et `TEM_SOR` dans la table `facts`
7. **Analyse des heures travaillées et absences** : Utiliser `HEURE_TRAV`, `HEURE_REAL`, `HEURE_ABS` dans la table `facts`

## Conseils pour créer des requêtes

1. **TOUJOURS inclure le filtre de sécurité** : `WHERE [alias_depot].ID_USER = ?`
2. **TOUJOURS joindre la table DEPOT** : Directement ou indirectement via FACTS
3. **Utiliser les hashtags appropriés** : Minimum `#DEPOT_[alias]#`
4. Filtrer par période (PERIODE dans depot) pour les analyses temporelles
5. Utiliser les témoins (TEM_FP, TEM_EMB, TEM_SOR) pour identifier les mouvements de personnel
6. Pour les analyses d'absences, joindre facts et facts_abs_final sur id_fact
7. Pour les analyses de rémunération, joindre facts et facts_rem sur ID_FACT
8. Utiliser la table referentiel pour obtenir les libellés des codes utilisés

## Codes importants à retenir

### Types de contrats (NATURE_CONTRAT)
- '01' = CDI
- '02' = CDD
- '03' = Intérim
- '07' à '08' = Stages/Alternances

### Témoins de présence
- TEM_FP = 1 : Salarié présent en fin de mois
- TEM_EMB = 1 : Salarié embauché dans le mois
- TEM_SOR = 1 : Salarié sorti dans le mois