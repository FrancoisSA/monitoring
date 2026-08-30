# Hermes Agent via Mammouth AI - Instructions pour les agents IA

Ce dossier contient les instructions spécifiques pour les agents IA travaillant sur le projet **Hermes Agent via Mammouth AI**.

---

## 🎯 Objectif du projet

Créer un assistant personnel basé sur le modèle **Hermes 3** (Nous Research) en utilisant l'API **Mammouth AI** comme backend LLM.

### Pourquoi Mammouth AI ?

- **API OpenAI-compatible** : facile à intégrer avec les SDK existants (mistralai, langchain, etc.)
- **Modèle `mammouth-recommended`** : alias intelligent qui pointe vers le meilleur modèle du moment (actuellement `glm-5.2`)
- **Prix compétitifs** : jusqu'à 10x moins cher que les alternatives cloud

### Pourquoi Hermes ?

- **Fine-tuning optimisé pour les agents** : format `tool_call` XML déterministe
- **Meilleure précision sur l'utilisation des outils** que les modèles non fine-tunés
- **Alignement neutre** : suit exactement le system prompt

---

## 📁 Structure du projet

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
│   └── README.md                # Documentation complète
│
├── .env.example                  # Template de configuration
└── requirements.txt             # Dépendances Python
```

---

## 🛠️ Tâches principales pour les agents

### 1. Configuration initiale

**Fichiers à créer :**
- `.env` : avec `MAMMOUTH_API_KEY` (à remplir par l'utilisateur)
- `.env.example` : template de configuration

**Variables critiques :**
```bash
MAMMOUTH_API_KEY=sk-mammouth-your-actual-api-key-here  # OBLIGATOIRE
MAMMOUTH_MODEL=mammouth-recommended  # ou mammouth, recommended
```

### 2. Wrapper dynamique du client LLM

**Fichier :** `src/hermes_agent.py`

Le wrapper doit détecter automatiquement le provider :

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
        raise ValueError("Aucune clé API disponible")
    
    return Mistral(
        api_key=mistral_api_key,
    )

# Utilisation dans la boucle agentique
client = get_llm_client()
MODEL = os.getenv("MAMMOUTH_MODEL", "mammouth-recommended")
```

### 3. Format des outils (Google Tasks/Calendar/Gmail)

**Fichier :** `src/hermes_agent.py`

Les outils doivent être au format **JSON Schema** compatible OpenAI :

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
    input_schema={...},
)

# Google Gmail
google_gmail = ToolDefinition(
    name="google_gmail",
    description="Gérer les emails Google Gmail",
    input_schema={...},
)

TOOLS = [google_tasks, google_calendar, google_gmail]
```

### 4. Boucle agentique

**Fichier :** `src/hermes_agent.py`

La boucle gère les tours multiples d'appels à des outils :

```python
MAX_TOOL_ROUNDS = 5  # Nombre maximum d'itérations

