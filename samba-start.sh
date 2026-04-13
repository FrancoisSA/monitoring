#!/bin/bash
# samba-start.sh — Vérifie et démarre les services Samba + Avahi (Time Capsule)
# Usage : sudo ./samba-start.sh
# Auteur : Pi Monitor / FSA-PI5
set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

OK="${GREEN}✅${NC}"; KO="${RED}❌${NC}"; WARN="${YELLOW}⚠️ ${NC}"
ARROW="${BLUE}▶${NC}"

ERRORS=0   # compteur d'erreurs bloquantes

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     Vérification & Démarrage Samba/Avahi     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""


# ── 1. Droits root ────────────────────────────────────────────────────────────
echo -e "${BOLD}[1] Droits d'exécution${NC}"
if [ "$EUID" -ne 0 ]; then
    echo -e "  ${KO} Ce script doit être exécuté avec sudo"
    exit 1
fi
echo -e "  ${OK} Exécution en root"
echo ""


# ── 2. Paquets Samba ──────────────────────────────────────────────────────────
echo -e "${BOLD}[2] Installation des paquets${NC}"
for pkg in samba samba-common-bin avahi-daemon; do
    if dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
        echo -e "  ${OK} $pkg installé"
    else
        echo -e "  ${KO} $pkg non installé — installation…"
        apt-get install -y "$pkg" >/dev/null 2>&1 \
            && echo -e "  ${OK} $pkg installé avec succès" \
            || { echo -e "  ${KO} Échec de l'installation de $pkg"; ERRORS=$((ERRORS+1)); }
    fi
done
echo ""


# ── 3. Validation smb.conf ────────────────────────────────────────────────────
echo -e "${BOLD}[3] Validation de smb.conf${NC}"
if testparm -s /etc/samba/smb.conf 2>/dev/null | head -1 | grep -q "Loaded"; then
    echo -e "  ${OK} smb.conf valide"
else
    # testparm écrit sur stderr — capturer les deux
    OUTPUT=$(testparm -s /etc/samba/smb.conf 2>&1 | head -5)
    if echo "$OUTPUT" | grep -qi "error\|invalid"; then
        echo -e "  ${KO} smb.conf contient des erreurs :"
        echo "$OUTPUT" | sed 's/^/     /'
        ERRORS=$((ERRORS+1))
    else
        echo -e "  ${OK} smb.conf valide (testparm OK)"
    fi
fi
echo ""


# ── Helper : vérifier/démarrer un service ────────────────────────────────────
ensure_service() {
    local svc="$1"
    local label="$2"
    echo -e "  ${ARROW} $label ($svc)…"

    # Activé au boot ?
    if ! systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        echo -e "     ${WARN} Non activé au démarrage → enable"
        systemctl enable "$svc" 2>/dev/null || true
    fi

    if systemctl is-active --quiet "$svc"; then
        echo -e "     ${OK} Service actif"
    else
        echo -e "     ${WARN} Service inactif → démarrage…"
        if systemctl start "$svc"; then
            sleep 1
            if systemctl is-active --quiet "$svc"; then
                echo -e "     ${OK} Démarré avec succès"
            else
                echo -e "     ${KO} Échec du démarrage"
                ERRORS=$((ERRORS+1))
            fi
        else
            echo -e "     ${KO} Erreur systemctl start"
            ERRORS=$((ERRORS+1))
        fi
    fi
}


# ── 4. Services Samba ─────────────────────────────────────────────────────────
echo -e "${BOLD}[4] Services Samba${NC}"
ensure_service smbd  "Samba daemon (SMB/CIFS)"
ensure_service nmbd  "NetBIOS name service"
echo ""


# ── 5. Service Avahi (Bonjour / Time Capsule) ─────────────────────────────────
echo -e "${BOLD}[5] Service Avahi (Bonjour)${NC}"
ensure_service avahi-daemon "Avahi Daemon"
echo ""


# ── 6. Point de montage Time Capsule ──────────────────────────────────────────
echo -e "${BOLD}[6] Point de montage Time Capsule${NC}"
TC_MOUNT="/mnt/timecapsule"

