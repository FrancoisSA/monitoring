# Pi Monitor — Manuel Utilisateur

**Version :** 1.2  
**Date :** 13 avril 2026  
**Auteur :** François Salazar  
**Accès :** http://FSA-PI5.local:9090

---

## Présentation

Pi Monitor est un tableau de bord de surveillance pour Raspberry Pi 5. Il offre une interface web accessible depuis n'importe quel navigateur sur le réseau local, ainsi qu'une interface console pour une utilisation directe sur le Pi.

---

## Accès

| Interface | URL |
|-----------|-----|
| Dashboard web | http://FSA-PI5.local:9090 |
| Dashboard web (IP Fixe) | http://10.0.0.2:9090 |
| Page de diagnostic | http://FSA-PI5.local:9090/diag |

**SSH (depuis le Mac) :**
```bash
ssh -i ~/.ssh/id_ed25519 fsalazar@FSA-PI5.local
# ou via IP si le nom ne résout pas :
ssh -i ~/.ssh/id_ed25519 fsalazar@192.168.1.60
```

---

## Interface Web — Onglets

### Vue d'ensemble
Métriques système en temps réel :
- **CPU** : pourcentage d'utilisation + température (°C)
- **RAM** : mémoire utilisée / totale (Mo)
- **Uptime** : durée depuis le dernier démarrage
- **Disques** : espace utilisé/libre par partition
- **I/O** : débits disque (sda) et réseau (eth0) en MB/s
- **Serveurs HTTP** : statut et latence des services web détectés

### Processus
Top 10 des processus les plus gourmands en CPU, avec leur consommation mémoire.

### Services
Liste des 5 services systemd surveillés :

| Touche | Service | Description |
|--------|---------|-------------|
| 1 | hcautomation | HC Automation (port 3141) |
| 2 | budget-web | Budget Web (port 5000) |
| 3 | budget-bot | Budget Bot (Telegram) |
| 4 | jeffrey | Jeffrey (Telegram) |
| 5 | monitor | Pi Monitor (port 9090) |

Actions disponibles sur chaque service : **Démarrer**, **Arrêter**, **Redémarrer**.

### Tension
- Tension cœur actuelle (Volts)
- Alertes de sous-tension et throttling
- Graphique sparkline de l'historique récent
- Journal des événements de sous-tension

### WiFi
Surveillance des réseaux WiFi visibles via nmcli :
- Liste des réseaux avec signal (%), bande (2.4/5 GHz), sécurité
- Bouton **Surveiller** : sélectionne un SSID pour le monitoring de signal
- Panneau de monitoring : signal actuel, historique 30 min, ping gateway
- **Alerte automatique** si le signal chute de plus de 20 points

> Note : le Pi fonctionne en filaire (eth0). Le scan WiFi utilise le cache NetworkManager (toutes les 30s).

### Partages
Liste des partages Samba configurés avec liens cliquables pour le Finder macOS :
- **TimeMachine** → `/mnt/timecapsule` (backup Time Machine)
- **fsalazar** → `/home/fsalazar` (dossier personnel)

Connexion depuis le Finder : `smb://192.168.1.60` ou `smb://FSA-PI5.local`

### Analyse disque
Sélectionner un point de montage pour analyser l'espace occupé par dossier (3 niveaux de profondeur).

---

## Bouton Température (ON/OFF)

Le bouton **Température** dans la barre d'en-tête active ou désactive la collecte de la température CPU côté serveur. Utile pour réduire la charge si le capteur pose problème.

---

## Interface Console (monitor.py)

Lancer depuis le Pi :
```bash
cd ~/03-monitor
source venv/bin/activate
python monitor.py
```

### Raccourcis clavier

| Touche | Action |
|--------|--------|
| `1`–`5` | Sélectionner un service |
| `r` | Redémarrer le service sélectionné |
| `a` | Démarrer le service sélectionné |
| `x` | Arrêter le service sélectionné |
| `f` | Afficher/masquer les partages SMB |
| `c` | Afficher/masquer le Top CPU |
| `t` | Ouvrir un terminal interactif |
| `s` | Arrêter le système (confirmation requise) |
| `q` | Quitter |

