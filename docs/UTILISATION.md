# Guide d'utilisation — TRANSCRIBE AI

## 1. Premier lancement

1. Exécutez `install.bat` (Windows). Le script crée l'environnement,
   installe les dépendances, génère votre `.env` et lance un diagnostic.
2. Lancez `run.bat`.
3. Allez dans **Paramètres → Intelligence artificielle**, collez votre clé
   OpenRouter (obtenue sur openrouter.ai), choisissez un modèle, puis
   cliquez sur **Tester la connexion**.
   - `✓ Connexion réussie` → tout est prêt.
   - `✕ Connexion impossible` → vérifiez la clé ou la connexion Internet.
4. Cliquez sur **Enregistrer les paramètres**.

> Sans clé API, l'application reste pleinement utilisable : la
> transcription fonctionne, seul le post-traitement IA est désactivé.

## 2. Transcrire une vidéo

1. Page **Transcrire**.
2. Collez une URL (`https://www.youtube.com/watch?v=…`) **ou** cliquez sur
   *Importer un fichier*.
3. Cliquez sur **Analyser** → titre, durée, auteur et langue s'affichent.
4. Choisissez la langue, et surtout le **traitement IA** :

   | Mode | Appels OpenRouter | Usage |
   |---|---|---|
   | Aucun | 0 | transcription brute, coût nul |
   | Nettoyage | 1 par bloc | ponctuation, paragraphes |
   | Nettoyage + résumé | + 2 | comptes rendus |
   | Analyse complète | + 4 | points clés, mots-clés, entités |

5. Cliquez sur **Télécharger et transcrire**. Les 6 étapes s'affichent en
   temps réel ; l'interface reste utilisable et le bouton *Annuler* est actif.

## 3. Corriger et exporter

Le texte apparaît dans l'éditeur. Vous disposez de :

- **Annuler / Refaire / Copier / Coller**
- **Rechercher / Remplacer / Tout remplacer**
- **Nettoyer avec l'IA**, **Résumer avec l'IA**, **Traduire avec l'IA**
  (langue cible à côté du bouton)

Puis exportez : **TXT**, **WORD**, **SRT**, **VTT**.

- *TXT* : le texte seul.
- *WORD* : document mis en forme (titre, source, durée, langue, date,
  résumé et points clés si disponibles, puis la transcription).
- *SRT / VTT* : sous-titres horodatés. Si le texte a été retravaillé par
  l'IA et a perdu ses timestamps, ils sont recalculés proportionnellement.

## 4. Traitement par lot

Page **Traitement par lot** : ajoutez plusieurs URLs (une par ligne) ou
plusieurs fichiers, choisissez langue et mode IA, puis **Lancer le lot**.
Chaque source progresse indépendamment ; une erreur sur l'une n'interrompt
pas les autres.

## 5. Historique

Toutes les transcriptions terminées sont enregistrées en SQLite.
Vous pouvez rechercher, **Ouvrir** (recharge le texte dans l'éditeur),
**Exporter** ou **Supprimer**.

## 6. Maîtriser les coûts

- Utilisez le mode **Aucun** pour un simple sous-titrage.
- Les blocs déjà envoyés sont mis en cache : relancer un nettoyage
  identique ne consomme rien (le compteur affiche « blocs cachés »).
- Réduisez `Taille des blocs` pour des requêtes plus petites, augmentez-la
  pour réduire leur nombre.
- **Vider le cache IA** dans les Paramètres si vous changez de stratégie.

## 7. Résolution des problèmes

| Symptôme | Cause probable | Solution |
|---|---|---|
| « FFmpeg est introuvable » | FFmpeg absent du PATH | installez-le, ou renseignez `FFMPEG_PATH`, ou gardez `imageio-ffmpeg` installé |
| « Le moteur de transcription n'est pas installé » | faster-whisper absent | `pip install faster-whisper` |
| Première transcription très lente | le modèle Whisper se télécharge | patientez, il est mis en cache ensuite |
| Erreur 401 | clé API invalide | régénérez-la sur openrouter.ai |
| Erreur 402 | crédits épuisés | rechargez votre compte OpenRouter |
| Erreur 429 | limite de débit | l'application réessaie automatiquement avec attente croissante |
| « Impossible d'analyser cette URL » | vidéo privée, géobloquée, ou yt-dlp obsolète | `pip install -U yt-dlp` |

Les journaux détaillés se trouvent dans le dossier de données affiché par
`python -m transcribe_ai.main --doctor` (sous-dossier `logs/`). Aucune clé
API n'y figure jamais.
