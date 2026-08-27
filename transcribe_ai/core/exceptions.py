"""Hierarchie d'exceptions de TRANSCRIBE AI.

Chaque couche leve une exception typee ; l'UI se contente de mapper
`TranscribeAIError.user_message` vers une notification lisible.
"""

from __future__ import annotations


class TranscribeAIError(Exception):
    """Exception de base. Porte un message technique et un message utilisateur.

    `message` reste technique (journaux, debogage) ; `user_message` est le
    seul texte montre a l'utilisateur. Lorsqu'une sous-classe definit un
    message dedie, celui-ci prime sur le detail technique, qui serait
    incomprehensible dans une notification.
    """

    default_user_message = "Une erreur inattendue est survenue."

    def __init__(self, message: str = "", *, user_message: str | None = None) -> None:
        super().__init__(message or self.default_user_message)
        self.detail = message
        if user_message:
            self.user_message = user_message
        elif type(self).default_user_message != TranscribeAIError.default_user_message:
            self.user_message = self.default_user_message
        else:
            self.user_message = message or self.default_user_message


# --- Configuration ---------------------------------------------------------
class ConfigurationError(TranscribeAIError):
    default_user_message = "Configuration invalide. Verifiez vos parametres."


class MissingAPIKeyError(ConfigurationError):
    default_user_message = (
        "Aucune cle API OpenRouter n'est configuree. "
        "Renseignez-la dans Parametres > Intelligence artificielle."
    )


class MissingDependencyError(ConfigurationError):
    default_user_message = "Une dependance requise est introuvable (FFmpeg, yt-dlp...)."


# --- Acquisition media -----------------------------------------------------
class MediaError(TranscribeAIError):
    default_user_message = "Impossible de traiter ce media."


class InvalidURLError(MediaError):
    default_user_message = "L'URL fournie n'est pas valide ou n'est pas supportee."


class DownloadError(MediaError):
    default_user_message = "Le telechargement de la video a echoue."


class UnsupportedFormatError(MediaError):
    default_user_message = "Ce format de fichier n'est pas pris en charge."


class FFmpegError(MediaError):
    default_user_message = "L'extraction audio via FFmpeg a echoue."


# --- Transcription ---------------------------------------------------------
class TranscriptionError(TranscribeAIError):
    default_user_message = "La transcription a echoue."


class EngineNotAvailableError(TranscriptionError):
    default_user_message = "Le moteur de transcription selectionne n'est pas disponible."


# --- IA / OpenRouter -------------------------------------------------------
class AIError(TranscribeAIError):
    default_user_message = "Le traitement par l'IA a echoue."


class OpenRouterError(AIError):
    """Erreur renvoyee par l'API OpenRouter."""

    default_user_message = "Erreur de communication avec OpenRouter."

    def __init__(
        self,
        message: str = "",
        *,
        status_code: int | None = None,
        user_message: str | None = None,
    ) -> None:
        super().__init__(message, user_message=user_message)
        self.status_code = status_code


class AuthenticationError(OpenRouterError):
    default_user_message = "Cle API OpenRouter invalide ou revoquee (401)."


class PermissionDeniedError(OpenRouterError):
    default_user_message = "Acces refuse par OpenRouter (403). Modele ou credits indisponibles."


class RateLimitError(OpenRouterError):
    default_user_message = "Limite de requetes atteinte (429). Nouvelle tentative en cours."


class ServerError(OpenRouterError):
    default_user_message = "OpenRouter rencontre un probleme serveur (5xx)."


class AITimeoutError(OpenRouterError):
    default_user_message = "Le delai d'attente de la requete IA est depasse."


class NetworkError(OpenRouterError):
    default_user_message = "Aucune connexion Internet disponible."


class EmptyResponseError(OpenRouterError):
    default_user_message = "L'IA a renvoye une reponse vide."


class InvalidResponseError(OpenRouterError):
    default_user_message = "La reponse de l'IA est illisible (JSON invalide)."


# --- Persistance / export --------------------------------------------------
class StorageError(TranscribeAIError):
    default_user_message = "Erreur d'acces a la base de donnees."


class ExportError(TranscribeAIError):
    default_user_message = "L'export du document a echoue."
