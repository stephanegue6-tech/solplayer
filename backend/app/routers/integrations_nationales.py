"""Endpoints d'intégration avec les systèmes nationaux existants (cahier
des charges 2.3). Voir `app/national_systems.py` pour le contrat
d'adaptateur et les garde-fous d'activation.

Ces endpoints restent fonctionnels (pas de 404 volontaire) pour que le
frontend puisse afficher un état "en attente de convention" plutôt que de
traiter la fonctionnalité comme absente. En revanche, aucun appel réel ne
peut passer tant que la configuration (SYSTEME_{CODE}_ACTIF +
SYSTEME_{CODE}_CONVENTION_REF) n'est pas renseignée pour l'environnement
de déploiement concerné.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit, auth, models, national_systems, schemas
from ..database import get_db

router = APIRouter(
    prefix="/integrations-nationales",
    tags=["integrations-nationales"],
    dependencies=[Depends(auth.get_current_user)],
)


@router.get("/systemes")
def lister_systemes(current_user: models.Utilisateur = Depends(auth.get_current_user)):
    """Vue d'ensemble : quels systèmes nationaux sont prévus, et leur état
    d'activation. Visible par tout utilisateur authentifié (transparence
    sur ce qui est/n'est pas connecté), mais l'appel de rapprochement
    lui-même est restreint (voir ci-dessous)."""
    return national_systems.statut_systemes()


@router.post("/{code_systeme}/rapprochement-personne", response_model=schemas.RapprochementPersonneOut)
def rapprocher_personne(
    code_systeme: str,
    payload: schemas.RapprochementPersonneIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_roles("opj", "administrateur")),
):
    audit.log(
        db,
        user=current_user,
        action="tentative_rapprochement_national",
        ressource_type="integration_nationale",
        ressource_id=code_systeme,
        details=f"personne nom={payload.nom} prenom={payload.prenom}",
        request=request,
    )
    try:
        adapter = national_systems.get_adapter(code_systeme)
        return adapter.rapprocher_personne(payload.nom, payload.prenom, payload.date_naissance)
    except national_systems.SystemeNonConfigureError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{code_systeme}/rapprochement-vehicule", response_model=schemas.RapprochementVehiculeOut)
def rapprocher_vehicule(
    code_systeme: str,
    payload: schemas.RapprochementVehiculeIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_roles("opj", "administrateur")),
):
    audit.log(
        db,
        user=current_user,
        action="tentative_rapprochement_national",
        ressource_type="integration_nationale",
        ressource_id=code_systeme,
        details=f"plaque={payload.plaque_immatriculation}",
        request=request,
    )
    try:
        adapter = national_systems.get_adapter(code_systeme)
        return adapter.rapprocher_vehicule(payload.plaque_immatriculation)
    except national_systems.SystemeNonConfigureError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
