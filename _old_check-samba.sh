#!/bin/bash

# Script de vérification rapide pour Samba et Time Capsule
echo "=== Vérification Samba et Time Capsule ==="
echo ""

# 1. Vérifier si Samba est installé
echo "1. Vérification de l'installation de Samba..."
if dpkg -l | grep -q samba; then
    echo "   ✅ Samba est installé"
else
    echo "   ❌ Samba n'est pas installé"
fi
echo ""

# 2. Vérifier si le service Samba est actif
echo "2. Vérification du service Samba..."
if systemctl is-active --quiet smbd; then
    echo "   ✅ Service Samba (smbd) est actif"
else
    echo "   ❌ Service Samba (smbd) n'est pas actif"
fi
echo ""

# 3. Lister les utilisateurs Samba
echo "3. Utilisateurs Samba configurés..."
sudo pdbedit -L | grep -v "^$" | while read user; do
    echo "   - $user"
done
echo ""

# 4. Lister les partages Samba
echo "4. Partages Samba disponibles..."
smbclient -L localhost -U% 2>/dev/null | grep "Disk\|IPC" | awk '{print "   - " $1}'
echo ""

# 5. Vérifier les points de montage
echo "5. Points de montage..."
df -h | grep -v tmpfs | grep -v udev | while read line; do
    echo "   $line"
done
echo ""

# 6. Vérifier les permissions du dossier TimeMachine
echo "6. Permissions du dossier TimeMachine..."
if [ -d "/mnt/timecapsule" ]; then
    owner=$(stat -c "%U" /mnt/timecapsule)
    group=$(stat -c "%G" /mnt/timecapsule)
    perms=$(stat -c "%A" /mnt/timecapsule)
    echo "   Propriétaire : $owner:$group"
    echo "   Permissions : $perms"
else
    echo "   ❌ Dossier /mnt/timecapsule non trouvé"
fi
echo ""

echo "=== Fin de la vérification ==="
