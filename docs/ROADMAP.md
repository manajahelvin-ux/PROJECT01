# Plan de développement — TRANSCRIBE AI

Règle : une phase n'est ouverte que lorsque la précédente est vérifiée
(tests verts + application lançable).

| Phase | Contenu | Livrables | Vérification | État |
|---|---|---|---|---|
| **1** | Architecture, arborescence, config, contrats | `settings.py`, `paths.py`, `models.py`, `interfaces.py`, `exceptions.py`, `prompts.py`, logs, diagnostics, `requirements*.txt`, `.env.example`, scripts `.bat`, `.spec` | 62 tests verts, `--doctor` opérationnel | ✅ **terminée** |
| 2 | Interface PySide6 | fenêtre principale, sidebar, 5 pages, thèmes sombre/clair, notifications | l'app s'ouvre et navigue | **✅ terminée** |
| 3 | Téléchargement yt-dlp | `YouTubeProvider`, analyse d'URL, progression | analyse + téléchargement réels | **✅ terminée** |
| 4 | FFmpeg | `FFmpegAudioExtractor` → WAV 16 kHz mono | audio conforme au contrat | **✅ terminée** |
| 5 | Moteur Whisper | `FasterWhisperEngine` + registre de moteurs | transcription avec timestamps | **✅ terminée** |
| 6 | Service OpenRouter | `openrouter_service.py` : auth, timeout, retry, erreurs, parsing | tests mockés (respx) + bouton « Tester la connexion » | **✅ terminée** |
| 7 | Chunking intelligent | `chunking.py` : découpe par phrases, ordre, empreintes, cache | recomposition fidèle | **✅ terminée** |
| 8 | Nettoyage IA | `OpenRouterProcessor` : clean, structure, résumé, points clés, traduction | pipeline complet URL → texte propre | **✅ terminée** |
| 9 | Éditeur | copier/coller, rechercher/remplacer, annuler/refaire, actions IA | édition fluide | **✅ terminée** |
| 10 | Exports | TXT, DOCX professionnel, SRT, VTT | fichiers ouverts par Word / VLC | **✅ terminée** |
| 11 | SQLite + historique | modèle, dépôt, page historique (ouvrir/modifier/exporter/supprimer) | persistance entre deux lancements | **✅ terminée** |
| 12 | Traitement par lot | file d'attente, `QThreadPool`, progression par vidéo | 4 URLs traitées indépendamment | **✅ terminée** |
| 13 | Paramètres | page IA (clé masquée, modèle, température, max tokens, test), langue, thème | modification sans redémarrage | **✅ terminée** |
| 14 | Tests | couverture complète des 12 domaines demandés, OpenRouter mocké | `pytest` vert, couverture > 80 % | **✅ terminée** |
| 15 | Packaging | finalisation `.spec`, icône, FFmpeg embarqué | `dist/TranscribeAI.exe` fonctionnel | **✅ terminée** |

## Etat final

Les 15 phases sont terminees et verifiees. Chaque phase a ete validee par
des tests avant l'ouverture de la suivante.

| Indicateur | Valeur |
|---|---|
| Tests automatises | **219**, tous verts |
| Modules applicatifs | 30 |
| Analyse statique | `ruff` : aucun avertissement |
| Appels reseau dans les tests | aucun (respx + doubles) |
| Cles API dans les tests | aucune (cle factice) |

### Verifications realisees par phase

| Phase | Verification |
|---|---|
| 1 | 62 tests : configuration, contrats, prompts, redaction des secrets |
| 2 | fenetre creee hors ecran, 6 pages instanciees, navigation testee, rendu visuel controle |
| 3 | detection de source, metadonnees yt-dlp mockees, provider local reel |
| 4 | extraction FFmpeg reelle : WAV verifie a 16 kHz / mono / 16 bits |
| 5 | registre de moteurs, moteur factice, chargement paresseux du modele |
| 6 | 15 tests : 401, 403, 429 + retry, 500, timeout, reseau, JSON invalide, reponse vide |
| 7 | ordre des blocs, aucune perte de contenu, empreintes stables, cache |
| 8 | un appel par bloc, cache anti-refacturation, degradation maitrisee sur erreur |
| 9 | annuler/refaire, rechercher/remplacer, compteur de mots, signaux IA |
| 10 | 4 formats produits et relus (DOCX rouvert avec python-docx, SRT/VTT parses) |
| 11 | CRUD complet, recherche, statistiques, persistance entre deux sessions |
| 12 | file d'attente sans doublon, progression globale par source |
| 13 | ecriture du .env non destructive, cle masquee, modele librement editable |
| 14 | 219 tests, dont un parcours integral fichier → audio → texte → export → historique |
| 15 | icone generee, .spec valide, toutes les ressources declarees resolvables |

### Limite connue

L'executable `dist/TranscribeAI.exe` doit etre genere **sur une machine
Windows** (`build.bat`) : PyInstaller ne produit pas de binaire Windows
depuis Linux. Le `.spec` est complet et sa logique de collecte a ete
verifiee (ressources, icone, FFmpeg embarque, imports caches).