---

## Time Capsule (sauvegarde macOS)

Le Pi est configuré comme serveur de sauvegarde Time Machine.

**Disque :** `/dev/sda1` — 916 Go ext4, monté sur `/mnt/timecapsule`  
**Utilisateur Samba :** `timemachine`

**Configurer Time Machine sur macOS :**
1. Préférences Système → Time Machine → Sélectionner le disque
2. Le Pi apparaît sous le nom `FSA-PI5` via Bonjour
3. Login : `timemachine` + mot de passe défini lors de l'installation
4. Lancer la première sauvegarde

**Scripts disponibles sur le Pi (`~/03-monitor/`) :**

| Script | Usage |
|--------|-------|
| `sudo ~/03-monitor/samba-start.sh` | Vérifie et démarre Samba + Avahi |
| `sudo ~/03-monitor/verify-timecapsule.sh` | Vérification complète |
| `sudo ~/03-monitor/check-samba.sh` | Vérification rapide |

---

## Affichage écran (HDMI)

Le Pi est configuré pour forcer le signal HDMI même sans écran branché au démarrage (`hdmi_force_hotplug=1`).

- Brancher sur le port **HDMI0** (le plus proche du connecteur USB-C d'alimentation)
- L'écran doit être branché **avant** la mise sous tension pour être détecté

---

## Déploiement (depuis le Mac)

```bash
cd "/Users/francoissalazar/Documents/01-PERSO DRIVE/13-PROJECTS/01-DEVELOPPEMENT/prj-raspberry"

# 1. Synchroniser les fichiers
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  -e "ssh -i ~/.ssh/id_ed25519 -o ServerAliveInterval=10" \
  ./ fsalazar@FSA-PI5.local:/home/fsalazar/03-monitor/

# 2. Redémarrer le service
ssh -i ~/.ssh/id_ed25519 fsalazar@FSA-PI5.local "sudo systemctl restart monitor"

# 3. Vérifier les logs
ssh -i ~/.ssh/id_ed25519 fsalazar@FSA-PI5.local "sudo journalctl -u monitor -n 20 --no-pager"
```

---

## Dépannage

### Dashboard inaccessible
```bash
ssh -i ~/.ssh/id_ed25519 fsalazar@192.168.1.60
sudo systemctl status monitor
sudo journalctl -u monitor -n 30 --no-pager
```

### Samba ne répond pas
```bash
sudo ~/03-monitor/samba-start.sh
```

### Disque Time Capsule non monté
```bash
sudo mount /dev/sda1 /mnt/timecapsule
df -h /mnt/timecapsule
```

### `FSA-PI5.local` ne résout pas (Mac)
```bash
# Vider le cache mDNS
sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder
# Ou utiliser l'IP directe
smb://192.168.1.60
```

---

## Changelog

### v1.2 — 13 avril 2026
- Refactorisation en modules Python séparés (9 fichiers)
- Monitoring WiFi : sélection SSID, historique signal, alerte chute
- Correction toggle température (bouton ON/OFF dashboard)
- Nouveau script `samba-start.sh` : vérification + démarrage automatique Samba
- Correction `setup-timecapsule-pi5.sh` : gestion du disque déjà monté
- Correctif Avahi IPv6 (`use-ipv6=no`) pour connexion SMB via nom d'hôte
- Affichage HDMI forcé (`hdmi_force_hotplug=1`, `hdmi_drive=2`)
- Vérification post-reboot : tous les services démarrent automatiquement
- Interface console : navigation étendue à 5 services (touches 1–5)

### v1.1 — 12 avril 2026
- Correction `monitor.service` : pointe sur `web_monitor.py`
- Mise à jour `KNOWN_SERVICES` avec les 5 services réels du Pi
- Déploiement initial sur FSA-PI5

### v1.0 — 11 avril 2026
- Version initiale
