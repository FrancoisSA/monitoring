# Raspberry Pi 5 — Time Capsule avec Samba + Avahi

**Objectif :** Transformer le Raspberry Pi 5 en serveur de sauvegarde Time Machine pour macOS, sans réinstaller l'OS.  
**Protocole choisi :** SMB3 via Samba + découverte automatique via Avahi (Bonjour)  
**Date de démarrage :** 2026-04-03

---

## Contexte & choix technique

| **Samba + Avahi** ✅ | SMB3 | ★★★★★ | Non | Excellente | Oui (Bonjour) |


**Raisons du choix Samba + Avahi :**
- Pas de compilation requise
- Compatible macOS Ventura/Sonoma/Sequoia
- Fonctionne avec ext4 (pas besoin de reformater en HFS+)
- Le Pi apparaît comme une vraie Time Capsule dans le Finder

---

## Prérequis matériels

- [ ] Raspberry Pi 5 branché en **Ethernet** (pas Wi-Fi)
- [ ] Disque USB 3.0 externe (minimum 2x la taille du Mac à sauvegarder)
- [ ] Alimentation stable (officielle Pi 5 27W recommandée)
- [ ] Raspberry Pi OS installé et à jour

---

## Étape 1 — Préparer le système

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install samba avahi-daemon -y
```

Vérifier que Samba tourne :
```bash
sudo systemctl status smbd
```

**Vérification supplémentaire :**
```bash
sudo systemctl status avahi-daemon
```

---

## Étape 2 — Préparer le disque externe

### Identifier le disque
```bash
lsblk
# ou
sudo fdisk -l
```

### Formater en ext4 (si nécessaire)
> ⚠️ Efface toutes les données sur le disque

```bash
sudo mkfs.ext4 /dev/sda1   # adapter selon lsblk
```

### Créer le point de montage et monter le disque
```bash
sudo mkdir -p /mnt/timecapsule
sudo mount /dev/sda1 /mnt/timecapsule
```

### Vérifier le montage
```bash
df -h | grep timecapsule
```

### Montage automatique au démarrage (fstab)
Récupérer l'UUID du disque :
```bash
sudo blkid /dev/sda1
```

Ajouter dans `/etc/fstab` :
```
UUID=XXXX-XXXX  /mnt/timecapsule  ext4  defaults,nofail  0  2
```

**Tester le montage automatique :**
```bash
sudo mount -a
```

---

## Étape 3 — Créer l'utilisateur Samba

```bash
# Créer un utilisateur système dédié (sans login shell)
sudo adduser --no-create-home --shell /usr/sbin/nologin timemachine

# Définir le mot de passe Samba pour cet utilisateur
sudo smbpasswd -a timemachine

# Donner les droits sur le dossier de backup
sudo chown -R timemachine:timemachine /mnt/timecapsule
sudo chmod 770 /mnt/timecapsule
```

**Vérification des droits :**
```bash
ls -ld /mnt/timecapsule
```

---

## Étape 4 — Configurer Samba

Éditer `/etc/samba/smb.conf` :

```ini
[global]
   server role = standalone server
   dns proxy = no

   # Support macOS (Time Machine)
   fruit:metadata = stream
   fruit:model = TimeCapsule8,119
   fruit:posix_rename = yes
   fruit:veto_appledouble = no
   fruit:wipe_intentionally_left_blank_rfork = yes
   fruit:delete_empty_adfiles = yes
   vfs objects = catia fruit streams_xattr

[TimeMachine]
   comment = Time Machine Backup
   path = /mnt/timecapsule
   browseable = yes
   writeable = yes
   create mask = 0600
   directory mask = 0700
   valid users = timemachine
   fruit:time machine = yes
   fruit:time machine max size = 500G   # adapter selon ton disque
```

Tester la config et redémarrer :
```bash
testparm
sudo systemctl restart smbd nmbd
```

**Vérification du service :**
```bash
sudo systemctl status smbd
```

---

## Étape 5 — Configurer Avahi (découverte Bonjour)

Créer le fichier `/etc/avahi/services/timemachine.service` :

```xml
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">%h</name>
  <service>
    <type>_smb._tcp</type>
    <port>445</port>
  </service>
  <service>
    <type>_adisk._tcp</type>
    <port>9</port>
    <txt-record>sys=waMa=0,adVF=0x100</txt-record>
    <txt-record>dk0=adVN=TimeMachine,adVF=0x82</txt-record>
  </service>
  <service>
    <type>_device-info._tcp</type>
    <port>0</port>
    <txt-record>model=TimeCapsule8,119</txt-record>
  </service>
</service-group>
```

Redémarrer Avahi :
```bash
sudo systemctl restart avahi-daemon
```

**Vérification d'Avahi :**
```bash
sudo systemctl status avahi-daemon
```

---

## Étape 6 — Configurer Time Machine sur macOS

1. Ouvrir **Préférences Système → Time Machine**
2. Cliquer **Sélectionner le disque...**
3. Le Pi devrait apparaître automatiquement sous son nom d'hôte
4. Se connecter avec : `timemachine` / (mot de passe défini à l'étape 3)
5. Lancer la première sauvegarde

**Vérification de la connexion :**
```bash
sudo smbstatus
```

---

## Vérifications utiles

```bash
# Voir les connexions Samba actives
sudo smbstatus

# Logs Samba
sudo journalctl -u smbd -f

# Vérifier qu'Avahi annonce bien les services
avahi-browse -a
```

---

## Correctifs connus

### Erreur `fuseblk: Bad value for 'source'` lors du setup
Le script `setup-timecapsule-pi5.sh` montait le disque manuellement puis appelait `mount -a`, créant un conflit. **Corrigé le 13/04/2026** : le script vérifie avec `mountpoint -q` avant toute tentative de montage, et ne double pas les entrées fstab.

### Connexion SMB via nom d'hôte (`FSA-PI5.local`) échoue
macOS résolvait `FSA-PI5.local` en IPv6 pour les connexions SMB classiques, mais Samba ne répondait pas sur cette adresse. **Corrigé le 13/04/2026** : `use-ipv6=no` dans `/etc/avahi/avahi-daemon.conf`.
- Time Machine fonctionnait car la découverte Bonjour (`_adisk._tcp`) fournit directement l'adresse IPv4.
- Pour les partages classiques, utiliser l'IP directe : `smb://192.168.1.60`

---

## Statut du projet

| Étape | Statut | Notes |
|---|---|---|
| Choix de la solution | ✅ Fait | Samba + Avahi |
| Préparation système | ✅ Fait | Packages installés et services actifs |
| Préparation disque | ✅ Fait | /dev/sda1 (916 Go ext4) monté sur /mnt/timecapsule |
| Utilisateur Samba | ✅ Fait | Utilisateur timemachine créé et mot de passe défini |
| Config Samba | ✅ Fait | Partages TimeMachine + fsalazar configurés |
| Config Avahi | ✅ Fait | Service Bonjour opérationnel, IPv6 désactivé |
| Démarrage auto | ✅ Vérifié | smbd, nmbd, avahi-daemon enabled + testés post-reboot |
| Config macOS | ⬜ À faire | À configurer sur le Mac |
| Première sauvegarde | ⬜ À faire | À tester |

---

## Journal

| Date | Action |
|---|---|
| 2026-04-03 | Démarrage du projet, choix Samba + Avahi |
| 2026-04-09 | Configuration terminée, disque monté, utilisateur créé, services actifs |
| 2026-04-13 | Correctif mount -a (setup script), correctif Avahi IPv6, vérification post-reboot OK |
