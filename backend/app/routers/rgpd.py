from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth, models, rgpd
from ..database import get_db

# Réservé administrateur : décider quelles fiches sont anonymisées est une
# opération sensible à fort impact (cahier des charges 6.1 / 6.2).
router = APIRouter(
    prefix="/rgpd",
    tags=["rgpd"],
    dependencies=[Depends(auth.require_roles("administrateur"))],
)


class CandidatPurgeOut(BaseModel):
    incident_id: str
    statut: str
    nombre_personnes_anonymisables: int


class PurgeResultOut(BaseModel):
    retention_days: int
    incidents_concernes: int
    personnes_anonymisees: int


@router.get("/candidats", response_model=List[CandidatPurgeOut])
def lister_candidats_purge(
    retention_days: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Mode "à blanc" (dry-run) : liste les dossiers clos éligibles à la
    purge et le nombre de fiches individu qui seraient anonymisées, sans
    rien modifier. À utiliser avant `/rgpd/purge` pour vérifier l'impact."""
    jours = retention_days if retention_days is not None else rgpd.DEFAULT_RETENTION_DAYS
    candidats = rgpd.identifier_candidats(db, jours)
    return [
        CandidatPurgeOut(
            incident_id=c.incident_id,
            statut=c.statut,
            nombre_personnes_anonymisables=len(c.personnes_anonymisables),
        )
        for c in candidats
    ]


@router.post("/purge", response_model=PurgeResultOut)
def lancer_purge(
    request: Request,
    retention_days: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_roles("administrateur")),
):
    """Exécute la purge RGPD (anonymisation) sur les dossiers clos dépassant
    la durée de rétention (cahier des charges 6.1). Irréversible : les
    champs anonymisés ne sont pas récupérables après coup."""
    jours = retention_days if retention_days is not None else rgpd.DEFAULT_RETENTION_DAYS
    resume = rgpd.executer_purge(db, current_user=current_user, retention_days=jours, request=request)
    return PurgeResultOut(**resume)
