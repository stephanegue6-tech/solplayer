"""Ajoute la chronologie des faits (Module 2, cahier des charges 3.2).

Jusqu'ici, la "fiche d'affaire" (incident) ne disposait pas d'objet dédié
pour documenter le déroulé des faits (dépositions, constatations, actes
d'enquête) — seules les dates de l'incident et de la chaîne de custody
existaient. Cette migration crée `evenements_chronologie`, rattachée à un
incident, pour la partie saisie manuellement ; les événements déjà tracés
ailleurs (chaîne de custody, pièces jointes) restent dans leurs tables
d'origine et sont fusionnés à la volée par l'API (voir
`GET /incidents/{id}/chronologie`) plutôt que dupliqués ici.

Revision ID: 0003_chronologie
Revises: 0002_corrections_audit
Create Date: 2026-07-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_chronologie"
down_revision: Union[str, None] = "0002_corrections_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evenements_chronologie",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("incident_id", sa.String(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("date_heure", sa.DateTime(), nullable=False),
        sa.Column("titre", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("origine", sa.String(), nullable=False, server_default="manuel"),
        sa.Column("ressource_type", sa.String(), nullable=True),
        sa.Column("ressource_id", sa.String(), nullable=True),
        sa.Column("auteur_id", sa.String(), sa.ForeignKey("utilisateurs.id"), nullable=True),
        sa.Column("date_creation", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_evenements_chronologie_incident_id", "evenements_chronologie", ["incident_id"])
    op.create_index("ix_evenements_chronologie_date_heure", "evenements_chronologie", ["date_heure"])


def downgrade() -> None:
    op.drop_index("ix_evenements_chronologie_date_heure", table_name="evenements_chronologie")
    op.drop_index("ix_evenements_chronologie_incident_id", table_name="evenements_chronologie")
    op.drop_table("evenements_chronologie")
