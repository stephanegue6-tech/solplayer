"""Ajoute la détection/lecture de plaque à partir d'image (Module 4, cahier
des charges 3.4).

Jusqu'ici `lectures_anpr` ne recevait que des plaques déjà décodées en
amont (upstream OCR hors périmètre). Cette migration ajoute :
- `source` : distingue une lecture saisie/transmise ("manuel") d'une
  lecture obtenue par le pipeline de détection+OCR local sur image
  ("image") — voir `app/anpr_engine.py` ;
- `image_chemin` / `image_hash_sha256` : référence vers l'image source
  stockée (même mécanisme que les pièces jointes, `app/storage.py`),
  pour permettre à un agent de revérifier la lecture automatique.

Revision ID: 0004_anpr_image
Revises: 0003_chronologie
Create Date: 2026-07-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_anpr_image"
down_revision: Union[str, None] = "0003_chronologie"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lectures_anpr",
        sa.Column("source", sa.String(), nullable=False, server_default="manuel"),
    )
    op.add_column("lectures_anpr", sa.Column("image_chemin", sa.String(), nullable=True))
    op.add_column("lectures_anpr", sa.Column("image_hash_sha256", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("lectures_anpr", "image_hash_sha256")
    op.drop_column("lectures_anpr", "image_chemin")
    op.drop_column("lectures_anpr", "source")
