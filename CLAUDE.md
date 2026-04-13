# Pi Monitor — CLAUDE.md

## Projet

**Pi Monitor** : Dashboard de surveillance pour Raspberry Pi 5.
Interface web Flask sur `http://FSA-PI5.local:9090`

## Accès SSH

```bash
ssh -i ~/.ssh/id_ed25519 fsalazar@FSA-PI5.local
```

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
- Quota configuré dans `smb.conf` : `fruit:time machine max size = 500G`
- Connexion macOS Time Machine → Sélectionner disque → login `timemachine`
- Connexion Finder : `smb://192.168.1.60/fsalazar` (IP directe, plus fiable que `.local`)

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

- `wlan0` est **déconnecté** — le Pi tourne sur `eth0` (filaire), IP : `192.168.1.60`
- Le scan WiFi via `nmcli` tourne toutes les **30s** pour ne pas surcharger
- La détection de chute de signal : alerte si signal < moyenne(5 derniers) - 20 pts
- SSH de secours via IP : `ssh -i ~/.ssh/id_ed25519 fsalazar@192.168.1.60` (si `.local` ne résout pas)

## RELEASE

Lorsqu'une release est demandée :
1. Relire le code pour détecter problèmes de performance ou sécurité — demander avant de modifier
2. Ajouter des commentaires pour qu'un humain puisse comprendre
3. Mettre à jour le manuel utilisateur (`Pi Monitor vX.Y.md`) avec date et numéro de version
4. Pousser dans git — si pas de repo, demander si l'utilisateur veut le créer
