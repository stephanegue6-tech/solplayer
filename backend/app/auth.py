"""Authentification (JWT) et autorisation par rôles (RBAC).

Cf. cahier des charges 4.3 : "Authentification et autorisation basées sur
les rôles (RBAC) : enquêteur, analyste, OPJ, administrateur."

- `enqueteur`, `opj`, `administrateur` : lecture + écriture sur le socle
  métier (incidents, personnes, véhicules, preuves, custody, ANPR).
- `analyste`   : lecture seule partout, y compris /incidents/analyse/hotspots
  et /relations/graphe (c'est son cœur de métier).
- `administrateur` uniquement : gestion des comptes utilisateurs.

⚠️ SECRET_KEY : une valeur de développement est fournie par défaut pour ne
pas bloquer le démarrage local, mais DOIT être surchargée par la variable
d'environnement JWT_SECRET_KEY avant tout déploiement (voir .env.example).
"""

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .database import get_db

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Rôles autorisés à créer/modifier des données métier.
WRITE_ROLES = ("enqueteur", "opj", "administrateur")
# Rôle(s) autorisé(s) à gérer les comptes.
ADMIN_ROLES = ("administrateur",)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "role": role, "exp": expire, "jti": str(uuid.uuid4())}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.Utilisateur:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides ou expirés",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        jti = payload.get("jti")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if jti and db.query(models.RevokedAccessToken).filter(models.RevokedAccessToken.jti == jti).first():
        raise credentials_exception

    user = db.query(models.Utilisateur).filter(models.Utilisateur.id == user_id).first()
    if user is None or not user.actif:
        raise credentials_exception
    return user


def require_roles(*roles: str):
    """Fabrique une dépendance FastAPI qui exige un des rôles donnés.

    Usage : `Depends(require_roles("opj", "administrateur"))`
    """

    def _dependency(current_user: models.Utilisateur = Depends(get_current_user)) -> models.Utilisateur:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle '{current_user.role}' non autorisé pour cette action (requis : {', '.join(roles)})",
            )
        return current_user

    return _dependency


# Dépendances prêtes à l'emploi, réutilisées dans les routers.
require_write = require_roles(*WRITE_ROLES)
require_admin = require_roles(*ADMIN_ROLES)


def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """Comme get_current_user, mais renvoie le payload décodé (utile pour
    /auth/logout, qui a besoin du jti pour révoquer CE token précis)."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")


def revoke_access_token(db: Session, payload: dict) -> None:
    """Révoque immédiatement un access token (déconnexion) au lieu d'attendre
    son expiration naturelle — absent jusqu'ici : un token volé restait
    valide jusqu'à ACCESS_TOKEN_EXPIRE_MINUTES même après déconnexion."""
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    if db.query(models.RevokedAccessToken).filter(models.RevokedAccessToken.jti == jti).first():
        return
    db.add(
        models.RevokedAccessToken(
            jti=jti,
            date_expiration=datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None),
        )
    )
    db.commit()


def _hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_refresh_token(db: Session, user: models.Utilisateur) -> str:
    """Émet un nouveau refresh token longue durée. Seul son hash est stocké."""
    raw_token = secrets.token_urlsafe(48)
    db.add(
        models.RefreshToken(
            utilisateur_id=user.id,
            token_hash=_hash_refresh_token(raw_token),
            date_expiration=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    return raw_token


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[models.Utilisateur, str]:
    """Échange un refresh token valide contre un nouveau couple (access, refresh).

    Rotation à chaque usage : l'ancien refresh token est marqué révoqué. Une
    tentative de réutilisation d'un token déjà consommé est donc détectable
    (signe probable de vol) — on révoque alors, par précaution, TOUS les
    refresh tokens actifs de l'utilisateur concerné.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalide ou expiré"
    )
    token_hash = _hash_refresh_token(raw_token)
    stored = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == token_hash).first()
    if not stored:
        raise credentials_exception

    if stored.revoked:
        # Réutilisation d'un token déjà consommé : vol probable -> on coupe
        # toutes les sessions actives de cet utilisateur par précaution.
        db.query(models.RefreshToken).filter(
            models.RefreshToken.utilisateur_id == stored.utilisateur_id, models.RefreshToken.revoked.is_(False)
        ).update({"revoked": True})
        db.commit()
        raise credentials_exception

    if stored.date_expiration < datetime.utcnow():
        raise credentials_exception

    user = db.query(models.Utilisateur).filter(models.Utilisateur.id == stored.utilisateur_id).first()
    if not user or not user.actif:
        raise credentials_exception

    stored.revoked = True
    db.commit()

    new_raw_token = create_refresh_token(db, user)
    return user, new_raw_token


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    token_hash = _hash_refresh_token(raw_token)
    stored = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == token_hash).first()
    if stored:
        stored.revoked = True
        db.commit()


def client_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None
