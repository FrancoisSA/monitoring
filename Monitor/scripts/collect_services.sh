#!/bin/bash

# Script pour collecter l'état des services via SSH
# Usage : bash Monitor/scripts/collect_services.sh HOST USER KEY_PATH

echo "🔑 Collecte de l'état des services via SSH"
echo "=========================================="

# Configuration par défaut (modifiable)
HOST="${1:-FSA-PI5.local}"
USER="${2:-fsalazar}"
KEY_PATH="${3:-$HOME/.ssh/id_ed25519}"

echo ""
echo "📋 Configuration :"
echo "  Hôte : $HOST"
echo "  Utilisateur : $USER"
echo "  Clé SSH : $KEY_PATH"
echo ""

# Vérifier la clé SSH
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Erreur : Clé SSH non trouvée ($KEY_PATH)"
    exit 1
fi

echo "✅ Clé SSH trouvée"
echo ""

# Fonction pour exécuter une commande SSH et retourner la sortie complète
ssh_exec() {
    ssh -i "$KEY_PATH" -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=30 "$USER@$HOST" "$1" 2>/dev/null
}

# Services à collecter (seulement hcautomation et monitor)
SERVICES=("hcautomation" "monitor")

echo "📊 Collecte des services..."
echo ""

# Fichiers temporaires pour stocker les résultats
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

for service in "${SERVICES[@]}"; do
    echo "   📊 Service : $service..."
    
    # Obtenir l'état du service avec systemctl show
    output=$(ssh_exec "systemctl show $service --property=ActiveState,ActiveEnterTimestamp 2>/dev/null")
    
    if [ -z "$output" ]; then
        echo "      Statut : ❌ Erreur (sortie vide)"
        echo "      Depuis : —"
    else
        active=""
        since=""
        
        # Extraire ActiveState (première ligne)
        active=$(echo "$output" | head -1 | cut -d= -f2 | tr -d ' ')
        
        # Extraire ActiveEnterTimestamp (deuxième ligne)
        since=$(echo "$output" | tail -1 | cut -d= -f2)
        
        # Formater la date si c'est une date valide
        if [[ "$since" =~ ^[A-Za-z]+ ]]; then
            # C'est une date, la formater
            since=$(echo "$since" | sed 's/^\([A-Za-z]*\) \([0-9]*\)-\([0-9]*\)-\([0-9]*\) \([0-9:]*\)$/\3\/\2 \4 (\1)/')
        fi
        
        echo "      Statut : $active"
        echo "      Depuis : $since"
    fi
    
    # Sauvegarder les résultats dans des fichiers temporaires
    echo "$active" > "$TMP_DIR/${service}_status.txt"
    echo "$since" > "$TMP_DIR/${service}_since.txt"
done

echo ""
echo "=========================================="
echo "📊 Résumé des services :"
echo ""

# Afficher le tableau de résumé en lisant les fichiers temporaires
printf "%-20s | %-10s | %-15s | %s\n" "Service" "Statut" "Depuis" "Port"
printf "%s\n" "$(printf '=%.0s' {1..65})"

for service in "${SERVICES[@]}"; do
    status=""
    port_icon=""
    
    case "$service" in
        hcautomation|monitor) port_icon="🔌" ;;
    esac
    
    # Lire le statut depuis le fichier temporaire
    if [ -f "$TMP_DIR/${service}_status.txt" ]; then
        status=$(cat "$TMP_DIR/${service}_status.txt")
    fi
    
    # Déterminer l'icône et le texte du statut
    if [ "$status" = "active" ]; then
        icon="✅"
        status_text="active"
    elif [ "$status" = "failed" ] || [ "$status" = "activating" ]; then
        icon="⚠️"
        status_text="$status"
    else
        icon="❌"
        status_text="$status"
    fi
    
    # Lire la date depuis le fichier temporaire
    if [ -f "$TMP_DIR/${service}_since.txt" ]; then
        since=$(cat "$TMP_DIR/${service}_since.txt")
    else
        since="—"
    fi
    
    printf "%-20s | %-10s | %-15s | %s\n" "$service" "$status_text" "$since" "${port_icon}"
done

echo ""
echo "✅ Collecte terminée !"
echo ""

# Sauvegarder les résultats dans un fichier JSON (pour utilisation par d'autres scripts)
echo "💾 Sauvegarde des résultats dans services_state.json..."

# Générer le JSON en lisant les fichiers temporaires
echo "{" > services_state.json
echo "  \"timestamp\": \"$(date -Iseconds)\"," >> services_state.json
echo "  \"host\": \"$HOST\"," >> services_state.json
echo "  \"user\": \"$USER\"," >> services_state.json
echo "  \"services\": [" >> services_state.json

first=true
for service in "${SERVICES[@]}"; do
    if [ "$first" = true ]; then
        first=false
    else
        echo "," >> services_state.json
    fi
    
    # Lire les données depuis les fichiers temporaires
    status=""
    since="—"
    
    if [ -f "$TMP_DIR/${service}_status.txt" ]; then
        status=$(cat "$TMP_DIR/${service}_status.txt")
    fi
    
    if [ -f "$TMP_DIR/${service}_since.txt" ]; then
        since=$(cat "$TMP_DIR/${service}_since.txt")
    fi
    
    # Extraire le port du service
    port_val="-"
    case "$service" in
        hcautomation) port_val="3141" ;;
        monitor) port_val="9090" ;;
    esac
    
    # Nettoyer le statut pour JSON (enlever les icônes)
    status_clean="${status#❓ }"
    status_clean="${status_clean#✅ }"
    status_clean="${status_clean#⚠️ }"
    status_clean="${status_clean#❌ }"
    
    cat >> services_state.json << EOF
    {
      "label": "$service",
      "service": "$service",
      "active": "${status:-—}",
      "since": "$since",
      "port": $port_val,
      "status_clean": "${status_clean:-—}"
    }
