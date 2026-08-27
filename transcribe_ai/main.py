"""Point d'entree de TRANSCRIBE AI.

Phase 1 : amorce l'application (configuration, chemins, logs) et expose
un mode diagnostic en ligne de commande. L'interface graphique est
branchee en Phase 2 via `transcribe_ai.ui.app`.

Usage :
    python -m transcribe_ai.main            # lance l'application
    python -m transcribe_ai.main --doctor   # verifie l'environnement
    python -m transcribe_ai.main --version
"""

from __future__ import annotations

import argparse
import sys

from transcribe_ai import __app_name__, __version__
from transcribe_ai.config.settings import get_settings
from transcribe_ai.utils.diagnostics import run_diagnostics
from transcribe_ai.utils.logging_config import get_logger, setup_logging


def bootstrap():
    """Prepare l'environnement d'execution et retourne les parametres."""
    settings = get_settings()
    paths = settings.paths  # cree l'arborescence de travail
    setup_logging(level=settings.log_level, log_dir=paths.logs)
    logger = get_logger(__name__)
    logger.info("%s v%s - demarrage", __app_name__, __version__)
    logger.debug("Dossier de donnees : %s", paths.root)
    return settings


def _print_doctor() -> int:
    settings = bootstrap()
    report = run_diagnostics(settings)
    print(f"\n{__app_name__} v{__version__} - diagnostic de l'environnement\n")
    for check in report.checks:
        icon = "OK  " if check.ok else ("WARN" if check.optional else "FAIL")
        print(f"[{icon}] {check.name:<22} {check.detail}")
    print(f"\nDossier de donnees : {settings.paths.root}")
    print(f"Base de donnees    : {settings.resolved_database_url}")
    print(f"Cle OpenRouter     : {settings.masked_api_key}")
    print(f"Modele IA          : {settings.openrouter_model}")
    print(f"\nResultat : {'PRET' if report.ok else 'CONFIGURATION INCOMPLETE'}\n")
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="transcribe-ai", description=f"{__app_name__}")
    parser.add_argument("--version", action="store_true", help="affiche la version")
    parser.add_argument("--doctor", action="store_true", help="verifie l'environnement")
    args = parser.parse_args(argv)

    if args.version:
        print(f"{__app_name__} {__version__}")
        return 0
    if args.doctor:
        return _print_doctor()

    bootstrap()
    try:
        from transcribe_ai.ui.app import run_app  # importe seulement si l'UI existe
    except ImportError:
        print(
            f"{__app_name__} v{__version__} - socle Phase 1 operationnel.\n"
            "L'interface graphique arrive en Phase 2. "
            "Utilisez `--doctor` pour verifier votre environnement."
        )
        return 0
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
