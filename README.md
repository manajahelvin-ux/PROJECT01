# DataExtract AI

**Extraction • Structuration • Qualité • Intelligence**

Une plateforme Web professionnelle d'Extraction, Nettoyage, Structuration, Validation et Analyse de données Web, propulsée par l'IA.

---

## 🚀 Fonctionnalités

### Pipeline Central
```
SOURCE WEB → EXTRACTION → NETTOYAGE → STRUCTURATION → IA → VALIDATION → STOCKAGE → EXPORT → INTÉGRATION
```

### Modules Principaux
- **Web Scraping** : Extraction statique (HTTPX/BeautifulSoup) et dynamique (Playwright)
- **Constructeur de Sélecteurs** : CSS, XPath, Regex avec test en direct
- **IA Générative** (OpenRouter) : Auto-analyse, nettoyage, structuration, détection d'anomalies
- **Data Quality Center** : Score de qualité multi-dimensionnel (Completeness, Accuracy, Consistency, Uniqueness, Validity)
- **Planification** : Extractions récurrentes via Celery Beat (cron, horaire, quotidien, etc.)
- **Exports** : CSV, Excel XLSX, JSON, XML, Parquet
- **Intégrations** : Webhooks avec retry, Google Sheets
- **Base de Connaissances** : Partage d'équipe de bonnes pratiques
- **API REST** : Documentation OpenAPI/Swagger auto-générée
- **Dashboard** : KPI, graphiques, activité récente

### Sécurité & Conformité
- Anti-SSRF, CSRF, XSS protection
- Respect des `robots.txt` et rate limiting
- Rôles : ADMIN, OPERATOR, VIEWER
- Politique de rétention configurable
- 2FA optionnelle

---

## 🏗️ Architecture

```
dataextract_ai/
├── config/              # Configuration Django (settings, URLs, Celery)
├── apps/
│   ├── authentication/  # Utilisateurs, rôles, permissions
│   ├── dashboard/       # KPI, graphiques, activité
│   ├── projects/        # Gestion des projets
│   ├── scraping/        # Fetch HTML, parsing, Playwright
│   ├── extraction/      # Config, exécution, historique
│   ├── datasets/        # Données extraites
│   ├── ai_engine/       # OpenRouter, prompts, validation IA
│   ├── quality/         # Score qualité, anomalies
│   ├── exports/         # CSV, XLSX, JSON, Parquet
│   ├── integrations/    # Webhooks, Google Sheets
│   ├── scheduling/      # Celery Beat, planification
│   ├── knowledge_base/  # Documentation interne
│   └── logs/            # Activity logs, audit
├── templates/           # HTML (Bootstrap 5)
├── static/              # CSS, JS, images
├── tests/               # Suite de tests
└── requirements/        # Dépendances par environnement
```

---

## 🛠️ Installation

### Prérequis
- Python 3.11+
- Redis (pour Celery)
- (Optionnel) Docker & Docker Compose

### Installation Locale

```bash
# 1. Cloner et entrer dans le projet
cd PROJECT01

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Installer les dépendances
pip install -r requirements/dev.txt

# 4. Installer les navigateurs Playwright
playwright install chromium

# 5. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (SECRET_KEY, OPENROUTER_API_KEY, etc.)

# 6. Migrer la base de données
python manage.py migrate

# 7. Créer un super-utilisateur
python manage.py createsuperuser

# 8. Lancer le serveur
python manage.py runserver
```

### Avec Docker

```bash
# Copier et configurer .env
cp .env.example .env

# Lancer tous les services
docker-compose up -d

# Accéder à l'application sur http://localhost:8000
```

### Services Docker
- **web** : Application Django (port 8000)
- **db** : PostgreSQL 16 (port 5432)
- **redis** : Redis 7 (port 6379)
- **celery_worker** : Worker Celery
- **celery_beat** : Scheduler Celery Beat

---

## ⚙️ Configuration

### Variables d'environnement (.env)

| Variable | Description | Défaut |
|---|---|---|
| `DEBUG` | Mode debug | `True` |
| `SECRET_KEY` | Clé secrète Django | `change-me` |
| `DATABASE_URL` | URL de la base de données | `sqlite:///db.sqlite3` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `OPENROUTER_API_KEY` | Clé API OpenRouter | - |
| `OPENROUTER_MODEL` | Modèle IA | `anthropic/claude-3.5-sonnet` |
| `PLAYWRIGHT_ENABLED` | Activer le rendu JS | `True` |
| `DEFAULT_REQUEST_DELAY_SECONDS` | Délai entre requêtes | `2` |
| `DATA_RETENTION_DAYS` | Jours de rétention | `365` |

---

## 🧪 Tests

```bash
# Lancer tous les tests
pytest

# Avec couverture
pytest --cov=apps --cov-report=html

# Lancer les tests d'une app spécifique
pytest apps/scraping/
pytest apps/ai_engine/
```

---

## 📊 Utilisation

### Données de démonstration

```bash
python manage.py seed_demo
```

### Lancement des tâches asynchrones

```bash
# Terminal 1 : Serveur Django
python manage.py runserver

# Terminal 2 : Worker Celery
celery -A config worker -l info

# Terminal 3 : Scheduler Celery Beat
celery -A config beat -l info
```

---

## 📖 API Documentation

Une fois le serveur lancé, accédez à :
- **Swagger UI** : `http://localhost:8000/api/docs/swagger/`
- **ReDoc** : `http://localhost:8000/api/docs/redoc/`

---

## 🔒 Politique de Scraping Responsable

DataExtract AI respecte les principes suivants :
- **robots.txt** : Toujours respecté et parsé avant extraction
- **Rate Limiting** : Délai configurable entre requêtes par domaine
- **Backoff Exponentiel** : Arrêt automatique après erreurs répétées
- **Pas de contournement** : Jamais de contournement CAPTCHA, authentification ou protections anti-bot
- **Transparence** : User-Agent identifiable, pas d'usurpation trompeuse
- **Données personnelles** : Avertissement RGPD si détection de champs sensibles

---

## 📝 Licence

Projet propriétaire — DataExtract AI © 2024
