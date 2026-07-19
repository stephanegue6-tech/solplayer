"""Point d'entrée utilisé UNIQUEMENT pour le paquet desktop Windows.

Différences avec `uvicorn app.main:app --reload` (usage serveur classique) :

1. Auto-seed au premier lancement : si la base est vide (aucun compte
   utilisateur), crée le jeu de données de démonstration — un utilisateur
   qui installe l'appli desktop n'a pas de terminal pour lancer
   `python -m app.seed` lui-même.
2. Chemins pilotés entièrement par variables d'environnement injectées par
   Electron (voir crimtrack-desktop/electron/main.js) : base SQLite et
   pièces jointes dans le dossier de données utilisateur Windows
   (`%APPDATA%\\CrimTrack`), jamais dans le dossier d'installation
   (souvent en lecture seule sous `Program Files`).
3. Pas de `--reload` : inutile hors développement, et incompatible avec un
   exécutable PyInstaller figé.

Ce fichier n'est pas utilisé par `docker-compose.yml` ni par le
déploiement serveur classique — ceux-ci continuent d'utiliser
`app.main:app` directement.
"""

import os

import uvicorn

from app.database import SessionLocal
from app.models import Utilisateur


def _needs_seed() -> bool:
    db = SessionLocal()
    try:
        return db.query(Utilisateur).first() is None
    finally:
        db.close()


def main():
    # Importé ici (après lecture des variables d'environnement par
    # database.py) pour que DATABASE_URL soit déjà positionné par Electron
    # au moment où l'engine SQLAlchemy est construit.
    from app.main import app  # noqa: E402  (import tardif volontaire)

    if _needs_seed():
        from app.seed import seed

        seed()

    port = int(os.getenv("CRIMTRACK_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