for round_num in range(MAX_TOOL_ROUNDS):
    response = client.chat.complete(
        model=MODEL,
        messages=messages,
        tools=TOOLS,  # mêmes outils JSON Schema que pour Mistral
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

### 5. Interface interactive (terminal)

**Fichier :** `src/main.py`

Interface avec affichage coloré via **Rich** :

```python
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

def main():
    console.print(Panel("[bold blue]Hermes Agent via Mammouth AI[/]", title="🤖"))
    
    messages: list[Message] = []
    
    while True:
        user_input = console.input("\n👤 Vous : ")
        
        if not user_input.strip():
            break
        
        messages.append(Message(role="user", content=user_input.strip()))
        
        console.print("[bold yellow]Hermes est en train de réfléchir...[/]")
        
        response = call_llm(messages, TOOLS)
        
        # Afficher la réponse avec les outils appelés
        console.print(format_response(response))
```

### 6. API Flask (optionnel)

**Fichier :** `src/api.py`

Point d'entrée pour discuter via une interface web/API REST :

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/api/chat", methods=["POST"])
def chat_api():
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
        "content": response.content or "",
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9191)
```

---

## 📊 Comparaison des modèles Mammouth AI

| Modèle | Prix Input ($/M) | Prix Output ($/M) | Usage recommandé |
|--------|-----------------|------------------|------------------|
| `mammouth-recommended` | 1.4 | 4.4 | **Défaut** (meilleur rapport qualité/prix) |
| `mistral-medium-3.1` | 0.4 | 2 | Tâches simples, budget serré |
| `mistral-small-2603` | 0.15 | 0.6 | Tests, prototypes (très économique) |
| `deepseek-v4-flash` | 0.14 | 0.28 | **Le moins cher** (très rapide) |

### Modèle recommandé par usage

| Usage | Modèle recommandé |
|-------|------------------|
| **Tâches simples** | `mistral-small-2603` |
| **Tâches agentic** | `mammouth-recommended` (alias pour `glm-5.2`) |
| **Reasoning complexe** | `glm-5.2` ou `claude-sonnet-4-6` |

---

## 🐛 Dépannage courant

### "MAMMOUTH_API_KEY n'est pas définie"

**Solution :**
```bash
# Créer le fichier .env avec votre clé API
cp .env.example .
nano .env  # Remplir MAMMOUTH_API_KEY

# Ou exporter directement depuis le terminal
export MAMMOUTH_API_KEY=votre_clé_api
```

### "Erreur de connexion à Mammouth AI"

**Causes possibles :**
- Clé API incorrecte ou expirée
- Crédits épuisés (plan gratuit)
- Service Mammouth AI en maintenance

**Solutions :**
```bash
# Vérifier les crédits Mammouth
curl https://api.mammouth.ai/v1/key/info \
  -H "Authorization: Bearer YOUR_API_KEY"

# Changer de modèle (moins cher)
nano .env  # Modifier MAMMOUTH_MODEL=deepseek-v4-flash

# Vérifier l'état du service
curl https://api.mammouth.ai/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### "Timeout lors de l'appel LLM"

**Causes possibles :**
- Modèle trop lourd (mammouth-recommended avec glm-5.2)
- Charge serveur Mammouth AI élevée

**Solutions :**
```bash
# Augmenter le timeout dans .env
API_TIMEOUT=300  # 5 minutes

# Changer de modèle (plus rapide)
MAMMOUTH_MODEL=deepseek-v4-flash  # Très rapide et économique
```

---

## 📚 Ressources utiles

- **Mammouth AI** : https://mammouth.ai
- **Documentation API Mammouth** : https://info.mammouth.ai/docs/api-quick-start/
- **Model Explorer Mammouth** : https://model-explorer.mammouth.ai/
- **Hermes 3 (Nous Research)** : https://nousresearch.com/hermes3
- **Hermes Agent** : https://github.com/nousresearch/hermes-agent

---

## 🔄 Migration depuis Mistral Cloud

Si vous utilisez déjà Jeffrey avec Mistral, la migration vers Mammouth AI est simple et réversible.

### Modifier `.env`

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

### Le code détecte automatiquement le provider

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

### Relancer l'agent

```bash
# Le bot détecte automatiquement le changement de provider au démarrage
sudo systemctl restart jeffrey.service

# Vérifier les logs
journalctl -u jeffrey.service -f

# Tester via Telegram (ou votre interface)
```

---

## 📝 Checklist pour les agents

- [x] Créer la structure du projet (`Hermes-Mammouth/`)
- [x] Créer `src/hermes_agent.py` avec le wrapper LLM et la boucle agentique
- [x] Créer `src/main.py` pour l'interface interactive
- [x] Créer `src/api.py` pour l'API Flask (optionnel)
- [x] Créer `.env.example` avec les variables Mammouth AI
- [x] Créer `requirements.txt` avec les dépendances
- [x] Créer les scripts d'installation (`setup.sh`, `test_llm.sh`)
- [ ] Tester l'agent avec différents prompts
- [x] Documenter le tout dans `docs/README.md`

---

*Document généré automatiquement à partir de la structure du projet.*