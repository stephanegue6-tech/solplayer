"""Peuple la base avec un jeu de données de démonstration.

Usage :
    python -m app.seed

Les personnes/véhicules/relations reprennent la même trame que le jeu de
données factice du frontend (src/relationsApi.js) afin que la démo "vraie
API" et la démo "mode hors-ligne" du frontend racontent la même histoire.

Crée également un compte par rôle RBAC (cf. cahier des charges 4.3) pour
pouvoir tester immédiatement /auth/login, ainsi que quelques preuves/
chaîne de custody/lectures ANPR pour illustrer les Modules 2 et 4.
"""

import hashlib
import os
from datetime import datetime, timedelta

from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import (
    ChaineCustody,
    Incident,
    LectureAnpr,
    Personne,
    Preuve,
    Relation,
    Utilisateur,
    Vehicule,
)

PERSONNES = [
    ("Marchal", "Damien", "suspect"),
    ("Ilhem", "Karim", "suspect"),
    ("Voss", "Romane", "témoin"),
    ("Nadeau", "Sacha", "suspect"),
    ("Okoye", "Tobi", "victime"),
    ("Lefort", "Manon", "suspect"),
    ("Benali", "Amine", "témoin"),
    ("Petit", "Julie", "suspect"),
]

VEHICULES = [
    ("AB-123-CD", "Marchal", "normal"),
    ("EF-456-GH", "Nadeau", "normal"),
    ("IJ-789-KL", "Petit", "volé"),  # sert à démontrer l'alerte ANPR
]

RELATIONS = [
    ("Marchal", "Ilhem", "complice", 8),
    ("Marchal", "Voss", "connaissance", 3),
    ("Ilhem", "Nadeau", "famille", 9),
    ("Nadeau", "Okoye", "affaire_commune", 5),
    ("Ilhem", "Lefort", "vu_avec", 4),
    ("Lefort", "Benali", "connaissance", 2),
    ("Lefort", "Petit", "complice", 7),
    ("Petit", "Voss", "affaire_commune", 3),
]

INCIDENTS = [
    ("vol", "faible", "ouvert"),
    ("cambriolage", "moyenne", "en_cours"),
    ("trafic", "haute", "ouvert"),
    ("vandalisme", "faible", "clos"),
    ("agression", "critique", "en_cours"),
    # Grappe supplémentaire resserrée géographiquement pour illustrer
    # /incidents/analyse/hotspots (les 3 incidents ci-dessous sont à
    # quelques dizaines de mètres les uns des autres).
    ("vol", "faible", "ouvert"),
    ("vol", "moyenne", "ouvert"),
]

# Comptes de démonstration — un par rôle RBAC. Le mot de passe par défaut
# DOIT être changé avant tout usage réel ; il peut être surchargé via la
# variable d'environnement SEED_ADMIN_PASSWORD.
UTILISATEURS = [
    ("admin@crimtrack.local", "administrateur", "Admin", "CrimTrack"),
    ("opj@crimtrack.local", "opj", "Diallo", "Fatou"),
    ("enqueteur@crimtrack.local", "enqueteur", "Bernard", "Léo"),
    ("analyste@crimtrack.local", "analyste", "Costa", "Inès"),
]
DEFAULT_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe123!")

GENESIS = "GENESIS"


