# Pi Monitor — CLAUDE.md

## Projet

**Pi Monitor** : Dashboard de surveillance pour Raspberry Pi 5.
Interface web Flask sur `http://FSA-PI5.local:9090`

## Accès SSH

```bash
# Réseau local
ssh -i ~/.ssh/id_ed25519 fsalazar@FSA-PI5.local

# Depuis l'extérieur (Tailscale)
ssh -i ~/.ssh/id_ed25519 fsalazar@100.81.42.20
```

## Tailscale

- **IP** : `100.81.42.20` — nom : `fsa-pi5-1`
- **Dashboard externe** : `http://100.81.42.20:9090`
- Installé le 13/04/2026 — compte `francois.salazar@`
- Fix disque USB (JMicron JMS567) : `usb-storage.quirks=152d:0562:u` ajouté dans `/boot/firmware/cmdline.txt` pour désactiver UAS et éviter le démontage intempestif de `/mnt/timecapsule`

## Architecture

| Fichier | Rôle |
|---|---|
| `web_monitor.py` | Point d'entrée Flask + routes API |
| `state.py` | État global partagé + thread de collecte |
| `config.py` | Constantes et chargement config.json |
| `system.py` | CPU, RAM, disques, processus, IoTracker |
| `services.py` | Services systemd, Samba |
| `network.py` | HTTP check, scan WiFi, ping gateway |
| `voltage.py` | Tension cœur + VoltageHistory |
| `disk.py` | Analyse récursive de dossiers |
| `dashboard.py` | Template HTML du dashboard |

## Déploiement (4 étapes)

```bash
# 1. Rsync
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='deploy_from_mac.sh' --exclude='deploy_custom.sh' \
  -e "ssh -i ~/.ssh/id_ed25519 -o ServerAliveInterval=10" \
  ./ fsalazar@FSA-PI5.local:/home/fsalazar/03-monitor/

# 2. (pas de package.json — projet Python, skip)

# 3. Redémarrer le service
ssh -i ~/.ssh/id_ed25519 fsalazar@FSA-PI5.local "sudo systemctl restart monitor"

# 4. Vérifier les logs
ssh -i ~/.ssh/id_ed25519 fsalazar@FSA-PI5.local "sudo journalctl -u monitor -n 20 --no-pager"
```

Informer l'utilisateur quand le service a été relancé.

## Hermes Agent (Mistral AI)

Assistant personnel (LLM cloud Hermes/Mistral) installé sur le Pi le 30/08/2026, migré de Mammouth AI vers Mistral AI direct le même jour.
Source : `Hermes-Pi/` dans ce repo (anciennement `Hermes-Mammouth/`). Web chat : `http://10.0.0.2:9191` (port 9191).

- **Répertoire** : `/home/fsalazar/hermes-pi/` (venv dans `venv/`, anciennement `/home/fsalazar/03-hermes-mammouth/`)
- **Service** : `hermes.service` → `venv/bin/python -m src.api` (API Flask, dashboard + `/api/chat`)
- **Config** : `.env` à la racine du projet sur le Pi — `MISTRAL_API_KEY` (obligatoire), `MISTRAL_MODEL`
- **Déploiement** : rsync du dossier `Hermes-Pi/` vers `hermes-pi/` puis `sudo systemctl restart hermes`
- **Mistral SDK** : mistralai 2.x n'expose plus `Mistral` à la racine ni `ToolDefinition` → imports compat dans `src/hermes_agent.py` et `src/api.py`

## Infra Pi

- **Service** : `monitor.service` dans `/etc/systemd/system/`
- **Répertoire** : `/home/fsalazar/03-monitor/`
- **PATH du service** : `/home/fsalazar/03-monitor/venv/bin` uniquement
  → Toujours utiliser les chemins absolus pour les binaires système (`/usr/bin/nmcli`, etc.)

