# TRANSCRIBE AI

Application desktop (PySide6) de transcription vidéo/audio, enrichie par
**OpenRouter** : coller une URL YouTube ou importer un fichier local,
obtenir une transcription nettoyée, structurée, résumée, puis l'exporter
en TXT, DOCX, SRT ou VTT.

**Les 15 phases de développement sont terminées** — voir [docs/ROADMAP.md](docs/ROADMAP.md).
219 tests automatisés, aucun appel réseau réel ni clé API dans les tests.

## Pipeline

```
URL / fichier → yt-dlp → FFmpeg → WAV 16 kHz → Whisper → texte brut
             → chunking → OpenRouter (nettoyage, résumé, points clés)
             → éditeur → export TXT / DOCX / SRT / VTT + historique SQLite
```

## Installation rapide (Windows)

```bat
install.bat      :: crée .venv, installe tout, crée .env, lance le diagnostic
run.bat          :: démarre l'application
build.bat        :: génère dist\TranscribeAI.exe
```

Puis ouvrez **Paramètres → Intelligence artificielle**, collez votre clé
OpenRouter et cliquez sur **Tester la connexion**.

### Linux / macOS

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/python -m transcribe_ai.main --doctor   # vérifie l'environnement
.venv/bin/python -m transcribe_ai.main            # lance l'interface
```

## Fonctionnalités

| Domaine | Détail |
|---|---|
| **Sources** | URL YouTube et ~1800 sites via yt-dlp ; fichiers MP4, MKV, AVI, MOV, WEBM, MP3, WAV, M4A, FLAC, OGG |
| **Transcription** | moteur local faster-whisper (l'audio ne quitte jamais la machine), segments horodatés |
| **IA** | OpenRouter : nettoyage, structuration, résumé court/détaillé, points clés, extraction, traduction |
| **Maîtrise des coûts** | 4 niveaux de traitement (dont « aucun »), chunking configurable, cache anti-refacturation, compteur d'appels |
| **Éditeur** | copier/coller, rechercher/remplacer, annuler/refaire, actions IA |
| **Exports** | TXT, DOCX (document professionnel), SRT, VTT |
| **Historique** | SQLite : ouvrir, rechercher, exporter, supprimer |
| **Lot** | plusieurs URLs/fichiers traités indépendamment en parallèle |
| **Interface** | thèmes sombre et clair, notifications, progression en 6 étapes, jamais figée |
| **Langues** | auto, français, anglais, malagasy, espagnol, portugais, allemand, italien |

## Configuration

Tout se règle par variables d'environnement ou par `.env` (modèle dans
`.env.example`) — **aucune clé n'est jamais écrite dans le code** :

```
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
AI_TEMPERATURE=0.2
AI_MAX_TOKENS=4096
CHUNK_SIZE=6000
```

Le modèle n'est jamais codé en dur : champ libre dans la page Paramètres,
qui réécrit le `.env` sans toucher au code.

## Sécurité

- `.env` est ignoré par Git ; seul `.env.example` (vide) est versionné.
- La clé est un `SecretStr` : absente de `repr()`, des dumps et de l'UI
  (affichage masqué `sk-or-************abcd`).
- Un filtre de rédaction masque tout secret dans les journaux — testé.
- Les tests utilisent une clé factice ; les appels HTTP sont mockés (respx).

## Tests

```bash
pytest                              # 219 tests
pytest --cov=transcribe_ai          # couverture
QT_QPA_PLATFORM=offscreen pytest    # sans affichage (CI)
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — architecture, choix techniques, sécurité, coûts
- [docs/ROADMAP.md](docs/ROADMAP.md) — état des 15 phases
- [docs/UTILISATION.md](docs/UTILISATION.md) — guide d'utilisation pas à pas
