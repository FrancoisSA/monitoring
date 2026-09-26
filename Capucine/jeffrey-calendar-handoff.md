# Jeffrey - handoff calendrier

Date du handoff : 2026-09-21

## Objet de la prochaine session

Reprendre, verifier et si necessaire refaire la partie calendrier de Jeffrey : integration Google Calendar, commandes langage naturel, rappels, notes de weekend et traitement des emails `[AGENDA PRO]`.

La demande de cette session etait de preparer ce handoff. Aucun code n'a ete modifie pendant cette session.

## Point de reprise

- Branche de reference : `main`, dernier commit connu `3e16195 feat: release v1.5 - anti-doublons AGENDA PRO`.
- Le working tree contient deja des modifications post-v1.5. Ne pas les ecraser : consulter `git status` et `git diff` avant toute intervention.
- Le service principal est `services/google_calendar.py`.
- L'authentification partagee est dans `services/google_auth.py` et la configuration dans `config.py`.
- Le calendrier est consomme par `agent/mistral_agent.py`, `services/reminder.py`, `dashboard/web.py` et `dashboard/notes.py`.

## Comportement actuel a preserver

1. Les dates sont manipulees dans le fuseau configure, actuellement `Europe/Paris`.
2. Les evenements ordinaires sont lus et ecrits dans le calendrier `primary`.
3. `add_event` applique une deduplication sur titre normalise + debut + fin avant insertion.
4. `upsert_agenda_pro_event` cible par defaut un calendrier nomme `primary`, et peut resoudre un calendrier par son nom. La logique `[AGENDA PRO]` utilise `EVENT_UID`, `extendedProperties.private` et un identifiant SQLite existant.
5. Les notes de weekend sont des evenements Google Calendar de type journee, identifies par `jeffrey_weekend=true` et `sat_date`; SQLite sert de fallback.
6. Les rappels appellent `get_upcoming_events` dans un thread et evitent les envois repetes en memoire.
7. Les appels Google passent par OAuth2 et les scopes sont declares dans `config.py`. Ne jamais afficher ni recopier le contenu des fichiers de credentials ou token.

## Surfaces a lire en premier

- `services/google_calendar.py` : CRUD, normalisation des dates, deduplication, notes weekend, upsert AGENDA PRO.
- `services/reminder.py` : rappels temporels et scanner des emails AGENDA PRO.
- `agent/mistral_agent.py` : schemas et descriptions des outils calendrier exposes au modele.
- `dashboard/web.py` : API agenda, OAuth dashboard et notes weekend.
- `dashboard/notes.py` : contrat SQLite -> Google Calendar -> fallback.
- `test_timezone.py` : verification existante des conversions de fuseau.

Les descriptions generales, l'historique et l'etat du depot sont deja documentes dans `SPECIFICATION.MD`, `CODEBASE_REPORT.md` et `CLAUDE.md`. Les lire plutot que recopier leur contenu.

## Hypotheses a verifier rapidement

- Hypothese principale : les erreurs restantes de calendrier viendront plutot des contrats de dates et des cas limites Google Calendar que de l'appel API de base. Check discriminant : executer `python test_timezone.py`, puis des tests unitaires avec un faux client Google pour `add_event`, `upsert_agenda_pro_event` et les evenements journee.
- Les dates sans offset sont ambigues selon leur source. `google_calendar._localize` les interprete comme locales, tandis que le format AGENDA PRO est documente comme UTC avant conversion. Verifier que chaque appelant fournit la convention attendue avant de modifier `_localize`.
- Les filtres `privateExtendedProperty` sont utilises pour les notes et AGENDA PRO, mais la documentation du code indique que le lookup AGENDA PRO peut etre asynchrone. La source de verite de reprise est donc SQLite quand un `gcal_event_id` est disponible.

## Risques et points d'attention

- Ne pas casser la deduplication AGENDA PRO : elle depend de la reservation SQLite et du verrou dans `services/reminder.py`, pas uniquement de Google Calendar.
- Tester les dates avec offset explicite, suffixe `Z`, dates naives, DST Paris, evenement journee et multi-jours. Une comparaison de datetimes doit se faire sur des instants conscients du fuseau.
- Verifier le comportement si un evenement Google a ete supprime, si l'ID SQLite est obsolete, si deux evenements ont le meme titre/creneau, ou si un email contient plusieurs `EVENT_UID`.
- Les appels `googleapiclient` sont synchrones. Les appeler hors de la boucle asyncio dans les handlers et jobs, comme le fait deja le rappel Calendar avec `asyncio.to_thread`.
- Le dashboard est une surface de donnees sensibles. Ne pas elargir son exposition reseau ou affaiblir la garde OAuth pendant une refonte calendrier.
- La documentation signale une contrainte Python 3.10+ liee aux annotations `|`; confirmer l'interpreteur cible avant d'ajouter du code.

## Ordre de travail recommande

1. Lire les artefacts references ci-dessus et capturer `git status`/`git diff`.
2. Executer `python test_timezone.py` et compiler les modules concernes.
3. Ajouter ou renforcer des tests unitaires sans appels reseau pour les conversions, les evenements journee et la deduplication.
4. Corriger uniquement le contrat qui echoue, en conservant les signatures publiques des outils agent/dashboard.
5. Rejouer les tests locaux, puis faire un test d'integration Google seulement avec des credentials deja configures localement, sans les inclure dans les logs ou le handoff.
6. Avant de deployer, examiner les changements de securite et suivre le workflow de deploiement documente dans `CLAUDE.md`. Ne pas lancer de release ou de commit sans demande explicite.

## Suggested skills

Le prochain agent devrait appeler le Skill tool pour :

- `python-fact-grounded-coding` : recommande pour valider les faits Pylance, l'interpreteur Python, les types et les tests avant de modifier les modules Python calendrier.
- `pylance-docs` : seulement si la session doit resoudre un diagnostic, une configuration ou un comportement specifique de Pylance.

Aucun skill Foundry, de deploiement Azure ou de personnalisation d'agent n'est requis pour cette reprise calendrier.

## Definition of done

- Les conventions de fuseau et de type d'evenement sont explicites et couvertes par des tests locaux.
- Les operations CRUD, rappels, notes weekend et AGENDA PRO conservent leurs contrats existants ou documentent clairement toute rupture voulue.
- Les doublons ne sont pas recrees en cas de retry, redemarrage ou SQLite desynchronise.
- Aucun secret, identifiant personnel, token, contenu d'email ou URL privee n'apparait dans les logs, tests ou documents.
- Les validations executees et leurs resultats sont notes dans le compte-rendu de la prochaine session.