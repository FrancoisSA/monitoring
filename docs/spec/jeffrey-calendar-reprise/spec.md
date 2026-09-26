Status: ready-for-agent

# Jeffrey — reprise calendrier — Spec

> Note de provenance : ce spec est synthétisé uniquement à partir du document
> de handoff `Capucine/jeffrey-calendar-handoff.md` (daté du 2026-09-21,
> aucune modification de code effectuée pendant cette session de handoff).
> Le code réel du projet Jeffrey vit dans `prj-jeffrey`, un dépôt distinct non
> accessible depuis cette session — ce spec n'a donc pas pu être vérifié
> contre le code, les ADR ou l'historique git de `prj-jeffrey`. Avant de
> démarrer l'implémentation, l'agent qui reprend ce ticket doit ouvrir
> `prj-jeffrey` et confronter ce spec à l'état réel du code, en particulier
> aux points listés dans "Hypothèses à vérifier" du handoff original.

## Problem Statement

Jeffrey (assistant personnel) intègre Google Calendar : lecture/écriture
d'événements, commandes en langage naturel, rappels temporels, notes de
weekend, et traitement d'emails `[AGENDA PRO]` avec déduplication. Une
release v1.5 a corrigé les doublons AGENDA PRO, mais des changements
post-v1.5 non commités existent dans le working tree, et une hypothèse forte
est que des bugs subsistent dans la gestion des fuseaux horaires et des cas
limites de dates (dates naïves ambiguës selon la source : `_localize`
suppose une date locale, alors que le format AGENDA PRO est documenté comme
UTC avant conversion). Sans clarification et couverture de tests, ces
ambiguïtés de contrat de date risquent de provoquer des évènements mal
placés dans le temps, des rappels manqués ou envoyés en double, et des
doublons AGENDA PRO recréés lors de redémarrages ou de désynchronisations
SQLite.

## Solution

Reprendre le module calendrier de Jeffrey sans en changer les contrats
publics : clarifier et documenter la convention de fuseau horaire attendue
par chaque appelant, couvrir par des tests unitaires (sans appel réseau) les
conversions de dates, les évènements journée/multi-jours, et la
déduplication AGENDA PRO, puis ne corriger que les contrats qui échouent
réellement aux tests. Le comportement existant (dédup, upsert AGENDA PRO,
notes de weekend, rappels) doit être préservé ou toute rupture volontaire
doit être documentée explicitement.

## User Stories

1. En tant qu'utilisateur de Jeffrey, je veux que les événements que je crée
   en langage naturel apparaissent à la bonne heure dans mon calendrier
   `primary`, quel que soit le fuseau de la source de la date, afin de ne
   pas manquer ou mal placer un rendez-vous.
2. En tant qu'utilisateur, je veux qu'un événement créé deux fois (même
   titre normalisé, même début, même fin) ne soit pas dupliqué dans mon
   calendrier, afin de garder un agenda propre.
3. En tant qu'utilisateur, je veux que les emails `[AGENDA PRO]` soient
   convertis en événements calendrier sans créer de doublons, même en cas de
   retry, de redémarrage du service, ou de désynchronisation entre SQLite et
   Google Calendar.
4. En tant qu'utilisateur, je veux que les emails `[AGENDA PRO]` contenant
   plusieurs `EVENT_UID` soient traités correctement (chaque UID résolu
   individuellement), afin qu'aucun événement ne soit perdu ou fusionné par
   erreur.
5. En tant qu'utilisateur, je veux que la déduplication AGENDA PRO utilise
   SQLite comme source de vérité quand un `gcal_event_id` est disponible,
   afin de rester cohérent même si le lookup Google Calendar est asynchrone
   ou en retard.
6. En tant qu'utilisateur, je veux que les notes de weekend restent des
   événements journée entière identifiés par `jeffrey_weekend=true` et
   `sat_date`, avec repli sur SQLite si Google Calendar est indisponible,
   afin de ne jamais perdre une note.
7. En tant qu'utilisateur, je veux recevoir mes rappels une seule fois même
   si le service redémarre ou si `get_upcoming_events` est appelé plusieurs
   fois dans un court intervalle, afin de ne pas être notifié en double.
8. En tant qu'utilisateur, je veux que les événements avec offset explicite,
   suffixe `Z`, dates naïves, ou traversant un changement d'heure (DST
   Europe/Paris), soient interprétés de façon cohérente et prévisible.
9. En tant qu'utilisateur, je veux que si un événement Google associé a été
   supprimé manuellement, ou si l'ID SQLite est obsolète, le système ne
   plante pas et adopte un comportement défini (recréation, ignorance
   documentée, ou erreur explicite) plutôt qu'un comportement indéterminé.