## API REST

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/stats` | GET | Toutes les métriques |
| `/api/service/<name>/<action>` | POST | start/stop/restart service |
| `/api/temperature/<on\|off>` | POST | Toggle collecte température |
| `/api/wifi/monitor` | POST | Sélectionner SSID à surveiller |
| `/api/scan/<path>` | GET | Analyse taille dossiers |

## Time Capsule (Samba + Avahi)

Fichiers de setup pour transformer le Pi en serveur de sauvegarde Time Machine macOS.

| Fichier | Rôle |
|---|---|
| `setup-timecapsule-pi5.sh` | Script autonome d'installation complet (`sudo ./setup-timecapsule-pi5.sh`) |
| `setup-timecapsule-pi5.md` | Documentation pas-à-pas des 6 étapes de configuration |
| `verify-timecapsule.sh` | Vérification complète services, config, permissions |
| `check-samba.sh` | Vérification rapide Samba + Time Capsule |
| `samba-start.sh` | Vérifie ET démarre Samba + Avahi (10 étapes, auto-correction) |

**Statut** (au 13/04/2026) : Services opérationnels, démarrage automatique vérifié après reboot. Config macOS et première sauvegarde à faire.

**Points clés :**
- Disque externe `/dev/sda1` (916 Go ext4) monté sur `/mnt/timecapsule`, propriétaire `timemachine`
- Partage Samba : `[TimeMachine]`, visible via Bonjour/Avahi
- Partage Samba : `[fsalazar]` → `/home/fsalazar`, accès utilisateur `fsalazar`
- Modèle annoncé : `TimeCapsule8,119`
- Quota configuré dans `smb.conf` : `fruit:time machine max size = 850G` (relevé de 500G le 05/08/2026 — disque physique 916 Go, laisse ~66 Go de marge). Backup config : `/etc/samba/smb.conf.bak.20260805-154341`
- **Purge automatique** : quand le quota (850 Go) est atteint, Time Machine supprime tout seul les sauvegardes les plus anciennes pour libérer de la place. Comportement natif macOS lié au `time machine max size`, aucune config supplémentaire.
- Connexion macOS Time Machine → Sélectionner disque → login `timemachine`
- Mot de passe Samba `timemachine` : indice stocké dans `SECRETS.local.md` (fichier local ignoré par git, jamais versionné)
- Connexion Finder : `smb://10.0.0.2/fsalazar` (IP directe, plus fiable que `.local`)

**Incident réseau (12/07/2026) — nouveau routeur, Time Machine perdait le serveur :**
- Nouveau routeur installé sur `10.0.0.0/24` (remplace l'ancien `192.168.1.0/24`)
- `smb.conf` a `interfaces = lo eth0` + `bind interfaces only = yes` → Samba reste bindé sur l'IP qu'avait `eth0` au démarrage du service. Après un changement de routeur/IP, `smbd`/`nmbd` restent sur l'ancienne IP (invisible) tant qu'ils ne sont pas redémarrés.
- Fix : `sudo systemctl restart smbd nmbd` pour rebinder sur l'IP actuelle, **puis** IP statique posée sur le Pi (`nmcli con mod "Wired connection 1" ipv4.method manual ipv4.addresses 10.0.0.2/24 ipv4.gateway 10.0.0.1 ipv4.dns 10.0.0.1`) pour que l'IP ne redérive plus.
- Réflexe à avoir après tout changement de routeur/réseau : vérifier `ip addr show eth0` sur le Pi vs `ss -tlnp | grep -E ':445|:139'` — si l'IP écoutée par smbd ne correspond plus à l'IP actuelle de l'interface, redémarrer Samba.

**Correctif Avahi IPv6 (13/04/2026) :**
- `use-ipv6=no` dans `/etc/avahi/avahi-daemon.conf` pour forcer IPv4
- Raison : macOS résolvait `FSA-PI5.local` en IPv6 pour SMB → échec de connexion
- TimeMachine fonctionnait car découverte via `_adisk._tcp` (Bonjour, IPv4 direct)

## Affichage écran (HDMI)

Config ajoutée dans `/boot/firmware/config.txt` sous `[all]` :
```
hdmi_force_hotplug=1   # force le signal HDMI même sans écran au boot
hdmi_drive=2           # mode HDMI plein (son + image)
```
- Pi 5 : brancher sur **HDMI0** (port le plus proche du USB-C d'alimentation)
- L'écran doit être branché **avant** la mise sous tension

## Points d'attention

- Le Pi tourne sur `eth0` (filaire), IP statique fixée à `10.0.0.2/24` (gateway `10.0.0.1`, nouveau routeur depuis 12/07/2026)
- `wlan0` reste configuré (SSID `Livebox-2A30` vu en secours) mais `eth0` est prioritaire (métrique de route plus basse)
- Le scan WiFi via `nmcli` tourne toutes les **30s** pour ne pas surcharger
- La détection de chute de signal : alerte si signal < moyenne(5 derniers) - 20 pts
- SSH de secours via IP : `ssh -i ~/.ssh/id_ed25519 fsalazar@10.0.0.2` (si `.local` ne résout pas)

## RELEASE

Lorsqu'une release est demandée :
1. Relire le code pour détecter problèmes de performance ou sécurité — demander avant de modifier
2. Ajouter des commentaires pour qu'un humain puisse comprendre
3. Mettre à jour le manuel utilisateur (`Pi Monitor vX.Y.md`) avec date et numéro de version
4. Pousser dans git — si pas de repo, demander si l'utilisateur veut le créer

## MEMORY
 Quand je te demande de mémoriser l'état du projet, ou que je te donne la commande MEMORY : Mémorise un ésumé des échanges dans MEMORY.md afin de pouvoir reprendre la conversation plus tard. Stocke les informations qui te permetrons de retrouver le contexte.