# Issue tracker: Local Markdown

Issues et specs pour ce repo vivent en fichiers markdown dans `docs/spec/`.

## Conventions

- Une fonctionnalité par dossier : `docs/spec/<feature-slug>/`
- Le spec est `docs/spec/<feature-slug>/spec.md`
- Les tickets d'implémentation sont un fichier par ticket dans `docs/spec/<feature-slug>/issues/<NN>-<slug>.md`, numérotés depuis `01`, jamais un fichier combiné
- L'état de triage est enregistré via une ligne `Status:` en haut de chaque fichier issue
- Les commentaires et l'historique de conversation s'ajoutent en bas du fichier sous un titre `## Comments`

## Quand un skill dit "publier sur le tracker d'issues"

Créer un nouveau fichier sous `docs/spec/<feature-slug>/` (en créant le dossier si besoin).

## Quand un skill dit "récupérer le ticket concerné"

Lire le fichier au chemin référencé. L'utilisateur passera normalement le chemin ou le numéro d'issue directement.

## Wayfinding operations

Utilisé par `/wayfinder`. La **map** est un fichier avec un fichier **enfant** par ticket.

- **Map** : `docs/spec/<effort>/map.md` (corps Notes / Decisions-so-far / Fog).
- **Ticket enfant** : `docs/spec/<effort>/issues/NN-<slug>.md`, numéroté depuis `01`, avec la question dans le corps. Une ligne `Type:` enregistre le type de ticket (`research`/`prototype`/`grilling`/`task`) ; une ligne `Status:` enregistre `claimed`/`resolved`.
- **Blocage** : une ligne `Blocked by: NN, NN` en haut. Un ticket est débloqué quand tous les fichiers listés sont `resolved`.
- **Frontier** : scanner `docs/spec/<effort>/issues/` pour les fichiers ouverts, non bloqués et non réclamés ; le premier par numéro gagne.
- **Claim** : mettre `Status: claimed` et sauvegarder avant tout travail.
- **Resolve** : ajouter la réponse sous un titre `## Answer`, mettre `Status: resolved`, puis ajouter un pointeur de contexte (résumé + lien) dans les Decisions-so-far de `map.md`.
