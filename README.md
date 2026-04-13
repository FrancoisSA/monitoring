# Documentation Technique - Pi Monitor

## Vue d'ensemble

Pi Monitor est un système de surveillance complet pour Raspberry Pi 5, offrant à la fois une interface console interactive et une interface web. Le système surveille les métriques système (CPU, RAM, disques), les services, les serveurs HTTP, les partages SMB et la tension d'alimentation.

## Architecture

### Composants principaux

| Fichier | Rôle |
|---|---|
| `web_monitor.py` | Point d'entrée Flask + routes API REST |
| `state.py` | État global partagé + thread de collecte (bg_loop) |
| `config.py` | Constantes et chargement config.json |
| `system.py` | CPU, RAM, disques, processus, IoTracker |
| `services.py` | Services systemd, Samba |
| `network.py` | HTTP check, scan WiFi (nmcli), ping gateway |
| `voltage.py` | Tension cœur + VoltageHistory |
| `disk.py` | Analyse récursive de dossiers |
| `dashboard.py` | Template HTML du dashboard (inline) |
| `monitor.py` | Interface console interactive (Rich) |
| `monitor.service` | Service systemd pour démarrage automatique de web_monitor.py |
| `config.json` | Configuration des serveurs à surveiller |

### Dépendances

- Python 3.8+
- psutil >= 5.9.0
- requests >= 2.31.0
- rich >= 13.0.0
- flask >= 3.0.0

## Installation et déploiement

### Sur le Raspberry Pi

1. **Prérequis système :**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip samba samba-common-bin
   ```

2. **Installation des dépendances Python :**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configuration :**
   - Modifier `config.json` pour ajouter les serveurs à surveiller
   - Ajuster les chemins dans `monitor.service` si nécessaire

4. **Déploiement du service web :**
   ```bash
   sudo cp monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable monitor
   sudo systemctl start monitor
   ```

### Accès

- **Interface web :** `http://FSA-PI5.local:9090`
- **Interface console :** `python3 monitor.py` (localement sur le Pi)

## Fonctionnalités

### Surveillance système
- Utilisation CPU et température
- Utilisation RAM
- Espace disque par partition
- Débits I/O disque et réseau

### Services systemd
- Statut des 5 services configurés : `hcautomation`, `budget-web`, `budget-bot`, `jeffrey`, `monitor`
- Contrôle à distance (start/stop/restart) via interface web

### Serveurs HTTP
- Vérification périodique des serveurs configurés dans `config.json`
- Détection automatique des processus web locaux (scan des ports TCP en écoute)
- Mesure de latence et codes de statut HTTP

### Monitoring WiFi
- Scan des réseaux visibles via `nmcli` (toutes les 30s, cache NetworkManager)
- Sélection d'un SSID à surveiller (signal en %)
- Historique du signal sur 30 minutes (sparkline)
- Alerte si le signal chute de plus de 20 points par rapport à la moyenne des 5 derniers échantillons
- Ping gateway (via eth0) comme métrique complémentaire

### Partages SMB
- Liste des partages configurés dans `/etc/samba/smb.conf`
- Partages actifs : `[TimeMachine]` (backup macOS) + `[fsalazar]` (dossier personnel)
- Liens cliquables pour accès Finder (macOS)

### Tension d'alimentation
- Surveillance de la tension cœur Raspberry Pi
- Détection des événements de sous-tension
- Historique sur 24 heures

## API REST

