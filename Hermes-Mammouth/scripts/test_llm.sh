#!/bin/bash
# test_llm.sh - Test rapide du LLM Mammouth AI

set -e

echo "============================================================"
echo "  Test rapide du LLM Mammouth AI (Hermes)"
echo "============================================================"

# Vérifier les variables d'environnement
if [ -z "$MAMMOUTH_API_KEY" ]; then
    echo "❌ MAMMOUTH_API_KEY n'est pas définie"
    echo ""
    echo "Pour configurer, utilisez :"
    echo "   export MAMMOUTH_API_KEY=votre_clé_api"
    exit 1
fi

echo "✅ Clé API : ${MAMMOUTH_API_KEY:0:8}..."
echo "✅ Modèle : ${MAMMOUTH_MODEL:-mammouth-recommended}"

# Python du venv s'il existe, sinon python3 système
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -x "$DIR/venv/bin/python" ]; then
    PYTHON="$DIR/venv/bin/python"
else
    PYTHON="python3"
fi

# Importer les modules
SRC_DIR="$DIR/src" "$PYTHON" << 'EOF'
import sys
import os
sys.path.insert(0, os.environ["SRC_DIR"])

from hermes_agent import call_llm, Message
import time

# Prompts de test en français
test_prompts = [
    "Bonjour, qui es-tu ?",
    "Explique-moi comment fonctionne la photosynthèse",
    "Écris un poème sur le printemps",
]

print("\n📝 Tests de prompts :")
print("=" * 60)

for prompt in test_prompts:
    print(f"\n👤 Prompt : {prompt}")
    
    messages = [{"role": "user", "content": prompt}]
    
    start_time = time.time()
    response = call_llm(messages, [])  # Pas d'outils pour le test
    
    latency = time.time() - start_time
    
    print(f"🤖 Réponse : {response.content[:200]}...")
    print(f"⏱️  Latence : {latency:.2f}s")
    print("-" * 60)

print("\n✅ Tests terminés !")
EOF