if mountpoint -q "$TC_MOUNT" 2>/dev/null; then
    echo -e "  ${OK} $TC_MOUNT est monté"
    # Espace disponible
    AVAIL=$(df -h "$TC_MOUNT" | awk 'NR==2 {print $4}')
    USED=$(df -h  "$TC_MOUNT" | awk 'NR==2 {print $5}')
    echo -e "       Espace libre : ${BOLD}$AVAIL${NC}  (utilisé : $USED)"
elif [ -d "$TC_MOUNT" ]; then
    echo -e "  ${WARN} Dossier présent mais non monté — tentative de montage via fstab…"
    if mount "$TC_MOUNT" 2>/dev/null; then
        echo -e "  ${OK} Monté avec succès"
    else
        echo -e "  ${KO} Impossible de monter $TC_MOUNT — vérifier /etc/fstab"
        ERRORS=$((ERRORS+1))
    fi
else
    echo -e "  ${KO} $TC_MOUNT inexistant — le disque Time Capsule est-il branché ?"
    ERRORS=$((ERRORS+1))
fi
echo ""


# ── 7. Permissions du dossier Time Machine ────────────────────────────────────
echo -e "${BOLD}[7] Permissions Time Machine${NC}"
TC_DIR="/mnt/timecapsule"
if [ -d "$TC_DIR" ]; then
    OWNER=$(stat -c "%U" "$TC_DIR")
    GROUP=$(stat -c "%G" "$TC_DIR")
    PERMS=$(stat -c "%A" "$TC_DIR")
    echo -e "  Propriétaire : ${BOLD}$OWNER:$GROUP${NC}   Permissions : ${BOLD}$PERMS${NC}"

    # Vérification d'écriture
    TESTFILE="$TC_DIR/.samba_write_test_$$"
    if touch "$TESTFILE" 2>/dev/null; then
        rm -f "$TESTFILE"
        echo -e "  ${OK} Écriture possible"
    else
        echo -e "  ${KO} Écriture impossible — vérifier les permissions"
        echo -e "       Suggestion : sudo chown -R nobody:nogroup $TC_DIR && sudo chmod -R 0777 $TC_DIR"
        ERRORS=$((ERRORS+1))
    fi
else
    echo -e "  ${WARN} Dossier $TC_DIR non disponible (voir étape 6)"
fi
echo ""


# ── 8. Utilisateurs Samba ─────────────────────────────────────────────────────
echo -e "${BOLD}[8] Utilisateurs Samba${NC}"
USERS=$(pdbedit -L 2>/dev/null | grep -v "^$" | cut -d: -f1)
if [ -n "$USERS" ]; then
    while IFS= read -r u; do
        echo -e "  ${OK} $u"
    done <<< "$USERS"
else
    echo -e "  ${WARN} Aucun utilisateur Samba configuré"
    echo -e "       Créer avec : sudo smbpasswd -a <utilisateur>"
fi
echo ""


# ── 9. Partages actifs ────────────────────────────────────────────────────────
echo -e "${BOLD}[9] Partages Samba disponibles${NC}"
SHARES=$(smbclient -L localhost -U% -N 2>/dev/null | grep -E "^\s+\S.*(Disk|IPC)" || true)
if [ -n "$SHARES" ]; then
    echo "$SHARES" | while IFS= read -r line; do
        echo -e "  ${OK} $line"
    done
else
    echo -e "  ${WARN} Aucun partage listé (smbd en cours de démarrage ?)"
fi
echo ""


# ── 10. Connexions actives ────────────────────────────────────────────────────
echo -e "${BOLD}[10] Connexions SMB actives${NC}"
CONNS=$(smbstatus --brief 2>/dev/null | tail -n +3 | grep -v "^$" || true)
if [ -n "$CONNS" ]; then
    echo -e "  ${OK} Sessions actives :"
    echo "$CONNS" | sed 's/^/     /'
else
    echo -e "  ℹ️  Aucune connexion SMB active"
fi
echo ""


# ── Résumé ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${BOLD}║  ${GREEN}✅ Tous les services Samba sont opérationnels${NC}${BOLD}  ║${NC}"
else
    echo -e "${BOLD}║  ${RED}❌ $ERRORS problème(s) détecté(s) — voir ci-dessus${NC}${BOLD}  ║${NC}"
fi
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""

exit "$ERRORS"