10. En tant qu'utilisateur, je veux que si deux événements distincts
    partagent le même titre et le même créneau, le système ne les fusionne
    pas à tort ni ne les duplique par erreur de correspondance.
11. En tant que développeur reprenant ce module, je veux que le fuseau
    horaire attendu par chaque appelant de `_localize` (ou équivalent) soit
    documenté explicitement, afin de pouvoir modifier la logique de date
    sans casser un des appelants.
12. En tant que développeur, je veux une suite de tests unitaires sans appel
    réseau (faux client Google) couvrant `add_event`,
    `upsert_agenda_pro_event`, et les événements journée, afin de pouvoir
    valider les correctifs sans dépendre de credentials Google en CI.
13. En tant que développeur, je veux que `python test_timezone.py` continue
    de passer et serve de garde-fou pour les conversions de fuseau après
    toute modification.
14. En tant qu'exploitant du service, je veux que les appels
    `googleapiclient` (synchrones) continuent d'être exécutés hors de la
    boucle asyncio (via `asyncio.to_thread` ou équivalent) dans tous les
    handlers et jobs qui les utilisent, afin de ne pas bloquer le event
    loop.
15. En tant qu'exploitant, je veux qu'aucun secret, credential, token,
    contenu d'email personnel ou URL privée n'apparaisse dans les logs,
    tests, ou tout document produit pendant cette reprise.
16. En tant qu'exploitant, je veux que la surface d'exposition réseau et la
    garde OAuth du dashboard (`dashboard/web.py`) ne soient ni élargies ni
    affaiblies pendant cette intervention, sauf demande explicite contraire.
17. En tant que mainteneur, je veux que les signatures publiques des outils
    calendrier exposés à l'agent (`agent/mistral_agent.py`) restent stables,
    afin que les changements internes n'impactent pas les intégrations
    existantes.
18. En tant que mainteneur, je veux que toute rupture de contrat volontaire
    (comportement changé intentionnellement) soit documentée clairement dans
    le compte-rendu de reprise plutôt que découverte a posteriori.

## Implementation Decisions

- **Aucune ré-architecture** : ce ticket ne prévoit pas de nouveaux modules
  ni de changement de schéma. Le périmètre est : `services/google_calendar.py`,
  `services/google_auth.py`, `services/reminder.py`, `config.py`,
  `agent/mistral_agent.py` (lecture seule côté schémas, pas de rupture de
  signature), `dashboard/web.py` et `dashboard/notes.py` (lecture seule sauf
  contrat de date interne qui échoue à un test).
- Le fuseau de référence reste configurable via `config.py`, actuellement
  `Europe/Paris` — ne pas le coder en dur ailleurs.
- La convention de fuseau pour les dates sans offset doit être rendue
  explicite avant toute modification de `_localize` : documenter, pour
  chaque appelant (`add_event`, `upsert_agenda_pro_event`, notes weekend,
  rappels), si la date entrante est supposée locale (`Europe/Paris`) ou UTC,
  et aligner l'implémentation sur cette convention documentée plutôt que sur
  une supposition implicite.
- La déduplication `add_event` (titre normalisé + début + fin) et la
  déduplication AGENDA PRO (SQLite + `EVENT_UID` + `extendedProperties.private`
  + verrou dans `services/reminder.py`) doivent rester la source de vérité ;
  SQLite prime sur Google Calendar quand un `gcal_event_id` existe déjà,
  compte tenu du lookup potentiellement asynchrone côté Google.
- Les notes de weekend restent des événements journée entière taggés
  `jeffrey_weekend=true` / `sat_date`, avec SQLite en fallback si Google
  Calendar échoue.
- Les appels `googleapiclient` restent synchrones et doivent continuer à
  être isolés du event loop asyncio via `asyncio.to_thread` (pattern déjà en
  place dans le rappel Calendar), y compris dans tout nouveau chemin de code
  ajouté pour corriger un contrat de date.
- Aucun changement de signature publique des outils calendrier exposés à
  l'agent, ni des routes API du dashboard, sauf si un test révèle qu'un
  contrat est intrinsèquement incorrect — dans ce cas, documenter la rupture
  plutôt que de la corriger silencieusement.
- Contrainte d'interpréteur : le code utilise potentiellement des
  annotations `X | Y` (syntaxe Python 3.10+) — confirmer la version cible de
  l'interpréteur dans `prj-jeffrey` avant d'ajouter du nouveau code utilisant
  cette syntaxe.
- Avant tout déploiement, suivre le workflow de déploiement documenté dans
  le `CLAUDE.md` de `prj-jeffrey` et faire relire les changements de
  sécurité. Ne pas déclencher de release ou de commit sans demande
  explicite de l'utilisateur.

