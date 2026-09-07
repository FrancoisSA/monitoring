Status: ready-for-agent

# Framework agentique Capucine — Spec

## Problem Statement

L'utilisateur veut un assistant personnel accessible depuis Telegram, capable
d'exécuter plusieurs tâches distinctes (revue de presse quotidienne, gestion
de planning, synthèse d'informations, et d'autres à venir) sans avoir à ouvrir
un outil dédié à chacune. Il dispose déjà d'un bot Telegram ("Capucine",
`@hermes_t4qq3hkd2oaq5fr7_bot`) et d'un Raspberry Pi 5 avec Ollama installé
localement (petits modèles 0.5B–3B) ainsi qu'une clé API Mistral existante.

Le Pi héberge déjà plusieurs autres services (Pi Monitor, Samba/Time Machine,
Tailscale) avec des ressources limitées (CPU/RAM) — toute nouvelle charge
ajoutée doit rester légère pour ne pas dégrader ces services existants.
Le Pi n'est volontairement pas exposé publiquement sur internet (pas de port
entrant ouvert), ce qui contraint le mode d'intégration Telegram.

Une précédente tentative avec un outil tiers (QwenPaw) a été désinstallée du
Pi car elle ne correspondait pas au besoin — ce nouveau framework est un
projet neuf, écrit spécifiquement pour cet usage plutôt que basé sur un
framework agentique générique.

## Solution

Un service Python unique, léger, tournant en permanence sur le Raspberry Pi,
qui :

- Interroge l'API Telegram en polling (pas de webhook — évite d'exposer un
  port entrant sur le Pi, contrainte de sécurité explicite) pour recevoir les
  messages du seul chat_id autorisé (accès strictement personnel).
- Route chaque message vers un agent via des commandes Telegram explicites
  (`/presse`, `/planning`, `/synthese`, etc.), à travers une couche de
  routage abstraite conçue pour pouvoir être remplacée plus tard par un
  routage par intention/LLM sans réécrire le cœur du framework.
- Chaque agent est un module Python respectant une interface commune
  (`Agent.handle`), déclarant statiquement son backend LLM par défaut
  (Ollama local `qwen2.5:3b`, ou API Mistral `mistral-small-latest`), les
  deux valeurs restant facilement reconfigurables.
