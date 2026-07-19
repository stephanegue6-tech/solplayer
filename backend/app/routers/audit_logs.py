from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

# Réservé OPJ/administrateur : la consultation du journal d'audit est
# elle-même une opération sensible (cahier des charges 2.2 / 4.3).
router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(auth.require_roles("opj", "administrateur"))],
)


@router.get("", response_model=List[schemas.AuditLogOut])
def list_audit_logs(
    ressource_type: Optional[str] = None,
    ressource_id: Optional[str] = None,
    utilisateur_email: Optional[str] = None,
    date_debut: Optional[datetime] = None,
    date_fin: Optional[datetime] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """Consultation du journal d'audit (traçabilité des accès et
    modifications, cahier des charges 2.2 / 6.2)."""
    query = db.query(models.JournalAudit)
    if ressource_type:
        query = query.filter(models.JournalAudit.ressource_type == ressource_type)
    if ressource_id:
        query = query.filter(models.JournalAudit.ressource_id == ressource_id)
    if utilisateur_email:
        query = query.filter(models.JournalAudit.utilisateur_email == utilisateur_email)
    if date_debut:
        query = query.filter(models.JournalAudit.date_heure >= date_debut)
    if date_fin:
        query = query.filter(models.JournalAudit.date_heure <= date_fin)
    return query.order_by(models.JournalAudit.date_heure.desc()).limit(limit).all()
