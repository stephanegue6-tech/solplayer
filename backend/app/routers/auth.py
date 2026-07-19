from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import audit, auth, models, schemas
from ..database import get_db
from ..rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Connexion (RBAC). `form_data.username` attend l'email de l'utilisateur.

    Limité à 5 tentatives/minute par IP (cahier des charges 4.3 / anti
    brute-force) — absent jusqu'ici, ce qui permettait un nombre illimité
    d'essais de mot de passe.

    Consommé par le frontend via un formulaire OAuth2 password-grant
    standard (`application/x-www-form-urlencoded`, champs `username`/`password`).
    """
    user = db.query(models.Utilisateur).filter(models.Utilisateur.email == form_data.username).first()

    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        audit.log(
            db,
            user=None,
            action="echec_connexion",
            ressource_type="utilisateur",
            details=f"Tentative avec l'identifiant '{form_data.username}'",
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.actif:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")

    access_token = auth.create_access_token(subject=user.id, role=user.role)
    refresh_token = auth.create_refresh_token(db, user)
    audit.log(db, user=user, action="connexion", ressource_type="utilisateur", ressource_id=user.id, request=request)

    return schemas.Token(
        access_token=access_token, refresh_token=refresh_token, role=user.role, nom=user.nom, prenom=user.prenom
    )


@router.post("/refresh", response_model=schemas.Token)
def refresh(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    """Échange un refresh token contre un nouveau couple (access, refresh).

    Cf. app/auth.py:rotate_refresh_token — rotation à chaque usage, avec
    détection de réutilisation (vol probable).
    """
    user, new_refresh_token = auth.rotate_refresh_token(db, payload.refresh_token)
    new_access_token = auth.create_access_token(subject=user.id, role=user.role)
    return schemas.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        role=user.role,
        nom=user.nom,
        prenom=user.prenom,
    )


@router.post("/logout", status_code=204)
def logout(
    payload: schemas.RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(auth.get_current_token_payload),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    """Déconnexion explicite : révoque IMMÉDIATEMENT l'access token en cours
    (au lieu d'attendre son expiration naturelle) et le refresh token associé.
    """
    auth.revoke_access_token(db, token_payload)
    auth.revoke_refresh_token(db, payload.refresh_token)
    audit.log(db, user=current_user, action="deconnexion", ressource_type="utilisateur", ressource_id=current_user.id, request=request)
    return None


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.Utilisateur = Depends(auth.get_current_user)):
    return current_user


@router.post("", response_model=schemas.UserOut, status_code=201)
def register_user(
    payload: schemas.UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_admin),
):
    """Création d'un compte utilisateur — réservé aux administrateurs."""
    if payload.role not in models.ROLES:
        raise HTTPException(status_code=422, detail=f"Rôle invalide (attendu : {', '.join(models.ROLES)})")

    if db.query(models.Utilisateur).filter(models.Utilisateur.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet email")

    user = models.Utilisateur(
        email=payload.email,
        hashed_password=auth.hash_password(payload.password),
        nom=payload.nom,
        prenom=payload.prenom,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="utilisateur",
        ressource_id=user.id,
        details=f"Compte créé pour {user.email} (rôle {user.role})",
        request=request,
    )
    return user


@router.get("", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_admin),
):
    """Liste des comptes — réservé aux administrateurs."""
    return db.query(models.Utilisateur).order_by(models.Utilisateur.email).all()
