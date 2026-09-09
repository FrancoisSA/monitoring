# Structure du projet prj-raspberry

Ce document décrit l'organisation générale du projet **prj-raspberry**, qui regroupe plusieurs sous-projets pour la gestion et le monitoring d'un Raspberry Pi.

---

## 📁 Structure globale

```
prj-raspberry/
├── .secrets/                    # 📁 Secrets non versionnés (dossier générique)
├── .claude/                     # 📁 Config locale Claude (à supprimer ou déplacer)
├── .git/                        # Git repository
├── .gitignore                   # Fichiers exclus du versionning
├── AGENTS.md                    # 📄 Instructions pour les agents IA
├── CLAUDE.md                    # 📄 Documentation spécifique à Claude
├── Hermes/                      # 📁 Analyse Hermes (exclu du versionning)
├── Monitor/                     # 📦 Projet Pi Monitor principal
│   ├── src/                     # 💻 Code source Python
│   │   └── *.py                 # Modules Python (config, dashboard, etc.)
│   ├── scripts/                 # 🛠️ Scripts systemd et déploiement
│   │   ├── collect_services.sh  # Collecte l'état des services (génère system_state.md et services_state.json)
│   │   ├── deploy_custom.sh     # Déploiement personnalisé via rsync
│   │   ├── deploy_from_mac.sh   # Déploiement depuis Mac via SCP
│   │   └── monitor.service      # Service systemd pour démarrage automatique de web_monitor.py
│   ├── docs/                    # 📖 Documentation spécifique au projet Monitor
│   │   └── STRUCTURE.md         # Structure du projet prj-raspberry (copie locale)
│   ├── .gitkeep                 # Garde le dossier dans git (vide, futur usage)
│   └── requirements.txt         # Dépendances Python
├── TimeCapsule/                 # 📦 Setup Time Capsule (Samba + Avahi)
│   ├── setup-timecapsule-pi5.sh # 🚀 Script d'installation complet (6 étapes)
│   ├── setup-timecapsule-pi5.md # 📖 Documentation pas-à-pas
│   ├── verify-timecapsule.sh    # ✅ Vérification complète de la configuration
│   └── check-samba.sh           # 🔍 Vérification rapide Samba + Time Machine
├── scripts/                    # 🛠️ Scripts système (duplicat, à supprimer)
└── deploy_*.sh                 # 🛠️ Scripts de déploiement (à la racine, à supprimer)
```

---

## 📦 Sous-projets

### 1. **Monitor** — Dashboard de surveillance Raspberry Pi

Projet principal pour surveiller les métriques système d'un Raspberry Pi via une interface web et console.

#### Structure de Monitor
```
Monitor/
├── src/                          # Code source Python
│   ├── __init__.py              # Package marker
│   ├── config.py                # Constantes et chargement config.json
│   ├── dashboard.py             # Template HTML du dashboard (1157+ lignes)
│   ├── disk.py                  # Analyse récursive de dossiers
│   ├── network.py               # HTTP check, scan WiFi, ping gateway
│   ├── services.py              # Services systemd, Samba
│   ├── state.py                 # État global + thread de collecte (457+ lignes)
│   ├── system.py                # CPU, RAM, température, uptime (système)
│   ├── voltage.py               # Tension cœur + VoltageHistory (58+ lignes)
│   └── web_monitor.py           # Point d'entrée Flask + routes API (276+ lignes)
│
├── scripts/                      # Scripts systemd et déploiement
│   ├── collect_services.sh      # Collecte l'état des services (génère system_state.md et services_state.json)
│   ├── deploy_custom.sh         # Déploiement personnalisé via rsync
│   ├── deploy_from_mac.sh       # Déploiement depuis Mac via SCP
│   └── monitor.service          # Service systemd pour démarrage automatique de web_monitor.py
│
├── docs/                         # Documentation spécifique au projet Monitor
│   └── STRUCTURE.md             # Structure du projet prj-raspberry (copie locale)
│
├── .gitkeep                      # Garde le dossier dans git (vide, futur usage)
├── configs/                      # ⚙️ Configs spécifiques à Monitor (vide, futur usage)
├── static/                       # 🖼️ Assets statiques (CSS, JS, images - futur usage)
└── templates/                    # 📄 Templates HTML (futur, actuellement inline dans dashboard.py)
```

