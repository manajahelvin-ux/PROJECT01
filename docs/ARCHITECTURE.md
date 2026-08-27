# TRANSCRIBE AI — Architecture technique (Phase 1)

## 1. Principe directeur

Trois responsabilités strictement séparées, reliées uniquement par des
contrats abstraits (`transcribe_ai/core/interfaces.py`) :

| Responsabilité | Où | Remplaçable par |
|---|---|---|
| **Acquisition** (URL / fichier → WAV 16 kHz) | `MediaProvider`, `AudioExtractor` | tout téléchargeur / tout convertisseur |
| **Transcription** (locale, hors ligne) | `TranscriptionEngine` | Whisper, faster-whisper, API distante |
| **Intelligence** (post-traitement du texte) | `AIProcessor` | OpenRouter, autre fournisseur |

Conséquence : changer de moteur Whisper ou de fournisseur IA n'impacte
ni le pipeline, ni l'UI, ni les exports.

## 2. Flux de bout en bout

```
SOURCE (URL ou fichier local)
      ↓  MediaProvider.analyze()      → MediaInfo (titre, durée, auteur, langue)
      ↓  MediaProvider.fetch()        → fichier média local
      ↓  AudioExtractor.extract()     → WAV 16 kHz / mono / pcm_s16le
      ↓  TranscriptionEngine.transcribe() → TranscriptionResult (texte + segments horodatés)
      ↓  TextChunker.split()          → [Chunk] ordonnés, empreintés (hash)
      ↓  AIProcessor.clean()          → appels OpenRouter, 1 par chunk non caché
      ↓  TextChunker.merge()          → AIResult (texte propre, résumés, points clés)
      ↓  Éditeur                      → corrections manuelles
      ↓  Exporter                     → TXT / DOCX / SRT / VTT
      ↓  Repository                   → historique SQLite
```

## 3. Arborescence

```
PROJECT01/
├── transcribe_ai/
│   ├── main.py                 # point d'entrée + mode --doctor
│   ├── config/
│   │   ├── settings.py         # Settings pydantic (env > .env > défauts)
│   │   └── paths.py            # dossiers utilisateur, compatible PyInstaller
│   ├── core/
│   │   ├── models.py           # MediaInfo, TranscriptionResult, Chunk, AIResult, Job…
│   │   ├── interfaces.py       # contrats abstraits de toutes les couches
│   │   ├── exceptions.py       # hiérarchie d'erreurs + messages utilisateur
│   │   ├── engines/            # Phase 5 : moteurs de transcription
│   │   ├── ai/
│   │   │   ├── prompts.py      # bibliothèque de prompts système (Phase 1 ✔)
│   │   │   ├── openrouter_service.py   # Phase 6
│   │   │   ├── chunking.py     # Phase 7
│   │   │   └── processor.py    # Phase 8 : OpenRouterProcessor
│   │   └── pipeline/           # Phases 3-4 (downloader, ffmpeg) + orchestrateur
│   ├── io/
│   │   ├── database.py, repository.py  # Phase 11 : SQLite / SQLAlchemy
│   │   └── exporters/          # Phase 10 : txt, docx, srt, vtt
│   ├── ui/
│   │   ├── app.py, main_window.py
│   │   ├── pages/              # accueil, transcription, historique, paramètres, à propos
│   │   ├── widgets/            # sidebar, cards, badges, progression, notifications
│   │   └── theme/              # thèmes sombre / clair
│   ├── utils/
│   │   ├── logging_config.py   # logs + rédaction automatique des secrets
│   │   └── diagnostics.py      # vérification de l'environnement
│   └── resources/              # icônes, QSS
├── tests/                      # 62 tests dès la Phase 1
├── docs/                       # ARCHITECTURE.md, ROADMAP.md
├── requirements.txt / requirements-dev.txt
├── .env.example                # .env est ignoré par Git
├── install.bat / run.bat / build.bat
└── TranscribeAI.spec           # PyInstaller → dist/TranscribeAI.exe
```

## 4. Choix techniques justifiés

| Choix | Raison |
|---|---|
| **faster-whisper** par défaut | 4× plus rapide que `openai-whisper` sur CPU, empreinte mémoire réduite, sortie déjà segmentée avec timestamps (indispensable pour SRT/VTT). Le contrat `TranscriptionEngine` permet de basculer sur un autre moteur. |
| **httpx** plutôt que requests | timeouts granulaires (connect/read/write), HTTP/2, client réutilisable, API async disponible plus tard sans réécriture. |
| **pydantic-settings** | validation stricte des paramètres, `SecretStr` pour la clé API, priorité env > `.env` > défauts, sans code de parsing maison. |
| **SQLAlchemy + SQLite** | schéma versionnable, requêtes typées pour l'historique, aucun serveur à installer, fichier unique dans le dossier utilisateur. |
| **QThreadPool + QRunnable** | l'interface ne se bloque jamais ; le mode lot (Phase 12) réutilise le même pool avec une concurrence configurable. |
| **Dossier de données utilisateur** | `%APPDATA%/TranscribeAI` — l'exécutable ne tente jamais d'écrire dans `Program Files`, ce qui casserait l'app sous Windows. |

## 5. Sécurité de la clé API

1. Jamais en dur dans le code — uniquement `.env` ou variable d'environnement.
2. `.env` est dans `.gitignore` ; seul `.env.example` (vide) est versionné.
3. En mémoire, la clé est un `SecretStr` : elle n'apparaît ni dans `repr()`,
   ni dans `model_dump()`, ni dans `safe_dump()`.
4. Tous les handlers de log portent un `RedactingFilter` qui masque
   `sk-or-v1-…`, `Bearer …` et `api_key: …` — testé explicitement.
5. L'UI affiche uniquement `masked_api_key` (`sk-or-************abcd`).
6. Les tests utilisent une clé factice et n'accèdent jamais au réseau.

## 6. Maîtrise des coûts OpenRouter

- Mode IA configurable : `none` / `clean` / `clean_summary` / `full`.
- Chunking à taille configurable (`CHUNK_SIZE`, défaut 6000 caractères).
- Chaque `Chunk` porte une empreinte (hash) : un bloc déjà traité est relu
  depuis le cache disque plutôt que refacturé.
- `AIUsage` compte appels, chunks cachés et tokens → affiché dans l'UI
  (« Chunks traités : 12/12 — Appels IA : 12 »).
- Découpage aux frontières de phrases pour éviter de payer deux fois
  la reformulation d'une phrase coupée.

## 7. Gestion des erreurs

Chaque code HTTP OpenRouter est mappé sur une exception dédiée
(`AuthenticationError` 401, `PermissionDeniedError` 403, `RateLimitError` 429,
`ServerError` 5xx, plus timeout, réseau, réponse vide, JSON invalide).
Toutes dérivent de `TranscribeAIError` et exposent un `user_message`
directement affichable. Le 429 déclenche un retry à backoff exponentiel
(`AI_MAX_RETRIES`, `AI_RETRY_BACKOFF`).

## 8. Contrat audio

Le pipeline impose un format unique en entrée du moteur de transcription :
**WAV, 16 000 Hz, mono, `pcm_s16le`** (constantes dans `config/settings.py`).
Toute source — MP4, MKV, AVI, MOV, WEBM, MP3, WAV, M4A, FLAC, OGG — converge
vers ce format, ce qui rend les moteurs interchangeables.
