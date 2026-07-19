from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit, auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/vehicules", tags=["vehicules"], dependencies=[Depends(auth.get_current_user)])


@router.get("", response_model=List[schemas.VehiculeOut])
def list_vehicules(db: Session = Depends(get_db)):
    return db.query(models.Vehicule).order_by(models.Vehicule.plaque_immatriculation).all()


@router.get("/{vehicule_id}", response_model=schemas.VehiculeOut)
def get_vehicule(vehicule_id: str, db: Session = Depends(get_db)):
    vehicule = db.query(models.Vehicule).filter(models.Vehicule.id == vehicule_id).first()
    if not vehicule:
        raise HTTPException(status_code=404, detail="Véhicule introuvable")
    return vehicule


@router.post("", response_model=schemas.VehiculeOut, status_code=201)
def create_vehicule(
    payload: schemas.VehiculeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    vehicule = models.Vehicule(**payload.model_dump())
    db.add(vehicule)
    db.commit()
    db.refresh(vehicule)

    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="vehicule",
        ressource_id=vehicule.id,
        request=request,
    )
    return vehicule
