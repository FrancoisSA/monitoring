# État des Services — Pi Monitor

**Date de génération :** 2026-08-23 19:32:04  
**Date d'acquisition :** 23/08 2026 19:32  
**Utilisateur :** fsalazar  
**Machine :** FSA-PI5.local

---

## 📊 Résumé des services

| Service | Statut | Depuis | Port |
|---------|--------|-------|------|
| ✅ hcautomation | active | Tue 2026-08-11 04:37:46 CEST | 🔌 |
| ✅ budget-web | active | Tue 2026-08-11 04:37:50 CEST | 🔌 |
| ✅ budget-bot | active | Tue 2026-08-11 04:37:50 CEST |  |
| ❌ jeffrey | inactive |  |  |
| ✅ monitor | active | Tue 2026-08-11 04:37:46 CEST | 🔌 |

---

## 📋 Détails des services

### 1. hcautomation
- **Service :** `hcautomation`
- **Statut :** active
- **Démarré le :** Tue 2026-08-11 04:37:46 CEST
- **Port :** 🔌hcautomation

### 2. budget-web
- **Service :** `budget-web`
- **Statut :** active
- **Démarré le :** Tue 2026-08-11 04:37:50 CEST
- **Port :** 🔌budget-web

### 3. budget-bot
- **Service :** `budget-bot`
- **Statut :** active
- **Démarré le :** Tue 2026-08-11 04:37:50 CEST
- **Port :** budget-bot

### 4. jeffrey
- **Service :** `jeffrey`
- **Statut :** inactive
- **Démarré le :** 
- **Port :** jeffrey

### 5. monitor
- **Service :** `monitor`
- **Statut :** active
- **Démarré le :** Tue 2026-08-11 04:37:46 CEST
- **Port :** 🔌monitor

---

## 📊 Résumé

- **Services actifs :** 4/5
- **Services en échec :** 0
- **Services inactifs :** 1/5
- **Erreurs :** 0/5

---

## 🛠️ Commandes utiles

### Vérifier l'état d'un service
```bash
systemctl status <service>
# Exemple : systemctl status monitor
```

### Redémarrer un service
```bash
systemctl restart <service>
# Exemple : systemctl restart monitor
```

### Arrêter un service
```bash
systemctl stop <service>
# Exemple : systemctl stop monitor
```

### Voir les logs d'un service
```bash
journalctl -u <service> -n 50 --no-pager
# Exemple : journalctl -u monitor -n 50 --no-pager
```

### Vérifier les services Samba (Time Capsule)
```bash
systemctl is-active smbd nmbd avahi-daemon
```

---

## 📝 Notes de maintenance

- **Dernière mise à jour :** ________________
- **Problèmes rencontrés :** _______________________________________
- **Actions entreprises :** _______________________________________

---

*Généré automatiquement par le script de collecte d'état des services.*
