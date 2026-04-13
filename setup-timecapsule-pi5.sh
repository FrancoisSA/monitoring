#!/bin/bash

# Script autonome pour configurer un Raspberry Pi 5 en Time Capsule avec Samba + Avahi
# sudo ./setup-timecapsule-pi5.sh
# Objectif : Transformer le Raspberry Pi 5 en serveur de sauvegarde Time Machine pour macOS
# Auteur : François Salazar
# Date : 2026-04-03

# Vérification des droits root
if [ "$(id -u)" -ne 0 ]; then
    echo "Ce script doit être exécuté en tant que root. Utilisez 'sudo'."
    exit 1
fi

# Fonction pour afficher un message d'erreur et quitter
function error_exit {
    echo "[ERREUR] $1" >&2
    exit 1
}

# Fonction pour afficher un message d'information
function info {
    echo "[INFO] $1"
}

# Fonction pour vérifier l'exécution d'une commande
function check_command {
    if [ $? -ne 0 ]; then
        error_exit "La commande '$1' a échoué."
    fi
}

# Étape 1 : Préparer le système
info "Étape 1/6 : Préparation du système..."
apt update && apt upgrade -y
check_command "apt update && apt upgrade -y"

apt install samba avahi-daemon -y
check_command "apt install samba avahi-daemon -y"

systemctl status smbd > /dev/null 2>&1
check_command "systemctl status smbd"

systemctl status avahi-daemon > /dev/null 2>&1
check_command "systemctl status avahi-daemon"

info "Le système est prêt."

# Étape 2 : Préparer le disque externe
info "Étape 2/6 : Préparation du disque externe..."

# Identifier le disque
info "Liste des disques disponibles :"
lsblk

read -p "Entrez le périphérique du disque (ex: /dev/sda1) : " DISK_DEVICE

# Formater le disque en ext4 (si nécessaire)
read -p "Voulez-vous formater le disque en ext4 ? (o/n) " FORMAT_DISK
if [ "$FORMAT_DISK" = "o" ]; then
    read -p "ATTENTION : Cela effacera toutes les données. Continuer ? (o/n) " CONFIRM_FORMAT
    if [ "$CONFIRM_FORMAT" = "o" ]; then
        mkfs.ext4 "$DISK_DEVICE"
        check_command "mkfs.ext4 $DISK_DEVICE"
    fi
fi

# Créer le point de montage et monter le disque (si pas déjà monté)
mkdir -p /mnt/timecapsule
if mountpoint -q /mnt/timecapsule; then
    info "Disque déjà monté sur /mnt/timecapsule — skip"
else
    mount "$DISK_DEVICE" /mnt/timecapsule
    check_command "mount $DISK_DEVICE /mnt/timecapsule"
fi

# Vérifier le montage
df -h | grep timecapsule

# Récupérer l'UUID du disque
UUID=$(blkid "$DISK_DEVICE" -s UUID -o value)
check_command "blkid $DISK_DEVICE -s UUID -o value"

# Ajouter l'entrée dans /etc/fstab (seulement si absente)
if grep -q "$UUID" /etc/fstab; then
    info "Entrée fstab déjà présente pour UUID=$UUID — skip"
else
    echo "UUID=$UUID  /mnt/timecapsule  ext4  defaults,nofail  0  2" >> /etc/fstab
    check_command "echo UUID dans fstab"
fi

# Tester le montage automatique (seulement si pas déjà monté)
if ! mountpoint -q /mnt/timecapsule; then
    mount -a
    check_command "mount -a"
fi

info "Le disque externe est prêt."

# Étape 3 : Créer l'utilisateur Samba
info "Étape 3/6 : Création de l'utilisateur Samba..."

# Créer un utilisateur système dédié
adduser --no-create-home --shell /usr/sbin/nologin timemachine
check_command "adduser --no-create-home --shell /usr/sbin/nologin timemachine"

# Définir le mot de passe Samba
read -s -p "Entrez le mot de passe pour l'utilisateur 'timemachine' : " SAMBA_PASSWORD
echo
(smbpasswd -a timemachine) <<EOF
$SAMBA_PASSWORD
$SAMBA_PASSWORD
EOF
check_command "smbpasswd -a timemachine"

# Donner les droits sur le dossier de backup
chown -R timemachine:timemachine /mnt/timecapsule
chmod 770 /mnt/timecapsule
check_command "chown -R timemachine:timemachine /mnt/timecapsule && chmod 770 /mnt/timecapsule"

# Vérifier les droits
ls -ld /mnt/timecapsule

info "L'utilisateur Samba est configuré."

# Étape 4 : Configurer Samba
info "Étape 4/6 : Configuration de Samba..."

# Sauvegarder la configuration actuelle
cp /etc/samba/smb.conf /etc/samba/smb.conf.bak

# Créer la nouvelle configuration
cat > /etc/samba/smb.conf <<EOF
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
   fruit:time machine max size = 500G
EOF

# Tester la configuration
testparm
check_command "testparm"

# Redémarrer les services Samba
systemctl restart smbd nmbd
check_command "systemctl restart smbd nmbd"

# Vérifier le service Samba
systemctl status smbd > /dev/null 2>&1
check_command "systemctl status smbd"

info "Samba est configuré."

# Étape 5 : Configurer Avahi (découverte Bonjour)
info "Étape 5/6 : Configuration d'Avahi..."

# Créer le fichier de service Avahi
cat > /etc/avahi/services/timemachine.service <<EOF
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
EOF

# Redémarrer Avahi
systemctl restart avahi-daemon
check_command "systemctl restart avahi-daemon"

# Vérifier le service Avahi
systemctl status avahi-daemon > /dev/null 2>&1
check_command "systemctl status avahi-daemon"

info "Avahi est configuré."

# Étape 6 : Instructions pour configurer Time Machine sur macOS
info "Étape 6/6 : Configuration de Time Machine sur macOS..."
info "1. Ouvrir 'Préférences Système → Time Machine'."
info "2. Cliquer sur 'Sélectionner le disque...'."
info "3. Le Raspberry Pi devrait apparaître automatiquement sous son nom d'hôte."
info "4. Se connecter avec l'utilisateur 'timemachine' et le mot de passe défini précédemment."
info "5. Lancer la première sauvegarde."

# Vérification finale
info "Vérification finale..."
smbstatus

info "Configuration terminée avec succès !"
info "Le Raspberry Pi 5 est maintenant prêt à être utilisé comme Time Capsule."