def _hash(previous_hash, preuve_id, utilisateur_id, action, date_heure):
    payload = f"{previous_hash}|{preuve_id}|{utilisateur_id}|{action}|{date_heure.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Personne).first():
            print("La base contient déjà des données — seed ignoré.")
            return

        # -- Utilisateurs (RBAC) ------------------------------------------------
        utilisateurs_by_email = {}
        for email, role, nom, prenom in UTILISATEURS:
            u = Utilisateur(
                email=email,
                hashed_password=hash_password(DEFAULT_PASSWORD),
                nom=nom,
                prenom=prenom,
                role=role,
            )
            db.add(u)
            utilisateurs_by_email[email] = u
        db.flush()

        # -- Personnes ------------------------------------------------------------
        personnes_by_nom = {}
        for nom, prenom, role in PERSONNES:
            p = Personne(nom=nom, prenom=prenom, role=role, statut="actif")
            db.add(p)
            personnes_by_nom[nom] = p
        db.flush()

        # -- Véhicules --------------------------------------------------------------
        vehicules_by_plaque = {}
        for plaque, proprietaire_nom, statut in VEHICULES:
            v = Vehicule(
                plaque_immatriculation=plaque,
                proprietaire_id=personnes_by_nom[proprietaire_nom].id,
                statut=statut,
            )
            db.add(v)
            vehicules_by_plaque[plaque] = v
        db.flush()

        # -- Incidents ----------------------------------------------------------------
        incidents = []
        base_lat, base_lon = 48.8566, 2.3522
        for i, (type_infraction, gravite, statut) in enumerate(INCIDENTS):
            if i < 5:
                lat = base_lat + (i - 2) * 0.01
                lon = base_lon + (i - 2) * 0.01
            else:
                # Grappe resserrée (~50-100m) pour peupler un hotspot évident.
                lat = base_lat + 0.05 + (i - 5) * 0.0003
                lon = base_lon + 0.05 + (i - 5) * 0.0003
            inc = Incident(
                type_infraction=type_infraction,
                date_heure=datetime.utcnow() - timedelta(days=i * 2),
                latitude=lat,
                longitude=lon,
                adresse=f"Secteur {chr(65 + i)}",
                statut=statut,
                gravite=gravite,
                unite_en_charge="Unité Centre" if i % 2 == 0 else "Unité Nord",
            )
            db.add(inc)
            incidents.append(inc)
        db.flush()

        # -- Relations ------------------------------------------------------------
        for i, (nom_a, nom_b, type_relation, poids) in enumerate(RELATIONS):
            db.add(
                Relation(
                    personne_a_id=personnes_by_nom[nom_a].id,
                    personne_b_id=personnes_by_nom[nom_b].id,
                    type_relation=type_relation,
                    poids=poids,
                    source_incident_id=incidents[i % len(incidents)].id,
                )
            )

        # -- Preuve + chaîne de custody (Module 2) ---------------------------------
        preuve = Preuve(
            incident_id=incidents[1].id,  # cambriolage
            type="objet",
            description="Outil d'effraction retrouvé sur les lieux",
            localisation_stockage="Scellé n°2026-014, armoire B3",
        )
        db.add(preuve)
        db.flush()

        custody_events = [
            (utilisateurs_by_email["opj@crimtrack.local"].id, "collecte"),
        ]
        previous_hash = GENESIS
        for utilisateur_id, action in custody_events:
            now = datetime.utcnow()
            h = _hash(previous_hash, preuve.id, utilisateur_id, action, now)
            db.add(
                ChaineCustody(
                    preuve_id=preuve.id,
                    utilisateur_id=utilisateur_id,
                    action=action,
                    date_heure=now,
                    horodatage_hash=h,
                )
            )
            previous_hash = h
        preuve.hash_integrite = previous_hash

        # -- Lectures ANPR (Module 4) -----------------------------------------------
        db.add(
            LectureAnpr(
                plaque_lue="IJ-789-KL",  # véhicule signalé volé -> déclenche une alerte
                date_heure=datetime.utcnow() - timedelta(hours=2),
                latitude=base_lat + 0.002,
                longitude=base_lon + 0.002,
                camera_id="CAM-A12",
                confiance_ocr=0.94,
                vehicule_id=vehicules_by_plaque["IJ-789-KL"].id,
            )
        )
        db.add(
            LectureAnpr(
                plaque_lue="AB-123-CD",
                date_heure=datetime.utcnow() - timedelta(hours=5),
                latitude=base_lat - 0.001,
                longitude=base_lon + 0.004,
                camera_id="CAM-B03",
                confiance_ocr=0.88,
                vehicule_id=vehicules_by_plaque["AB-123-CD"].id,
            )
        )

        db.commit()
        print("Base peuplée avec les données de démonstration.")
        print("\nComptes de démonstration créés (mot de passe : "
              f"'{DEFAULT_PASSWORD}' — à changer avant tout usage réel) :")
        for email, role, _, _ in UTILISATEURS:
            print(f"  - {email}  [{role}]")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