## Testing Decisions

- **Seam retenu (validé avec l'utilisateur)** : les fonctions publiques de
  `services/google_calendar.py` (`add_event`, `upsert_agenda_pro_event`,
  gestion des événements journée/notes weekend, `get_upcoming_events`),
  testées via un **faux client Google API** injecté à cette frontière —
  aucun appel réseau réel. C'est le seam unique privilégié pour ce ticket ;
  éviter d'introduire des seams supplémentaires ailleurs (ex. dans le
  dashboard ou l'agent) sauf nécessité absolue.
- Un bon test ici vérifie le comportement observable (l'événement créé a la
  bonne heure/le bon fuseau, la dédup ne recrée pas d'événement, le fallback
  SQLite est utilisé quand attendu) — pas les détails internes d'appel au
  client Google (nombre d'appels, ordre exact des kwargs) sauf quand ce
  détail *est* le contrat testé (ex. vérifier qu'aucun appel réseau
  supplémentaire n'est fait en cas de doublon détecté).
- Prior art existant à réutiliser : `test_timezone.py` (déjà présent dans
  `prj-jeffrey`) pour les conversions de fuseau — doit continuer à passer
  après toute modification.
- Cas à couvrir explicitement dans les nouveaux tests unitaires : offset
  explicite, suffixe `Z`, date naïve, traversée DST Europe/Paris, événement
  journée entière, événement multi-jours, événement Google supprimé
  manuellement, ID SQLite obsolète, deux événements avec même titre/créneau,
  email AGENDA PRO contenant plusieurs `EVENT_UID`.
- Comparaisons de datetimes dans les tests doivent porter sur des instants
  conscients du fuseau (aware), jamais sur des naive datetimes comparées
  entre elles sans normalisation préalable.
- Aucun test de cette suite ne doit dépendre de credentials Google réels ni
  faire d'appel réseau ; un test d'intégration Google manuel (hors CI) reste
  possible en local avec des credentials déjà configurés, mais son résultat
  ne doit jamais être recopié dans les logs, les tests versionnés, ou ce
  spec/les tickets qui en découlent.

## Out of Scope

- Ajout de nouvelles fonctionnalités calendrier (nouveaux types
  d'événements, nouvelles commandes en langage naturel, nouveaux canaux de
  notification).
- Changement de fournisseur de calendrier ou de bibliothèque d'accès Google
  Calendar.
- Élargissement de l'exposition réseau du dashboard ou modification de la
  garde OAuth.
- Migration ou changement de schéma SQLite au-delà de ce qui est
  strictement nécessaire pour corriger un contrat de date qui échoue à un
  test.
- Déploiement en production ou création de release — nécessite une demande
  explicite séparée de l'utilisateur.
- Vérification ou mise à jour des ADR/documentation de `prj-jeffrey` autre
  que le compte-rendu de fin de session demandé par la "Definition of done"
  ci-dessous.

## Further Notes

- Ce spec vit dans `prj-raspberry` (dépôt où la commande a été exécutée)
  alors que le code concerné vit dans `prj-jeffrey`, un dépôt séparé non
  ouvert dans cette session. L'agent qui reprend ce ticket doit d'abord
  ouvrir `prj-jeffrey`, relire `git status`/`git diff` (le working tree
  contient des modifications post-v1.5 non commitées à ne pas écraser), et
  confronter ce spec à `SPECIFICATION.MD`, `CODEBASE_REPORT.md` et
  `CLAUDE.md` de ce dépôt avant de commencer à coder.
- Le document source de ce spec, `Capucine/jeffrey-calendar-handoff.md`
  (dans `prj-raspberry`), est probablement une copie égarée du handoff
  original qui existe déjà à sa place légitime dans
  `prj-jeffrey/jeffrey-calendar-handoff.md`. Ne pas le traiter comme la
  documentation canonique une fois ce ticket créé.
- Skills suggérés par le handoff original pour la reprise dans
  `prj-jeffrey` : `python-fact-grounded-coding` (validation Pylance,
  interpréteur, types, tests avant modification) systématiquement, et
  `pylance-docs` seulement en cas de diagnostic Pylance spécifique.
- Definition of done (reprise du handoff original) : conventions de fuseau
  et de type d'événement explicites et testées ; contrats CRUD/rappels/notes
  weekend/AGENDA PRO préservés ou ruptures documentées ; pas de doublons
  recréés en cas de retry/redémarrage/désync SQLite ; aucun secret ni
  donnée personnelle dans logs/tests/documents ; validations exécutées et
  résultats consignés dans le compte-rendu de la session qui traite ce
  ticket.
