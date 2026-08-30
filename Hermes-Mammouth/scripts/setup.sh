#!/bin/bash
# setup-hermes-mammouth.sh - Installation complète de Hermes via Mammouth AI

set -e

echo "============================================================"
echo "  Installation de Hermes Agent via Mammouth AI"
echo "============================================================"

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
if [[ "$PYTHON_VERSION" < "3.9" ]]; then
    echo "❌ Python 3.9+ requis, vous avez $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION détecté"

# Créer le dossier de travail
WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Dossier de travail : $WORK_DIR"

# 1. Installer les dépendances Python
echo ""
echo "📦 Installation des dépendances Python..."
pip install -r "$WORK_DIR/requirements.txt"

# 2. Copier le fichier .env.example
echo ""
echo "📝 Configuration des variables d'environnement..."
cp "$WORK_DIR/.env.example" "$WORK_DIR/.env"

echo ""
echo "⚠️  À faire maintenant :"
echo "   1. Éditer le fichier .env avec votre clé API Mammouth"
echo "      nano .env  (ou vim, ou éditeur de votre choix)"
echo ""
echo "   2. Remplir la variable MAMMOUTH_API_KEY :"
echo "      MAMMOUTH_API_KEY=votre_clé_api"
echo ""
echo "   3. Obtenir votre clé API sur :"
echo "      https://mammouth.ai/app/account/settings/api"

# 3. Lancer l'agent (optionnel, après configuration)
echo ""
read -p "Lancer un test rapide ? (y/n) " -n1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Lancement du test..."
    
    # Charger les variables d'environnement
    export $(grep -v '^#' "$WORK_DIR/.env" | xargs)
    
    # Lancer l'agent
    python -m "$WORK_DIR/src/main"
fi

echo ""
echo "============================================================"
echo "  Installation terminée !"
echo "============================================================"
echo ""
echo "Pour lancer l'agent :"
echo "   cd $WORK_DIR"
echo "   export $(grep -v '^#' .env | xargs)"
echo "   python -m src.main"