#### Fonctionnalités de Monitor
- **Interface web** : Dashboard Flask accessible via navigateur local (`http://FSA-PI5.local:9090`)
- **Interface console** : Interface interactive en terminal (Rich)
- **Métriques surveillées** :
  - CPU, RAM, température, uptime (système)
  - État des services systemd et Samba
  - Serveurs HTTP détectés, ping gateway, scan WiFi (réseau)
  - Tension cœur et historique des événements de sous-tension (énergie)
  - Analyse de l'espace disque par dossier (stockage)

#### API REST (Flask)
| Endpoint | Méthode | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML principal |
| `/api/stats` | GET | Toutes les métriques système en JSON |
| `/api/service/<name>/<action>` | POST | start/stop/restart service |
| `/api/temperature/<on\|off>` | POST | Toggle collecte température |
| `/api/wifi/monitor` | POST | Sélectionner SSID à surveiller |
| `/api/scan/<path>` | GET | Analyse taille dossiers récursive |

#### Dépendances
- Python 3.8+
- Flask >= 3.0.0
- psutil >= 5.9.0
- requests >= 2.31.0
- rich >= 13.0.0

---

### 2. **TimeCapsule** — Setup Time Machine pour macOS

Scripts et documentation pour transformer un Raspberry Pi en serveur de sauvegarde Time Machine compatible avec macOS.

#### Structure de TimeCapsule
```
TimeCapsule/
├── setup-timecapsule-pi5.sh     # 🚀 Script d'installation complet (6 étapes)
├── setup-timecapsule-pi5.md     # 📖 Documentation pas-à-pas
├── verify-timecapsule.sh        # ✅ Vérification complète de la configuration
└── check-samba.sh               # 🔍 Vérification rapide Samba + Time Machine
```

#### Fonctionnalités de TimeCapsule
- **Formatage** du disque externe en ext4
- **Création** de l'utilisateur `timemachine`
- **Configuration Samba** avec support Time Machine (`fruit:time machine = yes`)
- **Modèle annoncé** : `TimeCapsule8,119` (compatible macOS)
- **Configuration Avahi** pour la découverte Bonjour (_adisk._tcp)
- **Quota automatique** : purge des anciennes sauvegardes quand le quota est atteint

#### Configuration Samba (extrait)
```ini
[TimeMachine]
   comment = Time Machine Backup
   path = /mnt/timecapsule
   browseable = yes
   writeable = yes
   valid users = timemachine
   fruit:time machine = yes
   fruit:time machine max size = 850G  # Quota (modifiable)
   fruit:metadata = stream
   fruit:model = TimeCapsule8,119
   vfs objects = catia fruit streams_xattr
```

#### Points importants
- **Disque** : `/dev/sda1` (ou autre) monté sur `/mnt/timecapsule`
- **Utilisateur** : `timemachine` avec mot de passe stocké dans `.secrets/SECRETS.local.md`
- **Réseau** : IP statique recommandée (évite les problèmes après changement de routeur)
- **IPv6** : `use-ipv6=no` dans Avahi pour éviter les conflits avec macOS

---

## 📂 Organisation des dossiers

### Dossiers versionnés (à commiter)
| Dossier | Contenu | À versionner ? |
|---------|---------|---------------|
| `Monitor/` | Code source, scripts, docs du projet Monitor | ✅ Oui |
| `.secrets/` | Secrets non versionnés (mot de passe, clés) | ⚠️ Non (gitignore) |
| `TimeCapsule/` | Scripts de setup Time Capsule | ⚠️ Optionnel (config spécifique au Pi) |
| `AGENTS.md` | Instructions pour les agents IA | ✅ Oui |
| `CLAUDE.md` | Documentation spécifique à Claude | ✅ Oui |
| `.gitignore` | Fichiers exclus du versionning | ✅ Oui (fichier lui-même) |

