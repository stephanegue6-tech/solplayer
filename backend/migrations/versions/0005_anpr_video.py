"""Ajoute la détection/lecture de plaque à partir de vidéo/flux caméra
(Module 4, cahier des charges 3.4 — "détection/lecture réelle de plaque sur
image OU VIDÉO", partie vidéo).

Ajoute à `lectures_anpr` :
- `video_chemin` : référence vers le fichier vidéo source stocké (même
  mécanisme que les pièces jointes et que `image_chemin`, `app/storage.py`)
  quand la lecture provient d'une vidéo téléversée. Reste NULL pour une
  lecture obtenue depuis un flux caméra en direct (non stocké tel quel,
  voir `app/anpr_engine.detecter_plaques_video`) ou une lecture
  manuelle/image.
- `video_timestamp_s` : position (en secondes) dans la vidéo/le flux à
  laquelle la plaque a été lue, pour permettre à un agent de resituer la
  lecture dans son contexte.

Revision ID: 0005_anpr_video
Revises: 0004_anpr_image
Create Date: 2026-07-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_anpr_video"
down_revision: Union[str, None] = "0004_anpr_image"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lectures_anpr", sa.Column("video_chemin", sa.String(), nullable=True))
    op.add_column("lectures_anpr", sa.Column("video_timestamp_s", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("lectures_anpr", "video_timestamp_s")
    op.drop_column("lectures_anpr", "video_chemin")
