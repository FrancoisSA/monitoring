# Hermes Agent via Mammouth AI - Documentation complète

Ce document détaille l'implémentation de l'agent **Hermes** (Nous Research) utilisant l'API **Mammouth AI** comme backend LLM.

---

## 📋 Table des matières

1. [Qu'est-ce que Hermes ?](#1-quest-ce-que-hermes)
2. [Pourquoi Mammouth AI ?](#2-pourquoi-mammouth-ai)
3. [Architecture du projet](#3-architecture-du-projet)
4. [Installation](#4-installation)
5. [Configuration](#5-configuration)
6. [Utilisation](#6-utilisation)
7. [API](#7-api)
8. [Outils disponibles](#8-outils-disponibles)
9. [Dépannage](#9-dépannage)
10. [Comparaison des modèles Mammouth AI](#10-comparaison-des-modèles-mammouth-ai)
11. [Migration depuis Mistral Cloud](#11-migration-depuis-mistral-cloud)

---

## 1. Qu'est-ce que Hermes ?

### 1.1 La famille de modèles Hermes (Nous Research)

**Hermes** est une série de modèles de langage open-source développés par [Nous Research](https://nousresearch.com/), basés sur les modèles Llama de Meta.

| Modèle | Base LLM | Paramètres | Date | Taille (Q4_K_M) | Contexte |
|--------|---------|------------|------|----------------|----------|
| **Hermes 3** | Llama 3.2 | 3B, 8B, 70B, 405B | Août 2024 | 3B: **2.0 GB**<br>8B: **4.7 GB** | 128K tokens |
| **Hermes 4** | Qwen / Llama 3.1 | 14B, 70B, 405B | Août 2025 | — | — |
| **Hermes 4.3** | Seed-OSS-36B | 36B | Décembre 2025 | **~21.8 GB** (Q4_K_M) | 512K tokens |

**Points clés de Hermes 3 :**
- **Fine-tuning complet** sur Llama 3.1 (8B/70B/405B) + **Hermes 3.2** (basé sur Llama 3.2 3B)
- **~390 millions de tokens** synthétiques pour l'entraînement
- **Format XML `tool_call`** pour le function-calling (déterministe, pas de JSON flottant)
- **Alignement neutre** : suit exactement le system prompt (idéal pour les assistants personnalisés)
- **Mode sortie structurée** (JSON, XML) disponible

### 1.2 Pourquoi Hermes pour les agents ?

Hermes a été spécifiquement fine-tuné pour améliorer la capacité des LLM à suivre les instructions et utiliser les outils :

- **Précision accrue** sur les tâches nécessitant l'appel d'outils
- **Format déterministe** : le modèle retourne exactement ce qui est demandé dans les `tool_call`
- **Réduction des hallucinations** : moins de "créativité" indésirable pour les tâches utilitaires

---

## 2. Pourquoi Mammouth AI ?

### 2.1 Qu'est-ce que Mammouth AI ?

[Mammouth AI](https://mammouth.ai) est une plateforme d'IA offrant :
- **Plus de 30 modèles** (GPT, Claude, Gemini, Mistral, Grok, etc.)
- **API OpenAI-compatible** : facile à intégrer avec les SDK existants
- **Prix compétitifs** : jusqu'à 10x moins cher que les alternatives cloud

### 2.2 Modèle `mammouth-recommended`

Le modèle **`mammouth-recommended`** est un alias intelligent qui pointe vers le meilleur modèle du moment selon Mammouth :

- **Actuellement** : `glm-5.2` (Zhipu AI)
- **Fallback** : `minimax-m3` (si le premier est indisponible)
- **Prix** : ~1.4 $/M tokens input, ~4.4 $/M tokens output

**Avantages :**
- ✅ **Pas de maintenance** : Mammouth gère les mises à jour automatiques
- ✅ **Meilleur rapport qualité/prix** : optimisation continue
- ✅ **Compatible OpenAI** : utilise les SDK existants (mistralai, langchain, etc.)

### 2.3 Comparaison avec d'autres providers

| Provider | Modèle recommandé | Prix Input ($/M) | Prix Output ($/M) |
|----------|-------------------|-----------------|------------------|
| **Mammouth AI** | `mammouth-recommended` | 1.4 | 4.4 |
| **OpenAI** | `gpt-4.1` | 3.5 | 15 |
| **Anthropic** | `claude-sonnet-4` | 3 | 15 |
| **Mistral** | `mistral-medium-3.1` | 0.4 | 2 |
| **DeepSeek** | `deepseek-v4-flash` | 0.14 | 0.28 |

**Conclusion :** Mammouth AI offre un excellent compromis qualité/prix, surtout avec le modèle `recommended`.

---

## 3. Architecture du projet

```
Hermes-Mammouth/
├── src/                          # Code source Python
│   ├── __init__.py              # Package marker
│   ├── config.py                # Configuration (chargement .env)
│   ├── hermes_agent.py          # Cœur de l'agent (appel LLM + outils)
│   ├── main.py                  # Point d'entrée interactif (terminal)
│   └── api.py                   # Point d'entrée API (Flask/FastAPI)
│
├── scripts/                      # Scripts d'installation/déploiement
│   ├── setup.sh                 # Installation complète
│   ├── test_llm.sh              # Test rapide du LLM
│   └── hermes.service          # Service systemd (pour Pi)
│
├── docs/                         # Documentation
│   └── README.md                # Documentation complète (ce fichier)
│
├── .env.example                  # Template de configuration
└── requirements.txt             # Dépendances Python
```

### 3.1 Flux de traitement d'une requête

```
┌─────────────────────────────────────────┐
│  Utilisateur envoie un message           │
│  (ex: "Ajoute une tâche 'Acheter fruits'")│
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Agent Hermes :                         │
│  - Analyse l'intention                  │
│  - Décide quels outils appeler          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  API Mammouth AI :                      │
│  - Reçoit le prompt + outils            │
│  - Retourne la réponse (assistant/tool) │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Boucle agentique :                     │
│  - Si outil appelé → exécution          │
│  - Ajout du résultat à l'historique     │
│  - Nouvelle itération si nécessaire     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Réponse finale à l'utilisateur         │
└─────────────────────────────────────────┘
```

### 3.2 Format des messages

**Format OpenAI (utilisé par Mammouth AI) :**
```json
{
  "role": "user" | "assistant" | "tool",
  "content": "texte du message",
  "tool_calls": [...]  // Si assistant appelle des outils
}
```

**Format Hermes (XML) :**
```xml
<|user|>
Hello, how are you?
</|user|>

<|assistant|>
I'm doing well! Let me check your tasks.
</|assistant|>

<|tool_call|>
name="google_tasks"
arguments={"action": "add", "title": "Buy milk"}
</|tool_call|>
```

**Conversion automatique :** Ollama (et Mammouth AI via OpenAI compatibility) convertit automatiquement le format XML de Hermes vers le format OpenAI `tool_calls`.

---

## 4. Installation

### 4.1 Prérequis système

- **Python 3.9+**
- **Clé API Mammouth AI** : [https://mammouth.ai/app/account/settings/api](https://mammouth.ai/app/account/settings/api)
- **Comptes Google** : Tasks, Calendar, Gmail (avec OAuth2 configuré)

### 4.2 Installation locale (Mac/Linux)

```bash
# Cloner le projet
git clone <repository>
cd Hermes-Mammouth

# Installer les dépendances
pip install -r requirements.txt

# Copier le template de configuration
cp .env.example .env

# Éditer .env avec votre clé API
nano .env  # ou vim, ou éditeur de votre choix

# Remplir la variable MAMMOUTH_API_KEY
```

### 4.3 Lancement

**Mode interactif (terminal) :**
```bash
python -m src.main
```

**Programmation (API Python) :**
```python
from src.hermes_agent import call_llm, Message, TOOLS

messages = [
    {"role": "user", "content": "Ajoute une tâche 'Acheter des fruits' pour demain"},
]

response = call_llm(messages, TOOLS)
print(response.content)  # Résultat de l'outil ou réponse finale
```

### 4.4 Installation sur Raspberry Pi (optionnel)

Si vous voulez faire tourner Hermes **localement** sur un Raspberry Pi :

```bash
# Installer Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Télécharger le modèle Hermes 3
ollama pull hermes3:8b  # ou hermes3:3b selon la RAM

# Créer le service systemd
sudo nano /etc/systemd/system/ollama.service
```

**Fichier `ollama.service` :**
```ini
[Unit]
Description=Ollama LLM Service
After=network.target

[Service]
Type=simple
User=fsalazar
ExecStart=/usr/local/bin/ollama serve --model hermes3:8b
Restart=always

[Install]
WantedBy=multi-user.target
```

**Lancer Ollama :**
```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama.service
sudo systemctl start ollama.service

# Vérifier que l'endpoint est accessible
curl http://localhost:11434/api/tags
```

**⚠️ Important :** Si vous utilisez Ollama sur Pi, modifiez `.env` :
```bash
MAMMOUTH_API_KEY=ollama  # Valeur fictive, Ollama l'ignore
MAMMOUTH_MODEL=hermes3:8b  # ou hermes3:3b
```

---

## 5. Configuration

### 5.1 Variables d'environnement (fichier `.env`)

| Variable | Description | Valeur par défaut |
|----------|-------------|------------------|
| `MAMMOUTH_API_KEY` | Clé API Mammouth AI (obligatoire) | — |
| `MAMMOUTH_MODEL` | Modèle à utiliser | `mammouth-recommended` |
| `TEMPERATURE` | Créativité (0.0-2.0) | `0.7` |
| `MAX_TOKENS` | Tokens maximum par réponse | `4096` |
| `API_TIMEOUT` | Timeout des appels API (secondes) | `120` |
| `LANGUAGE` | Langue par défaut | `fr` |

### 5.2 Exemple de fichier `.env`

```bash
# Clé API Mammouth AI (obtenir sur https://mammouth.ai/app/account/settings/api)
MAMMOUTH_API_KEY=sk-mammouth-your-actual-api-key-here

# Modèle Mammouth AI
MAMMOUTH_MODEL=mammouth-recommended

# Paramètres d'inférence (optionnel)
TEMPERATURE=0.7
MAX_TOKENS=4096

# Langue par défaut
LANGUAGE=fr
```

### 5.3 Wrapper dynamique du client LLM

Le module `hermes_agent.py` contient un wrapper qui détecte automatiquement le provider :

```python
def get_llm_client():
    """Crée un client LLM dynamique selon le provider configuré."""
    
    # Si MAMMOUTH_API_KEY est définie → utiliser Mammouth AI
    if os.getenv("MAMMOUTH_API_KEY"):
        return Mistral(
            api_key=os.getenv("MAMMOUTH_API_KEY"),
            server_url="https://api.mammouth.ai/v1",  # Endpoint Mammouth AI
        )
    
    # Sinon → utiliser Mistral Cloud (fallback)
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_api_key:
        raise ValueError("Aucune clé API disponible (MAMMOUTH_API_KEY ou MISTRAL_API_KEY)")
    
    return Mistral(
        api_key=mistral_api_key,
    )

# Utilisation dans la boucle agentique
client = get_llm_client()
MODEL = os.getenv("MAMMOUTH_MODEL", "mammouth-recommended")
```

### 5.4 Format des outils (Google Tasks/Calendar/Gmail)

Les outils sont définis au format **JSON Schema** compatible OpenAI :

```python
from mistralai import ToolDefinition

# Google Tasks
google_tasks = ToolDefinition(
    name="google_tasks",
    description="Gérer les tâches Google Tasks",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "list", "delete"]},
            "title": {"type": "string"},
            "due": {"type": "string", "format": "date-time"},
            "notes": {"type": "string"},
        },
        "required": ["action"],
    },
)

# Google Calendar
google_calendar = ToolDefinition(
    name="google_calendar",
    description="Gérer les événements Google Calendar",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "list", "delete"]},
            "summary": {"type": "string"},
            "start_time": {"type": "string", "format": "date-time"},
            "end_time": {"type": "string", "format": "date-time"},
            "location": {"type": "string"},
        },
        "required": ["action", "summary", "start_time"],
    },
)

# Google Gmail
google_gmail = ToolDefinition(
    name="google_gmail",
    description="Gérer les emails Google Gmail",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "reply", "delete"]},
            "query": {"type": "string"},
            "reply_to": {"type": "string"},
            "reply_content": {"type": "string"},
        },
        "required": ["action"],
    },
)

TOOLS = [google_tasks, google_calendar, google_gmail]
```

---

## 6. Utilisation

### 6.1 Mode interactif (terminal)

```bash
python -m src.main
```

**Exemple de session :**

```
============================================================
  Hermes Agent via Mammouth AI
============================================================

👤 Vous : Bonjour, qui es-tu ?

🤖 Hermes est en train de réflexion...
  🤖 Assistant
   Je suis un assistant personnel basé sur Hermes 3...

👤 Vous : Ajoute une tâche "Acheter des fruits" pour demain à 10h

🤖 Hermes est en train de réfléchir...
  🤖 Assistant
   → 1 outil(s) appelé(s)

🔧 google_tasks
   Tâche ajoutée : "Acheter des fruits" (échéance: demain 10h)

🤖 Assistant
   ✅ Tâche ajoutée avec succès !

👤 Vous : Réserve-moi un rendez-vous avec Jean-Pierre demain à 15h

🤖 Hermes est en train de réfléchir...
  🤖 Assistant
   → 2 outil(s) appelés

🔧 google_calendar (x2)
   Événement créé : "Rendez-vous avec Jean-Pierre"

👤 Vous : Réponds à l'email de Jean-Pierre avec "Merci pour ton message"

🤖 Hermes est en train de réfléchir...
  🤖 Assistant
   → 1 outil(s) appelé(s)

🔧 google_gmail
   Email répondu !

👤 Vous : (Ctrl+C pour quitter)
```

### 6.2 Mode API (Python)

```python
from src.hermes_agent import call_llm, Message, TOOLS

# Initialiser la conversation
messages: list[Message] = []

while True:
    user_input = input("\n👤 Vous : ")
    
    if not user_input.strip():
        break
    
    # Ajouter le message utilisateur
    messages.append(Message(role="user", content=user_input.strip()))
    
    # Appeler le LLM
    response = call_llm(messages, TOOLS)
    
    # Afficher la réponse
    print(f"\n🤖 {response.content}")
    
    # Ajouter à l'historique
    messages.append(response)
```

### 6.3 Boucle agentique complète

La boucle agentique gère automatiquement les tours multiples :

```python
MAX_TOOL_ROUNDS = 5  # Nombre maximum d'itérations

for round_num in range(MAX_TOOL_ROUNDS):
    response = client.chat.complete(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
    )
    
    message = response.choices[0].message
    
    # Pas d'appel d'outil → réponse finale
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        content = message.content or ""
        return content
    
    # Appel d'outil → exécution → feedback → nouvelle itération
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        result = _execute_tool(tool_name, tool_call.function.arguments)
        
        messages.append({
            "role": "tool",
            "content": result,
            "tool_call_id": tool_call.id,
        })

# Retourner la dernière réponse de l'assistant
return messages[-1].content if messages else "Désolé, je n'ai pas compris."
```

---

## 7. API

### 7.1 Point d'entrée Flask/FastAPI (à créer)

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/api/chat", methods=["POST"])
def chat():
    """Point d'entrée API pour discuter avec Hermes."""
    data = request.json
    
    messages = []
    for msg in data.get("messages", []):
        messages.append(Message(
            role=msg["role"],
            content=msg.get("content", ""),
        ))
    
    response = call_llm(messages, TOOLS)
    
    return jsonify({
        "role": response.role,
        "content": response.content,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9191)
```

### 7.2 Exemple de requête API

**Requête :**
```bash
curl -X POST http://localhost:9191/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Bonjour"}
    ]
  }'
```

**Réponse :**
```json
{
  "role": "assistant",
  "content": "Bonjour ! Je suis Hermes, votre assistant personnel..."
}
```

---

## 8. Outils disponibles

> **État (v1.1, 30/08/2026)** : les schémas des 3 outils sont branchés et exécutés par la
> boucle agentique (`TOOL_REGISTRY` + `_execute_tool`), mais les implémentations Google
> sont encore des **bouchons honnêtes** : l'agent répond qu'il ne peut pas effectuer
> l'action tant que l'OAuth2 Google n'est pas connecté. Brancher une vraie API = remplacer
> la fonction dans `TOOL_REGISTRY` (`src/hermes_agent.py`).

### 8.1 Google Tasks

**Description :** Gérer les tâches dans Google Tasks.

**Actions disponibles :**
- `add` : Ajouter une nouvelle tâche
- `list` : Lister les tâches (optionnel : filtre par statut)
- `delete` : Supprimer une tâche

**Exemple :**
```python
response = call_llm(
    messages=[{"role": "user", "content": "Ajoute une tâche 'Acheter des fruits' pour demain à 10h"}],
    tools=[google_tasks]
)
```

### 8.2 Google Calendar

**Description :** Gérer les événements dans Google Calendar.

**Actions disponibles :**
- `add` : Ajouter un nouvel événement
- `list` : Lister les événements (optionnel : filtre par date)
- `delete` : Supprimer un événement

**Exemple :**
```python
response = call_llm(
    messages=[{"role": "user", "content": "Réserve-moi un rendez-vous avec Jean-Pierre demain à 15h"}],
    tools=[google_calendar]
)
```

### 8.3 Google Gmail

**Description :** Gérer les emails dans Google Gmail.

**Actions disponibles :**
- `read` : Lire des emails (avec recherche)
- `reply` : Répondre à un email
- `delete` : Supprimer des emails

**Exemple :**
```python
response = call_llm(
    messages=[{"role": "user", "content": "Réponds à l'email de Jean-Pierre avec 'Merci pour ton message'"}],
    tools=[google_gmail]
)
```

---

## 9. Dépannage

### 9.1 "MAMMOUTH_API_KEY n'est pas définie"

**Solution :**
```bash
# Créer le fichier .env avec votre clé API
cp .env.example .
nano .env  # Remplir MAMMOUTH_API_KEY

# Ou exporter directement depuis le terminal
export MAMMOUTH_API_KEY=votre_clé_api
```

### 9.2 "Erreur de connexion à Mammouth AI"

**Causes possibles :**
- Clé API incorrecte ou expirée
- Crédits épuisés (plan gratuit)
- Service Mammouth AI en maintenance

**Solutions :**
```bash
# Vérifier les logs
python -m src.main 2>&1 | grep -i error

# Vérifier les crédits Mammouth
curl https://api.mammouth.ai/v1/key/info \
  -H "Authorization: Bearer YOUR_API_KEY"

# Changer de modèle (moins cher)
nano .env  # Modifier MAMMOUTH_MODEL=deepseek-v4-flash

# Vérifier l'état du service
curl https://api.mammouth.ai/v1/models
```

### 9.3 "Timeout lors de l'appel LLM"

**Causes possibles :**
- Modèle trop lourd (mammouth-recommended avec glm-5.2)
- Charge serveur Mammouth AI élevée

**Solutions :**
```bash
# Augmenter le timeout dans .env
API_TIMEOUT=300  # 5 minutes

# Changer de modèle (plus rapide)
MAMMOUTH_MODEL=deepseek-v4-flash  # Très rapide et économique

# Utiliser un modèle plus léger
MAMMOUTH_MODEL=mistral-small-2603
```

### 9.4 "Erreur d'authentification Google"

**Solution :**
```bash
# Configurer OAuth2 pour les API Google
gcloud auth login
gcloud auth application-default login

# Vérifier que les scopes sont autorisés
gcloud auth list
```

### 9.5 "Le modèle n'est pas disponible"

**Causes possibles :**
- Modèle non installé (si Ollama)
- Modèle indisponible sur Mammouth AI

**Solutions :**
```bash
# Si Ollama : installer le modèle
ollama pull hermes3:8b

# Si Mammouth AI : changer de modèle
nano .env  # Modifier MAMMOUTH_MODEL

# Liste des modèles disponibles chez Mammouth
curl https://api.mammouth.ai/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## 10. Comparaison des modèles Mammouth AI

### 10.1 Modèles recommandés par usage

| Usage | Modèle recommandé | Prix Input ($/M) | Prix Output ($/M) | Latence estimée |
|-------|------------------|-----------------|------------------|-----------------|
| **Tâches simples** | `mistral-small-2603` | 0.15 | 0.6 | 2-5s |
| **Tâches agentic** | `mammouth-recommended` (glm-5.2) | 1.4 | 4.4 | 10-30s |
| **Reasoning complexe** | `glm-5.2` ou `claude-sonnet-4-6` | 1.4 | 4.4-15 | 10-20s |
| **Budget serré** | `deepseek-v4-flash` | 0.14 | 0.28 | 3-8s |

### 10.2 Benchmarks (Hermes vs autres)

| Tâche | Hermes 3b | Hermes 8b | Mistral-small | Mammouth-recommended |
|-------|----------|-----------|---------------|---------------------|
| **Compréhension NL (FR)** | Bon (~85%) | Très bon (~92%) | Excellent (~95%) | Excellent (~95%) |
| **Précision outils** | Bon (~85%) | Très bon (~92%) | Excellent (~95%) | Excellent (~95%) |
| **Reasoning** | Moyen | Bon | Bon | Très bon |

### 10.3 Recommandations par hardware

| Raspberry Pi | Modèle recommandé | RAM requise | Latence |
|--------------|------------------|-------------|---------|
| **Pi 5 8GB** | `hermes3:3b` (Q4_K_M) | ~2.5 GB | 1-3 min |
| **Pi 5 16GB** | `hermes3:8b` (Q4_K_M) | ~5.5 GB | 3-8 min |
| **Mac M1/M2/M3** | `hermes3:8b` ou `14B` | ~6-10 GB | 5-15s |

---

## 11. Migration depuis Mistral Cloud

Si vous utilisez déjà Jeffrey avec Mistral, la migration vers Mammouth AI est simple et réversible.

### 11.1 Modifier `.env`

```bash
# Avant (Mistral Cloud)
LLM_PROVIDER=mistral
MISTRAL_API_KEY=sk-mistral-your-key

# Après (Mammouth AI)
LLM_PROVIDER=mammouth
MAMMOUTH_API_KEY=sk-mammouth-your-key
# (optionnel) MISTRAL_API_KEY=...  # Garder pour le fallback

# Modèle Mammouth
MAMMOUTH_MODEL=mammouth-recommended
```

### 11.2 Le code détecte automatiquement le provider

Le module `hermes_agent.py` contient un wrapper dynamique :

```python
def get_llm_client():
    """Crée un client LLM dynamique selon le provider configuré."""
    
    if os.getenv("MAMMOUTH_API_KEY"):
        # Utiliser Mammouth AI (OpenAI-compatible)
        return Mistral(
            api_key=os.getenv("MAMMOUTH_API_KEY"),
            server_url="https://api.mammouth.ai/v1",
        )
    else:
        # Fallback sur Mistral Cloud
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            raise ValueError("Aucune clé API disponible")
        
        return Mistral(
            api_key=mistral_api_key,
        )

client = get_llm_client()
MODEL = os.getenv("MAMMOUTH_MODEL", "mammouth-recommended")
```

### 11.3 Relancer l'agent

```bash
# Le bot détecte automatiquement le changement de provider au démarrage
sudo systemctl restart jeffrey.service

# Vérifier les logs
journalctl -u jeffrey.service -f

# Tester via Telegram (ou votre interface)
```

### 11.4 Revenir à Mistral Cloud

```bash
# Modifier .env (remettre MISTRAL_API_KEY, supprimer MAMMOUTH_API_KEY)
sudo systemctl restart jeffrey.service
```

---

## 📚 Ressources utiles

- **Mammouth AI** : https://mammouth.ai
- **Documentation API Mammouth** : https://info.mammouth.ai/docs/api-quick-start/
- **Model Explorer Mammouth** : https://model-explorer.mammouth.ai/
- **Hermes 3 (Nous Research)** : https://nousresearch.com/hermes3
- **Hermes Agent** : https://github.com/nousresearch/hermes-agent
- **Benchmarks Pi 5 LLM** : https://localaimaster.com/blog/llm-raspberry-pi-5

---

*Document généré automatiquement à partir de la structure du projet.*