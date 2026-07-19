"""Stockage sur disque des pièces jointes rattachées aux preuves (Module 2,
cahier des charges 3.2 : "fiche d'affaire centralisée : témoins, preuves,
pièces jointes, chronologie").

Principes :
- le fichier est écrit sous un nom généré (UUID), jamais sous le nom fourni
  par le client, pour éviter toute traversée de répertoire (path traversal)
  ou collision ;
- les métadonnées (nom d'origine, type MIME, taille) sont conservées en
  base (`app.models.PieceJointe`), pas dans le nom de fichier ;
- un hash SHA-256 du contenu est calculé à l'écriture et revérifié à la
  lecture pour détecter toute altération — même logique d'intégrité que la
  chaîne de custody (`app/routers/preuves.py`) ;
- une taille maximale et une liste blanche de types MIME sont appliquées
  pour limiter la surface d'attaque (fichiers exécutables, dépassement de
  quota disque).
"""

import hashlib
import os
import uuid
from pathlib import Path
from typing import BinaryIO, Tuple

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage/pieces_jointes")).resolve()

# Types de pièces versées à un dossier d'enquête : documents, images,
# audio/vidéo d'exploitation courante. Volontairement restrictif — pas
# d'exécutables, de scripts ni d'archives (vecteurs classiques de malware).
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
    "audio/mpeg",
    "audio/wav",
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/x-matroska",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024


class FichierTropVolumineux(Exception):
    pass


class TypeFichierNonAutorise(Exception):
    pass


def _ensure_storage_dir() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(file_obj: BinaryIO, *, content_type: str, chunk_size: int = 1024 * 1024) -> Tuple[str, str, int]:
    """Écrit le contenu sur disque sous un nom généré.

    Retourne (chemin_stockage, hash_sha256, taille_octets). Lève
    `TypeFichierNonAutorise` ou `FichierTropVolumineux` sans laisser de
    fichier partiel sur disque.
    """
    if content_type not in ALLOWED_MIME_TYPES:
        raise TypeFichierNonAutorise(f"Type de fichier non autorisé : {content_type}")

    _ensure_storage_dir()
    nom_stockage = f"{uuid.uuid4()}.bin"
    chemin = STORAGE_DIR / nom_stockage

    hasher = hashlib.sha256()
    taille = 0
    try:
        with open(chemin, "wb") as out:
            while True:
                chunk = file_obj.read(chunk_size)
                if not chunk:
                    break
                taille += len(chunk)
                if taille > MAX_UPLOAD_BYTES:
                    raise FichierTropVolumineux(
                        f"Fichier trop volumineux (max {MAX_UPLOAD_BYTES // (1024 * 1024)} Mo)"
                    )
                hasher.update(chunk)
                out.write(chunk)
    except Exception:
        # Ne jamais laisser de fichier partiel/corrompu sur disque.
        chemin.unlink(missing_ok=True)
        raise

    return str(chemin.relative_to(STORAGE_DIR)), hasher.hexdigest(), taille


def resolve_path(chemin_stockage: str) -> Path:
    """Résout un chemin stocké en base vers un chemin absolu, en s'assurant
    qu'il reste bien à l'intérieur de STORAGE_DIR (défense en profondeur
    contre un chemin corrompu/malveillant en base)."""
    candidate = (STORAGE_DIR / chemin_stockage).resolve()
    if STORAGE_DIR not in candidate.parents and candidate != STORAGE_DIR:
        raise ValueError("Chemin de stockage invalide")
    return candidate


def verify_integrity(chemin_stockage: str, hash_attendu: str) -> bool:
    """Recalcule le hash du fichier sur disque et le compare à celui
    enregistré en base — détecte une altération du fichier après coup."""
    chemin = resolve_path(chemin_stockage)
    if not chemin.is_file():
        return False
    hasher = hashlib.sha256()
    with open(chemin, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest() == hash_attendu


def delete_file(chemin_stockage: str) -> None:
    chemin = resolve_path(chemin_stockage)
    chemin.unlink(missing_ok=True)
