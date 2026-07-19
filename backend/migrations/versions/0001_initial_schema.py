"""schema initial — socle commun CrimTrack (incidents, personnes, véhicules,
preuves, chaîne de custody, relations, lectures ANPR) + utilisateurs (RBAC)
et journal d'audit.

Reproduit fidèlement le schéma généré jusqu'ici par `Base.metadata.create_all`
(cf. app/models.py) afin de servir de point de départ versionné : à partir de
cette révision, toute évolution de schéma doit passer par une nouvelle
révision Alembic plutôt que par create_all.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- utilisateurs (RBAC) ---------------------------------------------------
    op.create_table(
        "utilisateurs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("prenom", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("date_creation", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_utilisateurs_email", "utilisateurs", ["email"], unique=True)

    # -- personnes ----------------------------------------------------------------
    op.create_table(
        "personnes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("prenom", sa.String(), nullable=False),
        sa.Column("date_naissance", sa.DateTime(), nullable=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("signalement", sa.String(), nullable=True),
        sa.Column("photo_ref", sa.String(), nullable=True),
        sa.Column("statut", sa.String(), nullable=True),
    )

    # -- incidents ------------------------------------------------------------------
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("type_infraction", sa.String(), nullable=False),
        sa.Column("date_heure", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("adresse", sa.String(), nullable=True),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("gravite", sa.String(), nullable=False),
        sa.Column("unite_en_charge", sa.String(), nullable=True),
    )
    op.create_index("ix_incidents_type_infraction", "incidents", ["type_infraction"])
    op.create_index("ix_incidents_date_heure", "incidents", ["date_heure"])
    op.create_index("ix_incidents_statut", "incidents", ["statut"])

    # -- vehicules ------------------------------------------------------------------
    op.create_table(
        "vehicules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("plaque_immatriculation", sa.String(), nullable=False),
        sa.Column("marque", sa.String(), nullable=True),
        sa.Column("modele", sa.String(), nullable=True),
        sa.Column("couleur", sa.String(), nullable=True),
        sa.Column("proprietaire_id", sa.String(), sa.ForeignKey("personnes.id"), nullable=True),
        sa.Column("statut", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_vehicules_plaque_immatriculation", "vehicules", ["plaque_immatriculation"], unique=True
    )

    # -- tables de liaison plusieurs-à-plusieurs (cahier des charges 4.1) -----------
    op.create_table(
        "incident_personnes",
        sa.Column("incident_id", sa.String(), sa.ForeignKey("incidents.id"), primary_key=True),
        sa.Column("personne_id", sa.String(), sa.ForeignKey("personnes.id"), primary_key=True),
        sa.Column("role_dans_incident", sa.String(), nullable=True),
    )
    op.create_table(
        "incident_vehicules",
        sa.Column("incident_id", sa.String(), sa.ForeignKey("incidents.id"), primary_key=True),
        sa.Column("vehicule_id", sa.String(), sa.ForeignKey("vehicules.id"), primary_key=True),
    )

    # -- preuves (Module 2) -----------------------------------------------------------
    op.create_table(
        "preuves",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("incident_id", sa.String(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("hash_integrite", sa.String(), nullable=True),
        sa.Column("localisation_stockage", sa.String(), nullable=True),
    )

    # -- chaîne de custody (hash-chain, Module 2) --------------------------------------
    op.create_table(
        "chaine_custody",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("preuve_id", sa.String(), sa.ForeignKey("preuves.id"), nullable=False),
        sa.Column("personne_id", sa.String(), sa.ForeignKey("personnes.id"), nullable=False),
        sa.Column("date_heure", sa.DateTime(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("horodatage_hash", sa.String(), nullable=True),
    )

    # -- relations (Module 3) -----------------------------------------------------------
    op.create_table(
        "relations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("personne_a_id", sa.String(), sa.ForeignKey("personnes.id"), nullable=False),
        sa.Column("personne_b_id", sa.String(), sa.ForeignKey("personnes.id"), nullable=False),
        sa.Column("type_relation", sa.String(), nullable=False),
        sa.Column("source_incident_id", sa.String(), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("poids", sa.Integer(), nullable=False),
    )

    # -- lectures ANPR (Module 4) ---------------------------------------------------------
    op.create_table(
        "lectures_anpr",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("plaque_lue", sa.String(), nullable=False),
        sa.Column("date_heure", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("camera_id", sa.String(), nullable=True),
        sa.Column("confiance_ocr", sa.Float(), nullable=True),
        sa.Column("vehicule_id", sa.String(), sa.ForeignKey("vehicules.id"), nullable=True),
    )
    op.create_index("ix_lectures_anpr_plaque_lue", "lectures_anpr", ["plaque_lue"])

    # -- journal d'audit (cahier des charges 2.2 / 4.3 / 6.2) --------------------------
    op.create_table(
        "journal_audit",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("utilisateur_id", sa.String(), sa.ForeignKey("utilisateurs.id"), nullable=True),
        sa.Column("utilisateur_email", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("ressource_type", sa.String(), nullable=False),
        sa.Column("ressource_id", sa.String(), nullable=True),
        sa.Column("date_heure", sa.DateTime(), nullable=False),
        sa.Column("details", sa.String(), nullable=True),
        sa.Column("adresse_ip", sa.String(), nullable=True),
    )
    op.create_index("ix_journal_audit_action", "journal_audit", ["action"])
    op.create_index("ix_journal_audit_ressource_type", "journal_audit", ["ressource_type"])
    op.create_index("ix_journal_audit_ressource_id", "journal_audit", ["ressource_id"])
    op.create_index("ix_journal_audit_date_heure", "journal_audit", ["date_heure"])


def downgrade() -> None:
    op.drop_table("journal_audit")
    op.drop_table("lectures_anpr")
    op.drop_table("relations")
    op.drop_table("chaine_custody")
    op.drop_table("preuves")
    op.drop_table("incident_vehicules")
    op.drop_table("incident_personnes")
    op.drop_table("vehicules")
    op.drop_table("incidents")
    op.drop_table("personnes")
    op.drop_table("utilisateurs")
