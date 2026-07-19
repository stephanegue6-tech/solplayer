"""Corrections suite à l'audit du cahier des charges :

- active l'extension PostGIS (production uniquement, sans effet sur SQLite) ;
- corrige chaine_custody : la garde d'une preuve doit être attribuée à un
  agent (`utilisateurs`), pas à un suspect/témoin (`personnes`) — renomme
  `personne_id` en `utilisateur_id` et change la clé étrangère en
  conséquence ;
- ajoute la table `pieces_jointes` (fichiers rattachés à une preuve) ;
- ajoute `refresh_tokens` et `revoked_access_tokens` (révocation/rotation
  des JWT, absente jusqu'ici).

⚠️ Sur une base déjà en production avec des événements de custody existants :
la colonne renommée conservera les anciennes valeurs (des `personne_id`),
qui ne correspondront plus à de vrais `utilisateurs.id` après cette
migration. Il n'existe pas de correspondance fiable et automatique entre
« qui était le suspect/témoin » et « quel agent a réellement manipulé la
preuve » : une reprise de données manuelle est nécessaire pour les
événements historiques si ce cas se présente. Sur un environnement de
développement/démo, il est plus simple de repartir d'une base vierge.

Revision ID: 0002_corrections_audit
Revises: 0001_initial_schema
Create Date: 2026-07-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_corrections_audit"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # -- chaine_custody : personne_id -> utilisateur_id -----------------------
    with op.batch_alter_table("chaine_custody") as batch_op:
        if is_postgres:
            batch_op.drop_constraint("chaine_custody_personne_id_fkey", type_="foreignkey")
        batch_op.alter_column("personne_id", new_column_name="utilisateur_id")
        batch_op.create_foreign_key(
            "chaine_custody_utilisateur_id_fkey",
            "utilisateurs",
            ["utilisateur_id"],
            ["id"],
        )

    # -- pieces_jointes ---------------------------------------------------------
    op.create_table(
        "pieces_jointes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("preuve_id", sa.String(), sa.ForeignKey("preuves.id"), nullable=False),
        sa.Column("nom_fichier", sa.String(), nullable=False),
        sa.Column("chemin_stockage", sa.String(), nullable=False),
        sa.Column("type_mime", sa.String(), nullable=True),
        sa.Column("taille_octets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hash_sha256", sa.String(), nullable=False),
        sa.Column("ajoute_par_id", sa.String(), sa.ForeignKey("utilisateurs.id"), nullable=True),
        sa.Column("date_ajout", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pieces_jointes_preuve_id", "pieces_jointes", ["preuve_id"])

    # -- refresh_tokens -----------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("utilisateur_id", sa.String(), sa.ForeignKey("utilisateurs.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("date_creation", sa.DateTime(), nullable=False),
        sa.Column("date_expiration", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_refresh_tokens_utilisateur_id", "refresh_tokens", ["utilisateur_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # -- revoked_access_tokens -----------------------------------------------
    op.create_table(
        "revoked_access_tokens",
        sa.Column("jti", sa.String(), primary_key=True),
        sa.Column("date_expiration", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("revoked_access_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_utilisateur_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_pieces_jointes_preuve_id", table_name="pieces_jointes")
    op.drop_table("pieces_jointes")

    with op.batch_alter_table("chaine_custody") as batch_op:
        batch_op.drop_constraint("chaine_custody_utilisateur_id_fkey", type_="foreignkey")
        batch_op.alter_column("utilisateur_id", new_column_name="personne_id")
        batch_op.create_foreign_key(
            "chaine_custody_personne_id_fkey", "personnes", ["personne_id"], ["id"]
        )
