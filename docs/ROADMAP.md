# Plan de développement — TRANSCRIBE AI

Règle : une phase n'est ouverte que lorsque la précédente est vérifiée
(tests verts + application lançable).

| Phase | Contenu | Livrables | Vérification | État |
|---|---|---|---|---|
| **1** | Architecture, arborescence, config, contrats | `settings.py`, `paths.py`, `models.py`, `interfaces.py`, `exceptions.py`, `prompts.py`, logs, diagnostics, `requirements*.txt`, `.env.example`, scripts `.bat`, `.spec` | 62 tests verts, `--doctor` opérationnel | ✅ **terminée** |
| 2 | Interface PySide6 | fenêtre principale, sidebar, 5 pages, thèmes sombre/clair, notifications | l'app s'ouvre et navigue | à venir |
| 3 | Téléchargement yt-dlp | `YouTubeProvider`, analyse d'URL, progression | analyse + téléchargement réels | |
| 4 | FFmpeg | `FFmpegAudioExtractor` → WAV 16 kHz mono | audio conforme au contrat | |
| 5 | Moteur Whisper | `FasterWhisperEngine` + registre de moteurs | transcription avec timestamps | |
| 6 | Service OpenRouter | `openrouter_service.py` : auth, timeout, retry, erreurs, parsing | tests mockés (respx) + bouton « Tester la connexion » | |
| 7 | Chunking intelligent | `chunking.py` : découpe par phrases, ordre, empreintes, cache | recomposition fidèle | |
| 8 | Nettoyage IA | `OpenRouterProcessor` : clean, structure, résumé, points clés, traduction | pipeline complet URL → texte propre | |
| 9 | Éditeur | copier/coller, rechercher/remplacer, annuler/refaire, actions IA | édition fluide | |
| 10 | Exports | TXT, DOCX professionnel, SRT, VTT | fichiers ouverts par Word / VLC | |
| 11 | SQLite + historique | modèle, dépôt, page historique (ouvrir/modifier/exporter/supprimer) | persistance entre deux lancements | |
| 12 | Traitement par lot | file d'attente, `QThreadPool`, progression par vidéo | 4 URLs traitées indépendamment | |
| 13 | Paramètres | page IA (clé masquée, modèle, température, max tokens, test), langue, thème | modification sans redémarrage | |
| 14 | Tests | couverture complète des 12 domaines demandés, OpenRouter mocké | `pytest` vert, couverture > 80 % | |
| 15 | Packaging | finalisation `.spec`, icône, FFmpeg embarqué | `dist/TranscribeAI.exe` fonctionnel | |

## Ce qui est déjà en place (Phase 1)

- **Configuration** : priorité env > `.env` > défauts, validation stricte,
  clé API en `SecretStr`, 7 langues déclarées (fr, en, mg, es, pt, de, it).
- **Contrats** : `MediaProvider`, `AudioExtractor`, `TranscriptionEngine`,
  `WhisperTranscriptionEngine`, `AIProcessor`, `OpenRouterProcessor`,
  `TextChunker`, `Exporter` — transcription et intelligence séparées.
- **Modèles** : `MediaInfo`, `TranscriptSegment`, `TranscriptionResult`,
  `Chunk`, `AIUsage`, `AIResult`, `ProgressEvent` (6 étapes), `TranscriptionJob`.
- **Erreurs** : hiérarchie complète avec messages utilisateur, dont les
  8 cas OpenRouter exigés (401, 403, 429, 5xx, timeout, réseau, vide, JSON).
- **Prompts** : nettoyage, structuration, résumé court, résumé détaillé,
  points clés, extraction JSON, traduction — les 10 règles anti-hallucination
  sont présentes dans chacun (vérifié par test).
- **Sécurité** : rédaction automatique des secrets dans tous les logs.
- **Outillage** : `pytest`, `ruff`, `black`, `mypy`, `install.bat`,
  `run.bat`, `build.bat`, `TranscribeAI.spec`.

## Démarrage

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt    # Windows : .venv\Scripts\pip
cp .env.example .env                             # puis renseigner OPENROUTER_API_KEY
python -m transcribe_ai.main --doctor
pytest
```
