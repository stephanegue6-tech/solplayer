from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit, auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/personnes", tags=["personnes"], dependencies=[Depends(auth.get_current_user)])


@router.get("", response_model=List[schemas.PersonneOut])
def list_personnes(db: Session = Depends(get_db)):
    return db.query(models.Personne).order_by(models.Personne.nom).all()


@router.get("/{personne_id}", response_model=schemas.PersonneOut)
def get_personne(
    personne_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    personne = db.query(models.Personne).filter(models.Personne.id == personne_id).first()
    if not personne:
        raise HTTPException(status_code=404, detail="Personne introuvable")

    # Consultation d'une fiche individu nominative = accès sensible,
    # journalisé conformément au cahier des charges 6.2.
    audit.log(
        db,
        user=current_user,
        action="consultation",
        ressource_type="personne",
        ressource_id=personne.id,
        request=request,
    )
    return personne


@router.post("", response_model=schemas.PersonneOut, status_code=201)
def create_personne(
    payload: schemas.PersonneCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    personne = models.Personne(**payload.model_dump())
    db.add(personne)
    db.commit()
    db.refresh(personne)

    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="personne",
        ressource_id=personne.id,
        request=request,
    )
    return personne
