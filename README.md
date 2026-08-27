# TRANSCRIBE AI

Application desktop (PySide6) de transcription vidéo/audio, enrichie par
**OpenRouter** : coller une URL YouTube ou importer un fichier local,
obtenir une transcription nettoyée, structurée, résumée, puis l'exporter
en TXT, DOCX, SRT ou VTT.

> **État actuel : Phase 1 terminée** — architecture, contrats, configuration,
> sécurité et outillage. L'interface graphique arrive en Phase 2
> (voir [docs/ROADMAP.md](docs/ROADMAP.md)).

## Pipeline

```
URL / fichier → yt-dlp → FFmpeg → WAV 16 kHz → Whisper → texte brut
             → chunking → OpenRouter (nettoyage, résumé, points clés)
             → éditeur → export TXT / DOCX / SRT / VTT + historique SQLite
```

## Installation

**Windows**

```bat
install.bat
run.bat
```

**Linux / macOS**

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # renseigner OPENROUTER_API_KEY
.venv/bin/python -m transcribe_ai.main --doctor
```

`--doctor` liste précisément ce qui manque (FFmpeg, yt-dlp, moteur Whisper,
clé API) avant même de lancer l'interface.

## Configuration

Tout se règle par variables d'environnement ou par le fichier `.env`
(modèle dans `.env.example`) — **aucune clé n'est jamais écrite dans le code** :

```
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
AI_TEMPERATURE=0.2
AI_MAX_TOKENS=4096
CHUNK_SIZE=6000
```

Le modèle OpenRouter n'est jamais codé en dur : il se change dans `.env`
ou depuis la page Paramètres.

## Sécurité

- `.env` est ignoré par Git ; seul `.env.example` (vide) est versionné.
- La clé est stockée en `SecretStr` : absente de `repr()`, des dumps et de l'UI
  (affichage masqué `sk-or-************abcd`).
- Un filtre de rédaction masque tout secret dans les journaux — testé.
- Les tests n'utilisent qu'une clé factice et aucun appel réseau réel.

## Tests

```bash
pytest                      # 62 tests (Phase 1)
pytest --cov=transcribe_ai
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — architecture, choix techniques, sécurité, coûts
- [docs/ROADMAP.md](docs/ROADMAP.md) — plan des 15 phases