### Dossiers exclus du versionning
| Dossier | Raison |
|---------|--------|
| `.claude/` | Config locale de Claude (personnelle) |
| `Hermes/` | Analyse temporaire d'Hermes |
| `.DS_Store`, `.AppleDouble` | Fichiers système macOS |
| `*.local.md` | Notes locales non versionnées |

---

## 🛠️ Scripts de déploiement

### `deploy_from_mac.sh`
Déploie les fichiers modifiés depuis un Mac vers le Raspberry Pi via SCP.

```bash
cd Monitor/scripts/
./deploy_from_mac.sh
```

### `deploy_custom.sh`
Déploie vers une configuration SSH personnalisée via rsync.

```bash
cd Monitor/scripts/
./deploy_custom.sh
# Modifier les variables PI_USER, PI_HOST, PI_DEST au début du script si nécessaire
```

### Workflow de déploiement recommandé
1. Modifier les fichiers source dans `Monitor/src/`
2. Lancer un script de déploiement (`deploy_from_mac.sh` ou `deploy_custom.sh`)
3. Vérifier les logs sur le Pi : `journalctl -u monitor -n 20 --no-pager`
4. Redémarrer le service si nécessaire : `systemctl restart monitor`

---

## 🔐 Gestion des secrets

Les fichiers contenant des données sensibles sont stockés dans `.secrets/` et exclus du versionning :

- `SECRETS.local.md` : Indices de mots de passe, clés API
- `credentials.json` : Credentials (à déplacer ici si nécessaire)

**Règle d'or** : Ne jamais commiter de secrets dans le repository !

---

## 📝 Conventions de nommage

### Dossiers
- `Monitor/` : Projet principal (nom en PascalCase)
- `TimeCapsule/` : Sous-projet Time Capsule (nom en PascalCase)
- `scripts/`, `src/`, `docs/` : Dossiers génériques (nom en minuscule)

### Fichiers
- `*.py` : Modules Python (nom en minuscule, séparés par `_`)
- `*.sh` : Scripts shell (nom en minuscule, séparés par `_`)
- `*.md` : Documentation (nom descriptif en minuscule)
- `setup-*`, `verify-*`, `check-*` : Scripts de setup/verification (préfixe)
- `deploy_*` : Scripts de déploiement (préfixe)

---

## 🔄 Flux de travail recommandé

1. **Développement** :
   - Modifier le code dans `Monitor/src/`
   - Tester localement (ou sur un Pi de test)

2. **Documentation** :
   - Mettre à jour `Monitor/Pi Monitor vX.Y.md` avec les changements
   - Ajouter des exemples d'utilisation

3. **Déploiement** :
   - Lancer un script de déploiement (`deploy_from_mac.sh` ou `deploy_custom.sh`)
   - Vérifier les logs sur le Pi

4. **Versionning** :
   - Commiter les changements dans Git
   - Mettre à jour le numéro de version dans `Pi Monitor vX.Y.md`

5. **Maintenance** :
   - Utiliser les scripts de vérification (`verify-timecapsule.sh`, `check-samba.sh`)
   - Surveiller les logs : `journalctl -u monitor`

---

## 📊 Résumé par projet

| Projet | Dossiers principaux | Fichiers clés | Usage principal |
|--------|-------------------|---------------|-----------------|
| **Monitor** | `src/`, `scripts/` | `web_monitor.py`, `state.py`, `dashboard.py`, `collect_services.sh` | Dashboard de surveillance Raspberry Pi |
| **TimeCapsule** | `TimeCapsule/` | `setup-timecapsule-pi5.sh`, `verify-timecapsule.sh` | Setup Time Machine pour macOS |

---

*Document généré automatiquement à partir de la structure du projet.*