- Les agents partagent une interface d'outils minimale et commune
  (function-calling / registre d'outils), évitant la duplication entre
  agents (ex. accès web, accès calendrier) tout en gardant chaque outil
  isolé et testable.
- Un historique court par agent est conservé dans un fichier SQLite léger
  (pas de serveur de base de données).
- Les déclenchements planifiés (ex. revue de presse chaque matin) passent
  par cron système, qui communique avec le service déjà démarré via un
  socket Unix local — pas de relance d'un interpréteur Python complet à
  chaque exécution planifiée, pas de port réseau supplémentaire.
- Un garde-fou simple limite le nombre d'appels quotidiens à l'API Mistral
  (configurable) ; au dépassement, l'agent concerné refuse d'exécuter la
  requête et prévient clairement l'utilisateur par Telegram plutôt que de
  basculer silencieusement sur un modèle local dégradé.
- Un journal de performance (latence, modèle utilisé, succès/échec par
  agent) est tenu dans SQLite, consultable via une commande Telegram
  `/stats` et via un fichier de synthèse `.md` régénéré, lisible sans outil
  supplémentaire — sert à ajuster les choix de modèles par la suite.
- Le code est volontairement minimal et custom (pas de framework agentique
  générique type LangChain — coût mémoire/temps d'import jugé excessif pour
  la contrainte de légèreté sur le Pi), mais commenté pédagogiquement pour
  rester compréhensible par un néophyte, et structuré autour d'un seam de
  test unique et explicite.

## User Stories

1. En tant qu'utilisateur, je veux envoyer `/presse` sur Telegram et recevoir une revue de presse générée, afin de m'informer sans devoir consulter plusieurs sources moi-même.
2. En tant qu'utilisateur, je veux recevoir automatiquement la revue de presse chaque matin sans avoir à la demander, afin qu'elle s'intègre à ma routine sans action de ma part.
3. En tant qu'utilisateur, je veux envoyer `/planning` sur Telegram pour interroger ou faire gérer mon planning, afin de piloter mon agenda depuis la même interface que le reste.
4. En tant qu'utilisateur, je veux envoyer `/synthese` avec un contenu à résumer, afin d'obtenir rapidement l'essentiel d'une information sans la lire en entier.
5. En tant qu'utilisateur, je veux que seul mon compte Telegram (mon chat_id) puisse déclencher les agents, afin qu'aucun tiers ne puisse consommer mon quota d'API ou interagir avec mes données personnelles.
6. En tant qu'utilisateur, je veux que le service ne consomme pas de ressources excessives sur mon Raspberry Pi, afin de ne pas dégrader les autres services qui y tournent déjà (Pi Monitor, Samba, Tailscale).
7. En tant qu'utilisateur, je veux que le Pi reste sans port entrant exposé pour cette fonctionnalité, afin de ne pas augmenter la surface d'attaque de ma machine.
8. En tant qu'utilisateur, je veux que chaque agent choisisse automatiquement entre Ollama local et l'API Mistral selon sa complexité déclarée, afin de limiter les coûts et la latence sans avoir à choisir moi-même à chaque fois.
9. En tant qu'utilisateur, je veux pouvoir changer facilement le modèle par défaut (local ou cloud) utilisé par un agent, afin d'ajuster les performances sans devoir modifier la logique de l'agent.
10. En tant qu'utilisateur, je veux consulter un journal de performance (latence, modèle utilisé, taux de succès) via `/stats` sur Telegram, afin de décider rapidement si un modèle doit être changé.
11. En tant qu'utilisateur, je veux aussi disposer d'un fichier de synthèse `.md` lisible du journal de performance, afin de pouvoir l'analyser plus en détail sans dépendre de Telegram.
12. En tant qu'utilisateur, je veux être prévenu clairement sur Telegram si la limite quotidienne d'appels Mistral est atteinte, afin de comprendre pourquoi une réponse n'a pas été produite plutôt que de recevoir une réponse dégradée sans explication.
13. En tant qu'utilisateur, je veux pouvoir configurer la limite quotidienne d'appels Mistral, afin de l'ajuster selon mon usage réel et mon budget.
14. En tant que développeur du framework, je veux pouvoir ajouter un nouvel agent en ajoutant un seul module Python respectant une interface commune, afin de ne pas devoir modifier le cœur du framework à chaque nouvel agent.
15. En tant que développeur du framework, je veux que les agents partagent une interface d'outils commune (function-calling), afin d'éviter de dupliquer l'accès aux mêmes ressources externes (web, calendrier, etc.) dans chaque agent.
16. En tant que développeur du framework, je veux que le routage commande → agent passe par une couche abstraite, afin de pouvoir introduire un orchestrateur basé sur un LLM plus tard sans réécrire le routage existant.
17. En tant que développeur du framework, je veux un point d'entrée unique et testable par agent (`Agent.handle`), afin de pouvoir tester chaque agent sans dépendre d'un vrai appel réseau vers Ollama ou Mistral.
18. En tant que développeur du framework, je veux pouvoir injecter un faux client LLM en test, afin de valider le comportement de chaque agent de façon déterministe et rapide.
19. En tant que développeur du framework, je veux que le code soit commenté pour expliquer le pourquoi (pas seulement le quoi), afin qu'un néophyte puisse comprendre et faire évoluer le framework.
20. En tant qu'utilisateur, je veux que les jobs planifiés (cron) déclenchent le service déjà actif plutôt que de démarrer un nouveau processus à chaque fois, afin de limiter la consommation CPU/RAM liée aux tâches planifiées.
21. En tant qu'utilisateur, je veux que l'historique de conversation de chaque agent soit conservé localement (SQLite), afin que l'agent conserve du contexte utile entre deux échanges sans dépendre d'un service externe.
22. En tant qu'utilisateur, je veux réutiliser la clé API Mistral et le token du bot Telegram Capucine déjà configurés, afin de ne pas avoir à refaire cette configuration depuis zéro.

## Implementation Decisions

- **Projet neuf** : ce framework n'est pas une évolution du code `Hermes-Pi` existant (celui-ci n'est pas restauré). Seules les clés API déjà provisionnées sont réutilisées : `MISTRAL_API_KEY` et `TELEGRAM_BOT_TOKEN` (bot Capucine), déjà présentes dans `Hermes-Pi/.env` sur le Mac et à reporter dans la config de ce nouveau projet.
- **Cible de déploiement** : Raspberry Pi 5 (`FSA-PI5`), en tant que service `systemd` long-running (pattern à réutiliser : cf. `monitor.service` existant sur le Pi pour le style de service).
- **Intégration Telegram** : polling (pas de webhook), pour ne pas exposer de port entrant sur le Pi. Un seul `chat_id` autorisé (whitelist stricte), tout autre expéditeur ignoré.
- **Modèle de process** : un seul service Python long-running qui gère à la fois le polling Telegram et l'exécution des agents. Les déclenchements planifiés (cron système) communiquent avec ce service déjà démarré via un **socket Unix local** (pas de port TCP, même en local) plutôt que de relancer un process.
- **Routage** : commandes Telegram explicites (`/presse`, `/planning`, `/synthese`, ...) résolues vers un agent via une interface `Router` abstraite (ex. `Router.route(command) -> Agent`), conçue pour permettre un remplacement futur par un routage par intention/LLM sans changement d'interface pour les agents eux-mêmes.
- **Interface agent commune** : chaque agent est un module Python exposant un point d'entrée unique `Agent.handle(command_args, deps) -> AgentResponse`. `deps` regroupe les dépendances injectables : client LLM, registre d'outils, accès au store SQLite.
- **Abstraction LLM** : une interface commune (`LLMClient`) unifie Ollama local et l'API Mistral cloud, permettant à un agent de ne pas connaître le backend réel utilisé. Chaque agent déclare **statiquement** dans sa config quel backend/modèle utiliser par défaut — pas de classification dynamique de la complexité en v1.
- **Modèles par défaut** (reconfigurables) : `qwen2.5:3b` via Ollama local, `mistral-small-latest` via l'API Mistral. Doivent être modifiables facilement (fichier de config ou constantes centralisées) au vu des données du journal de performance.
- **Registre d'outils partagé** : une interface minimale de function-calling, commune à tous les agents, permettant de déclarer un outil une fois (ex. accès web, accès calendrier) et de l'équiper à n'importe quel agent. Priorité à la simplicité sur la complétude en v1.
- **Persistance** : un fichier SQLite unique et léger pour (a) l'historique court de conversation par agent, et (b) le journal de performance (latence, modèle utilisé, agent, succès/échec, horodatage) — deux tables distinctes dans la même base, pas deux systèmes de stockage séparés.
- **Garde-fou de coût Mistral** : un compteur quotidien d'appels à l'API Mistral, avec une limite configurable. Au dépassement, l'agent concerné n'exécute pas la requête et répond immédiatement via Telegram avec un message explicite ("limite Mistral atteinte pour aujourd'hui") — pas de repli automatique et silencieux vers Ollama.
- **Consultation des performances** : une commande Telegram `/stats` affichant un résumé (latence moyenne, taux de succès par agent/modèle sur une période récente), et un fichier `.md` de synthèse régénéré à intervalle régulier ou à la demande, lisible directement sans outil.
- **Extensibilité** : ajouter un agent = ajouter un module Python respectant l'interface `Agent.handle`, sans modification du cœur du framework (service, routeur, store, client LLM).
- **Style de code** : implémentation custom minimale (pas de framework agentique générique de type LangChain/LangGraph — coût d'import/mémoire jugé excessif pour la contrainte de légèreté du Pi), commentée pédagogiquement (expliquer le pourquoi, pas seulement le quoi), destinée à être compréhensible par un néophyte.
- **Seam de test unique** : `Agent.handle(command_args, deps)`, avec `deps` injectant `LLMClient` (mockable — aucun appel réseau réel en test) et le registre d'outils (mockable par outil). Le store SQLite n'est pas mocké : les tests utilisent un vrai fichier SQLite temporaire. Le routeur (`Router.route`) est une fonction pure testée directement, sans mock nécessaire. La couche Telegram (polling, parsing des updates) reste une fine couche de câblage en périphérie, volontairement hors du périmètre de test unitaire approfondi.

## Testing Decisions

- Un bon test ici valide le **comportement observable** d'un agent (étant donné une commande et des dépendances injectées, quelle `AgentResponse` est produite, quelles entrées SQLite sont écrites) — pas les détails internes d'implémentation (ex. ne pas tester le contenu exact d'un prompt envoyé au LLM, seulement le résultat produit à partir d'une réponse simulée).
- Modules à tester en priorité :
  - Chaque agent, via son point d'entrée `Agent.handle`, avec un `LLMClient` fake déterministe (pas d'appel réseau réel vers Ollama ni Mistral dans les tests).
  - Le routeur (`Router.route`) : fonction pure, un test par commande reconnue + un test pour une commande inconnue/non autorisée.
  - Le garde-fou de limite Mistral : test du comportement au dépassement (refus + message explicite), avec compteur simulé.
  - Le registre d'outils : chaque outil testé isolément avec ses propres mocks (ex. un outil web mocké au niveau de la requête HTTP, pas plus haut).
  - Le store SQLite (historique + journal de performance) : tests d'intégration légers sur fichier temporaire, vérifiant les écritures/lectures attendues.
