# Hermes Agent via Mammouth AI

Assistant personnel basé sur le modèle **Hermes 3** (Nous Research) utilisant l'API **Mammouth AI** comme backend LLM.

## 🎯 Fonctionnalités

- ✅ **Modèle Hermes 3** : LLM open-source optimisé pour les agents (format `tool_call` XML)
- ✅ **API Mammouth AI** : Alternative économique aux API cloud (Mistral, Claude, etc.)
- 🔌 **Outils Google** : Tasks, Calendar, Gmail — schémas branchés et exécutés par la boucle agentique, mais en **bouchon honnête** tant que l'OAuth2 Google n'est pas connecté (v1.1)
- ✅ **Interface interactive** : Terminal avec affichage coloré (Rich)
- ✅ **API web** : Dashboard de chat Flask sur le port 9191, historique côté serveur (v1.1)

## 📋 Prérequis

- **Python 3.9+**
- **Clé API Mammouth AI** : [https://mammouth.ai/app/account/settings/api](https://mammouth.ai/app/account/settings/api)
- **Comptes Google** : Tasks, Calendar, Gmail (avec OAuth2)

## 🚀 Installation rapide

```bash
# 1. Cloner le projet
git clone <repository>
cd Hermes-Mammouth

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer l'API Mammouth AI
cp .env.example .env
nano .env  # Remplir MAMMOUTH_API_KEY

# 4. Lancer l'agent
python -m src.main
```

## ⚙️ Configuration

### Variables d'environnement (fichier `.env`)

| Variable | Description |
|----------|-------------|
| `MAMMOUTH_API_KEY` | Clé API Mammouth AI (obligatoire) |
| `MAMMOUTH_MODEL` | Modèle à utiliser (`mammouth-recommended`, `hermes3:8b`, etc.) |
| `TEMPERATURE` | Créativité (0.0-2.0, défaut 0.7) |
| `MAX_TOKENS` | Tokens maximum par réponse (défaut 4096) |

### Modèle recommandé

- **`mammouth-recommended`** : Alias qui pointe vers le meilleur modèle du moment (actuellement `glm-5.2`)
- **Prix** : ~1.4 $/M tokens input, ~4.4 $/M tokens output
- **Performance** : Excellent pour les tâches agentic

## 📖 Utilisation

### Mode interactif (terminal)

```bash
python -m src.main
```

Exemple de conversation :

```
👤 Vous : Ajoute une tâche "Acheter des fruits" pour demain à 10h

🤖 Hermes est en train de réfléchir...
  🤖 Assistant
   → 1 outil(s) appelé(s)

🔧 google_tasks
   Tâche ajoutée : "Acheter des fruits" (échéance: demain 10h)

🤖 Assistant
   ✅ Tâche ajoutée avec succès !
```

### Mode web (Raspberry Pi)

Sur le Pi, l'agent tourne en service systemd (`hermes.service`) avec l'API Flask :

```bash
# Déployer le code puis :
sudo systemctl restart hermes
```

- **Dashboard** : `http://10.0.0.2:9191` (web chat, historique conservé côté serveur par session)
- **API** : `POST /api/chat` avec `{"message": "..."}` → `{"content", "tools_used", "rounds"}`
- **Logs** : `sudo journalctl -u hermes -f`

### Programmation (API)

```python
from src.hermes_agent import call_llm, Message, TOOLS

messages = [
    {"role": "user", "content": "Ajoute une tâche 'Acheter des fruits' pour demain"},
]

response = call_llm(messages, TOOLS)
print(response.content)  # Résultat de l'outil ou réponse finale
```

## 🛠️ Architecture

```
Hermes-Mammouth/
├── src/
│   ├── hermes_agent.py    # Cœur de l'agent (appel LLM + outils)
│   ├── main.py            # Point d'entrée interactif
│   └── config.py          # Configuration et chargement .env
├── scripts/               # Scripts d'installation/déploiement
│   ├── setup.sh           # Installation complète (Ollama + Mammouth fallback)
│   └── test_llm.sh        # Test rapide du LLM
├── docs/                  # Documentation
│   └── README.md          # Ce fichier
├── .env.example           # Template de configuration
└── requirements.txt       # Dépendances Python
```

## 💡 Exemples d'utilisation

### Google Tasks
```
👤 Vous : Crée-moi une tâche "Ranger la chambre" pour ce soir à 20h
🤖 Assistant : Tâche créée !
```

### Google Calendar
```
👤 Vous : Réserve-moi un rendez-vous avec Jean-Pierre demain à 15h
🤖 Assistant : Événement créé !
```

### Google Gmail
```
👤 Vous : Réponds à l'email de Jean-Pierre avec "Merci pour ton message"
🤖 Assistant : Email répondu !
```

## ⚠️ Limitations & Conseils

### Performance

- **Latence** : 10-60 secondes par tour (dépend du modèle Mammouth)
- **Coût** : ~0.15 $/tour avec `mammouth-recommended` (Standard plan)
- **Conseil** : Utilisez un plan payant si vous faites beaucoup d'appels

### Qualité

- **Hermes 3** : Très bon pour le français, excellent sur les outils
- **Format outil** : Compatible avec le format XML `tool_call` de Hermes (Ollama normalise automatiquement)

### Fallback automatique

Si Mammouth AI est indisponible, l'agent peut basculer sur un autre provider (à configurer).

## 🔐 Sécurité

- **API Key** : Stockée dans `.env` (non versionnée)
- **Données locales** : Les conversations restent sur votre machine
- **Google API** : Toujours cloud (inévitable pour Google)

## 🐛 Dépannage

### "MAMMOUTH_API_KEY n'est pas définie"
```bash
# Créer le fichier .env avec votre clé API
cp .env.example .
nano .env  # Remplir MAMMOUTH_API_KEY
```

### "Erreur de connexion à Mammouth AI"
- Vérifier que la clé API est correcte
- Vérifier votre plan Mammouth (crédits disponibles)
- Consulter : https://mammouth.ai/app/account/api

### "Timeout lors de l'appel LLM"
- Augmenter `API_TIMEOUT` dans `.env` (défaut 120s)
- Changer de modèle (`mammouth-recommended` → `mistral-small`)

## 📊 Comparaison des modèles Mammouth AI

| Modèle | Prix Input ($/M) | Prix Output ($/M) | Usage recommandé |
|--------|-----------------|------------------|------------------|
| `mammouth-recommended` | 1.4 | 4.4 | **Défaut** (meilleur rapport qualité/prix) |
| `mistral-medium-3.1` | 0.4 | 2 | Tâches simples, budget serré |
| `mistral-small-2603` | 0.15 | 0.6 | Tests, prototypes (très économique) |
| `deepseek-v4-flash` | 0.14 | 0.28 | **Le moins cher** (très rapide) |

## 🔄 Migration depuis Mistral Cloud

Si vous utilisez déjà Jeffrey avec Mistral, la migration est simple :

1. Modifier `.env` :
   - `LLM_PROVIDER=mammouth` (au lieu de `mistral`)
   - Ajouter `MAMMOUTH_API_KEY=...`

2. Le code détecte automatiquement le provider et configure le client LLM

3. Relancer l'agent :
   ```bash
   python -m src.main
   ```

## 📚 Ressources

- **Mammouth AI** : https://mammouth.ai
- **Documentation API** : https://info.mammouth.ai/docs/api-quick-start/
- **Hermes 3** : https://nousresearch.com/hermes3
- **Nous Research** : https://nousresearch.com

## 📝 Changelog

### v1.1 — 30 août 2026
- **Boucle agentique complète** (`run_agent`) : les appels d'outils sont exécutés (`_execute_tool`) et leurs résultats renvoyés au modèle (max 5 tours, cf. spec AGENTS.md)
- **Registre d'outils** (`TOOL_REGISTRY`) : outils Google en bouchons honnêtes — brancher une vraie API = remplacer une fonction
- **API web fonctionnelle** : port 9191, historique de conversation côté serveur (sessions cookie, TTL 2 h, 20 messages max)
- Compatibilité **mistralai 1.x / 2.x** (imports + format d'outils), `.env` chargé automatiquement
- `TEMPERATURE`, `MAX_TOKENS`, `API_TIMEOUT` du `.env` désormais pris en compte
- Déploiement Raspberry Pi : service `hermes.service` (`/home/fsalazar/03-hermes-mammouth`)
- Tests locaux sans clé API : `python tests/test_agent.py`
- Nettoyage : `config.py` supprimé (code mort), `test_llm.sh` portable, `.gitignore` corrigé

### v1.0 — 24 août 2026
- Création initiale de Hermes via Mammouth AI
- Intégration avec les outils Google (Tasks, Calendar, Gmail)
- Interface interactive en terminal

---

*Document généré automatiquement à partir de la structure du projet.*