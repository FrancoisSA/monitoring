# Capucine — Manuel utilisateur

Dernière mise à jour : 30 septembre 2026

Capucine est un assistant personnel qui répond sur Telegram, hébergé sur le
Raspberry Pi. Tout se passe dans la conversation avec le bot — texte ou
vocal.

## Commandes

| Commande | Rôle |
|---|---|
| `/aide` | Rappelle cette liste de commandes |
| `/echo <texte>` | Renvoie le texte tel quel (test de connectivité) |
| `/synthese <texte>` | Résume un texte fourni |
| `/presse` | Revue de presse automobile électrique |
| `/renault` | Veille Renault / Ampere |
| `/ia` | Digest actualité IA & frameworks agentiques |
| `/agenda <demande>` | Calendrier et tâches, en langage naturel |

## Vocal

Envoyer un **message vocal** Telegram est traité automatiquement comme une
commande `/agenda` — pas besoin de taper quoi que ce soit. Exemples à dire :

- "Ajoute un rendez-vous demain à 14h chez le dentiste"
- "Liste mes événements de la semaine"
- "Ajoute une tâche : acheter du pain"

Un message "🎤 Vocal reçu, en cours de traitement…" confirme la réception
pendant que la transcription se fait (peut prendre quelques dizaines de
secondes).

`/presse`, `/renault` et `/ia` peuvent aussi répondre avec un message vocal
en plus du texte (revue lue à voix haute).

## Calendrier et tâches (`/agenda`)

Comprend le langage naturel pour :
- Ajouter, modifier, supprimer ou rechercher un événement du calendrier
- Ajouter, lister, compléter ou rechercher une tâche (Google Tasks)

## Dashboard web

`http://FSA-PI5.local:9192` — vue d'ensemble des tâches, de l'agenda et des
notes de weekend. Accessible uniquement depuis le réseau local ou Tailscale,
pas de login applicatif.

## En cas de souci

- **Pas de réponse du bot** : vérifier que le service tourne sur le Pi —
  `sudo systemctl status capucine.service`
- **Le vocal ne fonctionne pas** : la transcription (texte → commande)
  nécessite que le Mac soit configuré et joignable — pas de repli local sur
  le Pi pour cette étape. La réponse vocale de `/presse` `/renault` `/ia`,
  elle, a un repli automatique (Piper, sur le Pi) si le Mac est indisponible.
- **Voir les logs** : `sudo journalctl -u capucine.service -n 50 --no-pager`