- Pas de prior art directement réutilisable dans ce repo (projet neuf) — le style de test (fichiers `tests/<module>` en Python, un test unitaire par comportement) peut s'inspirer de la structure existante de l'ancien `Hermes-Pi/tests/` (avant sa suppression), qui suivait déjà ce découpage par comportement plutôt que par fichier source.

## Out of Scope

- Restauration ou réutilisation du code source de l'ancien projet `Hermes-Pi` (décision explicite : projet neuf, seules les clés API sont reprises).
- Routage par intention/orchestrateur LLM (l'architecture le permet, mais ce n'est pas construit en v1 — commandes explicites uniquement).
- Classification dynamique de la complexité d'une requête pour choisir automatiquement entre Ollama et Mistral (backend statique par agent en v1).
- Exposition d'un webhook Telegram ou de tout endpoint réseau public sur le Pi.
- Accès multi-utilisateurs ou multi-chat Telegram (accès restreint à un seul chat_id).
- Intégration effective avec Google Calendar/Tasks/Gmail ou toute autre source de données externe concrète pour les agents planning/synthèse — seule l'interface d'outils partagée est spécifiée ici : les outils concrets nécessaires à chaque agent (ex. lecture de calendrier, sources de presse) seront définis lors de l'implémentation de chacun.
- Facturation ou suivi de coût en temps réel de l'API Mistral au-delà du simple compteur d'appels quotidien.
- Interface web ou dashboard autre que Telegram et le fichier `.md` de synthèse.

## Further Notes

- Le bot Telegram Capucine (`@hermes_t4qq3hkd2oaq5fr7_bot`) et son token sont déjà opérationnels et vérifiés (testés via `getUpdates`) ; le `chat_id` personnel de l'utilisateur (`643004339`) est déjà identifié et doit être la seule valeur autorisée dans la whitelist d'accès.
- Le Raspberry Pi dispose actuellement d'Ollama avec les modèles `llama3.2:1b`, `qwen2.5:0.5b` et `qwen2.5:3b` déjà téléchargés — `qwen2.5:3b` est le choix retenu par défaut parmi ceux-ci.
- Le service `monitor.service` (Pi Monitor) tourne déjà sur le Pi comme référence de pattern systemd léger à suivre pour le nouveau service.
- Aucune limite chiffrée précise n'a été fixée pour le garde-fou Mistral (nombre d'appels/jour) — à définir lors de l'implémentation, en gardant la valeur facilement configurable.
- Le nom exact des commandes Telegram (`/presse`, `/planning`, `/synthese`) et le nom du projet/dossier ne sont pas figés — à confirmer lors du découpage en tickets d'implémentation.
