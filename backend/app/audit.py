"""Journalisation des accès et modifications (audit trail).

Cf. cahier des charges 2.2 : "Journalisation complète des actions
(audit trail)" et 6.2 : "traçabilité de chaque consultation".

Utilisation dans un router :

    from .. import audit
    audit.log(db, user=current_user, action="creation",
               ressource_type="incident", ressource_id=incident.id,
               request=request)

Le log est écrit dans la même transaction que l'action métier quand c'est
possible (même `db`), pour éviter les écritures "orphelines" en cas
d'erreur applicative.
"""

from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from . import models


def log(
    db: Session,
    *,
    user: Optional[models.Utilisateur],
    action: str,
    ressource_type: str,
    ressource_id: Optional[str] = None,
    details: Optional[str] = None,
    request: Optional[Request] = None,
) -> models.JournalAudit:
    entry = models.JournalAudit(
        utilisateur_id=user.id if user else None,
        utilisateur_email=user.email if user else None,
        action=action,
        ressource_type=ressource_type,
        ressource_id=ressource_id,
        details=details,
        adresse_ip=request.client.host if (request and request.client) else None,
    )
    db.add(entry)
    db.commit()
    return entry
