"""Purge RGPD des données à caractère personnel (cahier des charges 6.1) :

    "Le traitement de données à caractère personnel (identité, signalement,
    localisation) impose une base légale claire, une minimisation des
    données collectées et des durées de conservation définies conformément
    au cadre applicable aux traitements de police et de justice."

Principes retenus pour ce périmètre :

- seuls les dossiers CLOS (`incident.statut` dans `INCIDENT_STATUTS_CLOS`)
  et dont la date des faits dépasse la durée de rétention peuvent être
  concernés : un dossier ouvert n'est jamais purgé, quelle que soit son
  ancienneté (l'enquête peut être en cours) ;
- on **anonymise** les personnes plutôt que de les supprimer physiquement,
  et seulement si elles ne sont rattachées à AUCUN incident encore actif
  ou non purgeable : une personne impliquée à la fois dans un vieux dossier
  clos et une affaire en cours ne doit pas perdre son identité dans ce
  second dossier ;
- les preuves, la chaîne de custody et le journal d'audit ne sont **jamais**
  purgés par ce module : ce sont des pièces de procédure / de traçabilité
  légale, hors du champ de la minimisation des données de la fiche
  individu (et le journal d'audit doit au contraire subsister pour prouver
  qu'une purge a bien eu lieu) ;
- chaque exécution est journalisée dans le journal d'audit (traçabilité de
  la purge elle-même, cf. 4.3 "Auditabilité").

La durée de rétention par défaut est volontairement conservatrice (3 ans)
et doit être ajustée selon le cadre juridique applicable réellement au
service utilisateur (voir `.env` -> RGPD_RETENTION_DAYS).
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from . import audit, models

INCIDENT_STATUTS_CLOS = {"clos", "classe_sans_suite", "classé_sans_suite"}

DEFAULT_RETENTION_DAYS = int(os.getenv("RGPD_RETENTION_DAYS", "1095"))  # ~3 ans

ANONYMISATION_NOM = "ANONYMISÉ (purge RGPD)"


@dataclass
class CandidatPurge:
    incident_id: str
    date_heure: datetime
    statut: str
    personnes_anonymisables: List[str] = field(default_factory=list)


def _cutoff(retention_days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=retention_days)


def _incidents_purgeables(db: Session, retention_days: int) -> List[models.Incident]:
    cutoff = _cutoff(retention_days)
    return (
        db.query(models.Incident)
        .filter(models.Incident.statut.in_(INCIDENT_STATUTS_CLOS))
        .filter(models.Incident.date_heure < cutoff)
        .all()
    )


def identifier_candidats(db: Session, retention_days: int = DEFAULT_RETENTION_DAYS) -> List[CandidatPurge]:
    """Mode "à blanc" : liste ce qui serait purgé, sans rien modifier."""
    incidents = _incidents_purgeables(db, retention_days)
    purgeable_ids = {i.id for i in incidents}
    candidats = []

    for incident in incidents:
        anonymisables = []
        for personne in incident.personnes:
            autres_incidents = {i.id for i in personne.incidents} - purgeable_ids
            if not autres_incidents and personne.nom != ANONYMISATION_NOM:
                anonymisables.append(personne.id)
        candidats.append(
            CandidatPurge(
                incident_id=incident.id,
                date_heure=incident.date_heure,
                statut=incident.statut,
                personnes_anonymisables=anonymisables,
            )
        )
    return candidats


def _anonymiser_personne(personne: models.Personne) -> None:
    personne.nom = ANONYMISATION_NOM
    personne.prenom = ""
    personne.date_naissance = None
    personne.signalement = None
    personne.photo_ref = None
    # `role` (suspect/victime/témoin) et `statut` sont conservés : ce sont
    # des données statistiques utiles (hotspots, rapports d'unité) qui ne
    # permettent pas, seules, de ré-identifier la personne.


def executer_purge(
    db: Session,
    *,
    current_user: Optional[models.Utilisateur],
    retention_days: int = DEFAULT_RETENTION_DAYS,
    request=None,
) -> dict:
    """Exécute réellement la purge (anonymisation) et journalise l'opération.

    Retourne un résumé (nombre d'incidents concernés, de personnes
    anonymisées) pour affichage / journalisation applicative.
    """
    candidats = identifier_candidats(db, retention_days)
    total_personnes = 0

    for candidat in candidats:
        for personne_id in candidat.personnes_anonymisables:
            personne = db.query(models.Personne).filter(models.Personne.id == personne_id).first()
            if personne:
                _anonymiser_personne(personne)
                total_personnes += 1

    db.commit()

    resume = {
        "retention_days": retention_days,
        "incidents_concernes": len(candidats),
        "personnes_anonymisees": total_personnes,
    }

    audit.log(
        db,
        user=current_user,
        action="purge_rgpd",
        ressource_type="personnes",
        ressource_id=None,
        details=(
            f"Purge RGPD exécutée : {total_personnes} personne(s) anonymisée(s) sur "
            f"{len(candidats)} incident(s) clos de plus de {retention_days} jours"
        ),
        request=request,
    )
    return resume


if __name__ == "__main__":
    # Utilisation en tâche planifiée (cron), hors requête HTTP :
    #   python -m app.rgpd
    from .database import SessionLocal

    db = SessionLocal()
    try:
        resume = executer_purge(db, current_user=None)
        print(f"Purge RGPD terminée : {resume}")
    finally:
        db.close()