EOF
done

echo "]" >> services_state.json
echo "}" >> services_state.json

echo "✅ Résultats sauvegardés dans services_state.json"
echo ""

# Générer le fichier system_state.md en lisant les fichiers temporaires
echo "📝 Génération de system_state.md..."

cat > system_state.md << EOF
# État des Services — Pi Monitor

**Date de génération :** $(date +"%Y-%m-%d %H:%M:%S")  
**Date d'acquisition :** $(date +"%d/%m %Y %H:%M")  
**Utilisateur :** $USER  
**Machine :** $HOST

---

## 📊 Résumé des services

| Service | Statut | Depuis | Port |
|---------|--------|-------|------|
EOF

for service in "${SERVICES[@]}"; do
    status=""
    
    case "$service" in
        hcautomation|monitor) port_icon="🔌" ;;
        *) port_icon="" ;;
    esac
    
    # Lire le statut depuis le fichier temporaire
    if [ -f "$TMP_DIR/${service}_status.txt" ]; then
        status=$(cat "$TMP_DIR/${service}_status.txt")
    fi
    
    # Déterminer l'icône et le texte du statut
    if [ "$status" = "active" ]; then
        icon="✅"
        status_text="active"
    elif [ "$status" = "failed" ] || [ "$status" = "activating" ]; then
        icon="⚠️"
        status_text="$status"
    else
        icon="❌"
        status_text="$status"
    fi
    
    # Lire la date depuis le fichier temporaire
    if [ -f "$TMP_DIR/${service}_since.txt" ]; then
        since=$(cat "$TMP_DIR/${service}_since.txt")
    else
        since="—"
    fi
    
    echo "| $icon $service | $status_text | $since | ${port_icon} |" >> system_state.md
done

cat >> system_state.md << EOF

---

## 📋 Détails des services

EOF

for i in "${!SERVICES[@]}"; do
    service="${SERVICES[$i]}"
    
    # Lire les données depuis les fichiers temporaires
    status=""
    since="—"
    
    if [ -f "$TMP_DIR/${service}_status.txt" ]; then
        status=$(cat "$TMP_DIR/${service}_status.txt")
    fi
    
    if [ -f "$TMP_DIR/${service}_since.txt" ]; then
        since=$(cat "$TMP_DIR/${service}_since.txt")
    fi
    
    echo "### $((i+1)). ${service}" >> system_state.md
    echo "- **Service :** \`$service\`" >> system_state.md
    
    # Déterminer l'icône et le texte du statut
    if [ "$status" = "active" ]; then
        status_text="active"
    elif [ "$status" = "failed" ] || [ "$status" = "activating" ]; then
        status_text="$status"
    else
        status_text="$status"
    fi
    
    echo "- **Statut :** $status_text" >> system_state.md
    echo "- **Démarré le :** $since" >> system_state.md
    
    # Ajouter l'icône du port
    case "$service" in
        hcautomation|monitor) port_icon="🔌" ;;
        *) port_icon="" ;;
    esac
    
    echo "- **Port :** ${port_icon}${service}" >> system_state.md
    echo "" >> system_state.md
done

cat >> system_state.md << EOF
---

## 📊 Résumé

EOF

active_count=0
failed_count=0
unknown_count=0
error_count=0

for service in "${SERVICES[@]}"; do
    status=""
    
    if [ -f "$TMP_DIR/${service}_status.txt" ]; then
        status=$(cat "$TMP_DIR/${service}_status.txt")
    fi
    
    if [ "$status" = "active" ]; then
        ((active_count++))
    elif [ "$status" = "failed" ] || [ "$status" = "activating" ]; then
        ((failed_count++))
    elif [ "$status" = "inactive" ]; then
        ((unknown_count++))
    else
        ((error_count++))
    fi
done

echo "- **Services actifs :** $active_count/2" >> system_state.md
echo "- **Services en échec :** $failed_count" >> system_state.md
echo "- **Services inactifs :** $unknown_count/2" >> system_state.md
echo "- **Erreurs :** $error_count/2" >> system_state.md

cat >> system_state.md << EOF

---

## 🛠️ Commandes utiles

### Vérifier l'état d'un service
\`\`\`bash
systemctl status <service>
# Exemple : systemctl status monitor
\`\`\`

### Redémarrer un service
\`\`\`bash
systemctl restart <service>
# Exemple : systemctl restart monitor
\`\`\`

### Arrêter un service
\`\`\`bash
systemctl stop <service>
# Exemple : systemctl stop monitor
\`\`\`

### Voir les logs d'un service
\`\`\`bash
journalctl -u <service> -n 50 --no-pager
# Exemple : journalctl -u monitor -n 50 --no-pager
\`\`\`

### Vérifier les services Samba (Time Capsule)
\`\`\`bash
systemctl is-active smbd nmbd avahi-daemon
\`\`\`

---

## 📝 Notes de maintenance

- **Dernière mise à jour :** ________________
- **Problèmes rencontrés :** _______________________________________
- **Actions entreprises :** _______________________________________

---

*Généré automatiquement par le script de collecte d'état des services.*
EOF

echo "✅ Fichier system_state.md généré !"
echo ""
echo "🎉 Collecte terminée avec succès !"

