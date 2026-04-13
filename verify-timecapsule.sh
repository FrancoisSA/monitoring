#!/bin/bash

# Script de vérification pour la configuration Time Capsule sur Raspberry Pi
# Vérifie les services, les configurations et les permissions

echo "=== Vérification de la configuration Time Capsule ==="
echo ""

# 1. Vérifier que Samba et Avahi sont installés
echo "1. Vérification des packages installés..."
if dpkg -l | grep -q samba && dpkg -l | grep -q avahi-daemon; then
    echo "   ✅ Samba et Avahi sont installés"
else
    echo "   ❌ Samba ou Avahi non installé"
fi
echo ""

# 2. Vérifier que les services sont actifs
echo "2. Vérification des services..."
if systemctl is-active --quiet smbd && systemctl is-active --quiet avahi-daemon; then
    echo "   ✅ Services Samba et Avahi sont actifs"
else
    echo "   ❌ Services non actifs"
    systemctl status smbd --no-pager | grep -E "Active|Loaded"
    systemctl status avahi-daemon --no-pager | grep -E "Active|Loaded"
fi
echo ""

# 3. Vérifier le montage du disque Time Capsule
echo "3. Vérification du montage du disque..."
if mount | grep -q "/mnt/timecapsule"; then
    echo "   ✅ Disque monté sur /mnt/timecapsule"
else
    echo "   ❌ Disque non monté"
fi
echo ""

# 4. Vérifier les permissions du dossier Time Capsule
echo "4. Vérification des permissions..."
if [ -d "/mnt/timecapsule" ]; then
    owner=$(stat -c "%U" /mnt/timecapsule)
    group=$(stat -c "%G" /mnt/timecapsule)
    perms=$(stat -c "%A" /mnt/timecapsule)
    
    if [ "$owner" = "timemachine" ] && [ "$group" = "timemachine" ]; then
        echo "   ✅ Propriétaire et groupe corrects : timemachine"
    else
        echo "   ❌ Propriétaire ou groupe incorrect : $owner:$group"
    fi
    
    if [ "$perms" = "drwxrwx---" ]; then
        echo "   ✅ Permissions correctes : $perms"
    else
        echo "   ❌ Permissions incorrectes : $perms"
    fi
else
    echo "   ❌ Dossier /mnt/timecapsule non trouvé"
fi
echo ""

# 5. Vérifier la configuration Samba
echo "5. Vérification de la configuration Samba..."
if grep -q "fruit:time machine = yes" /etc/samba/smb.conf; then
    echo "   ✅ Configuration Time Machine trouvée dans smb.conf"
else
    echo "   ❌ Configuration Time Machine non trouvée"
fi
echo ""

# 6. Vérifier la configuration Avahi
echo "6. Vérification de la configuration Avahi..."
if [ -f "/etc/avahi/services/timemachine.service" ]; then
    echo "   ✅ Fichier de service Avahi trouvé"
    if grep -q "_adisk._tcp" /etc/avahi/services/timemachine.service; then
        echo "   ✅ Configuration _adisk._tcp présente"
    else
        echo "   ❌ Configuration _adisk._tcp manquante"
    fi
else
    echo "   ❌ Fichier de service Avahi non trouvé"
fi
echo ""

# 7. Vérifier la connectivité réseau
echo "7. Vérification de la connectivité réseau..."
if ping -c 1 google.com &> /dev/null; then
    echo "   ✅ Connexion Internet OK"
else
    echo "   ❌ Pas de connexion Internet"
fi

if ip a | grep -q "eth0"; then
    echo "   ✅ Interface Ethernet détectée"
else
    echo "   ❌ Interface Ethernet non détectée"
fi
echo ""

# 8. Vérifier les logs pour erreurs récentes
echo "8. Vérification des logs..."
errors_samba=$(journalctl -u smbd --since "1 hour ago" | grep -i "error" | wc -l)
errors_avahi=$(journalctl -u avahi-daemon --since "1 hour ago" | grep -i "error" | wc -l)

if [ "$errors_samba" -eq 0 ]; then
    echo "   ✅ Aucun erreur récente dans les logs Samba"
else
    echo "   ❌ $errors_samba erreur(s) dans les logs Samba"
fi

if [ "$errors_avahi" -eq 0 ]; then
    echo "   ✅ Aucun erreur récente dans les logs Avahi"
else
    echo "   ❌ $errors_avahi erreur(s) dans les logs Avahi"
fi
echo ""

echo "=== Fin de la vérification ==="