### Endpoints principaux

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/stats` | GET | Toutes les métriques système |
| `/api/service/<name>/<action>` | POST | start/stop/restart service systemd |
| `/api/temperature/<on\|off>` | POST | Active/désactive la collecte température |
| `/api/wifi/monitor` | POST | Sélectionner un SSID à surveiller |
| `/api/scan/<path>` | GET | Analyse des tailles de dossiers |

### Format de réponse

```json
{
  "system": {
    "cpu_percent": 15.2,
    "cpu_temp": 45.0,
    "mem_total_mb": 8192,
    "mem_used_mb": 2048,
    "mem_percent": 25.0,
    "uptime": "2h 30m",
    "hostname": "FSA-PI5"
  },
  "disks": [...],
  "services": [...],
  "http": [...],
  "voltage": {...}
}
```

## Interface console

### Raccourcis clavier

- `f` : Afficher/masquer le panneau SMB
- `c` : Afficher/masquer le Top CPU
- `1-5` : Sélectionner un service pour contrôle
- `r` : Redémarrer le service sélectionné
- `a` : Démarrer le service sélectionné
- `x` : Arrêter le service sélectionné
- `t` : Ouvrir un terminal interactif
- `s` : Confirmer l'arrêt du système
- `q` : Quitter

### Métriques affichées

- Système : CPU, RAM avec barres de progression
- Disques : Utilisation par partition
- Flux I/O : Débits disque et réseau
- Services : Statut systemd avec uptime
- Serveurs HTTP : Statut et latence
- Voltage : Tension avec historique et alertes

## Sécurité

### Considérations

- L'interface web écoute sur toutes les interfaces (0.0.0.0:9090)
- Les commandes systemctl utilisent sudo
- Pas d'authentification implémentée
- Exposition des métriques système sensibles

### Recommandations

- Restreindre l'accès au port 9090 (firewall)
- Implémenter une authentification basique
- Utiliser HTTPS en production
- Auditer les permissions des fichiers de configuration

### Problèmes connus à corriger (backlog)

| # | Type | Fichier | Description |
|---|------|---------|-------------|
| 1 | 🔴 Sécurité | `web_monitor.py` | `/api/scan/<path>` sans restriction — n'importe quel client réseau peut scanner `/etc`, `/root`, etc. Corriger avec une liste blanche des points de montage autorisés. |
| 2 | 🟡 Sécurité | `web_monitor.py` | Pas d'authentification sur les routes d'action (`/api/service`, `/api/temperature`, `/api/wifi/monitor`). Acceptable en réseau local privé, à sécuriser pour un usage étendu. |
| 3 | 🟠 Performance | `state.py` | Vérifications HTTP séquentielles dans `bg_loop()` — un timeout par serveur hors-ligne multiplie le temps de cycle (ex: 3 serveurs × 5s = 15s au lieu de 2s). Corriger avec `ThreadPoolExecutor`. |

## Maintenance

### Logs et debugging

- Les erreurs sont affichées dans la console
- Point de diagnostic : `http://FSA-PI5.local:9090/diag`
- Vérification des services : `sudo systemctl status monitor`

### Mise à jour

1. Arrêter le service : `sudo systemctl stop monitor`
2. Mettre à jour le code
3. Redémarrer : `sudo systemctl start monitor`

### Sauvegarde

- `config.json` : Configuration des serveurs
- `/etc/samba/smb.conf` : Configuration SMB
- `/etc/systemd/system/monitor.service` : Configuration du service

## Dépannage

### Problèmes courants

1. **Interface web inaccessible :**
   - Vérifier que le service est actif : `sudo systemctl status monitor`
   - Contrôler le port 9090 : `netstat -tlnp | grep 9090`

2. **Métriques vides :**
   - Vérifier les permissions psutil
   - Tester vcgencmd : `vcgencmd measure_volts core`

3. **SMB non détecté :**
   - Vérifier la configuration `/etc/samba/smb.conf`
   - Contrôler l'état des services smbd/nmbd

### Commandes de diagnostic

```bash
# État du service
sudo systemctl status monitor

# Logs du service
sudo journalctl -u monitor -f

# Test des dépendances
python3 -c "import psutil, flask, rich; print('OK')"

# Vérification réseau
curl http://localhost:9090/api/stats
```

## Développement

### Structure du code

- Fonctions utilitaires dans le début des fichiers
- Thread de collecte des données en arrière-plan
- Interface principale avec boucle d'événements
- API REST avec endpoints Flask

### Extensions possibles

- Ajout de métriques personnalisées
- Notifications (email, webhook)
- Stockage historique des données
- Authentification et autorisation
- Interface mobile responsive

---

**Version :** 1.2  
**Date :** 13 avril 2026  
**Auteur :** François Salazar

## Changelog

### v1.2 — 13 avril 2026
- Refactorisation : découpage en modules Python (`state.py`, `config.py`, `system.py`, `services.py`, `network.py`, `voltage.py`, `disk.py`)
- Ajout du monitoring WiFi : sélection SSID, historique signal, alerte chute, ping gateway
- Correction du toggle température (bouton ON/OFF dans le dashboard)
- Ajout de `samba-start.sh` : vérification et démarrage automatique Samba + Avahi
- Correction `setup-timecapsule-pi5.sh` : gestion du cas disque déjà monté (évite l'erreur `fuseblk`)
- Correctif Avahi IPv6 (`use-ipv6=no`) pour que `FSA-PI5.local` resolve en IPv4 pour SMB
- Ajout config HDMI dans `config.txt` (`hdmi_force_hotplug=1`, `hdmi_drive=2`)
- Vérification post-reboot : tous les services (smbd, nmbd, avahi, monitor) démarrent automatiquement
- Clavier console : étendu à `1-5` (5 services)

### v1.1 — 12 avril 2026
- Correction de `monitor.service` : pointe sur `web_monitor.py` au lieu de `monitor.py`
- Mise à jour de `KNOWN_SERVICES` : `hcautomation`, `budget-web`, `budget-bot`, `jeffrey`, `monitor`
- Déploiement initial du service sur FSA-PI5

### v1.0 — 11 avril 2026
- Version initiale</content>
<parameter name="filePath">/Users/francoissalazar/Documents/01-PERSO DRIVE/13-PROJECTS/01-DEVELOPPEMENT/prj-raspberry/README.md