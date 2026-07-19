"""Preuves & chaîne de custody — Module 2 (cahier des charges 3.2).

Implémente :
- fiche de preuve rattachée à un incident ;
- horodatage infalsifiable de chaque manipulation (hash-chain) : chaque
  événement de la chaîne de custody inclut le hash de l'événement
  précédent, ce qui rend toute falsification a posteriori détectable ;
- vérification d'intégrité + alerte en cas de rupture de chaîne.
"""

import hashlib
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from .. import audit, auth, export, models, schemas, storage
from ..database import get_db

router = APIRouter(prefix="/preuves", tags=["preuves"], dependencies=[Depends(auth.get_current_user)])

GENESIS = "GENESIS"


def _compute_hash(previous_hash: str, preuve_id: str, utilisateur_id: str, action: str, date_heure) -> str:
    payload = f"{previous_hash}|{preuve_id}|{utilisateur_id}|{action}|{date_heure.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@router.get("", response_model=List[schemas.PreuveOut])
def list_preuves(incident_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Preuve)
    if incident_id:
        query = query.filter(models.Preuve.incident_id == incident_id)
    return query.all()


@router.get("/{preuve_id}", response_model=schemas.PreuveOut)
def get_preuve(preuve_id: str, db: Session = Depends(get_db)):
    preuve = db.query(models.Preuve).filter(models.Preuve.id == preuve_id).first()
    if not preuve:
        raise HTTPException(status_code=404, detail="Preuve introuvable")
    return preuve


@router.post("", response_model=schemas.PreuveOut, status_code=201)
def create_preuve(
    payload: schemas.PreuveCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    incident = db.query(models.Incident).filter(models.Incident.id == payload.incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident introuvable")

    preuve = models.Preuve(**payload.model_dump())
    db.add(preuve)
    db.commit()
    db.refresh(preuve)

    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="preuve",
        ressource_id=preuve.id,
        details=f"Preuve rattachée à l'incident {preuve.incident_id}",
        request=request,
    )
    return preuve


@router.get("/{preuve_id}/custody", response_model=schemas.ChaineCustodyChainOut)
def get_custody_chain(
    preuve_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    preuve = db.query(models.Preuve).filter(models.Preuve.id == preuve_id).first()
    if not preuve:
        raise HTTPException(status_code=404, detail="Preuve introuvable")

    evenements = (
        db.query(models.ChaineCustody)
        .filter(models.ChaineCustody.preuve_id == preuve_id)
        .order_by(models.ChaineCustody.date_heure.asc())
        .all()
    )

    chaine_intacte = True
    previous_hash = GENESIS
    for evt in evenements:
        expected = _compute_hash(previous_hash, preuve_id, evt.utilisateur_id, evt.action, evt.date_heure)
        if evt.horodatage_hash != expected:
            chaine_intacte = False
            break
        previous_hash = evt.horodatage_hash

    # Consultation de la chaîne de custody = accès sensible, journalisé (6.2).
    audit.log(
        db,
        user=current_user,
        action="consultation",
        ressource_type="chaine_custody",
        ressource_id=preuve_id,
        request=request,
    )

    return schemas.ChaineCustodyChainOut(
        preuve_id=preuve_id,
        evenements=evenements,
        chaine_intacte=chaine_intacte,
        alerte_rupture=not chaine_intacte,
    )


@router.post("/{preuve_id}/custody", response_model=schemas.ChaineCustodyOut, status_code=201)
def add_custody_event(
    preuve_id: str,
    payload: schemas.ChaineCustodyCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    """Ajoute un maillon à la chaîne de custody (collecte / transfert / analyse / restitution).

    L'agent est TOUJOURS l'utilisateur authentifié (`current_user`), jamais
    un identifiant fourni dans le payload : avant correction, le client
    pouvait désigner n'importe quel `personne_id` (y compris un suspect)
    comme dépositaire de la preuve.
    """
    preuve = db.query(models.Preuve).filter(models.Preuve.id == preuve_id).first()
    if not preuve:
        raise HTTPException(status_code=404, detail="Preuve introuvable")

    dernier = (
        db.query(models.ChaineCustody)
        .filter(models.ChaineCustody.preuve_id == preuve_id)
        .order_by(models.ChaineCustody.date_heure.desc())
        .first()
    )
    previous_hash = dernier.horodatage_hash if dernier else GENESIS
    now = datetime.utcnow()
    evenement = models.ChaineCustody(
        preuve_id=preuve_id,
        utilisateur_id=current_user.id,
        action=payload.action,
        date_heure=now,
        horodatage_hash=_compute_hash(previous_hash, preuve_id, current_user.id, payload.action, now),
    )
    db.add(evenement)

    # Le hash du dernier maillon sert de "sceau" d'intégrité courant de la preuve.
    preuve.hash_integrite = evenement.horodatage_hash

    db.commit()
    db.refresh(evenement)

    audit.log(
        db,
        user=current_user,
        action="modification",
        ressource_type="chaine_custody",
        ressource_id=preuve_id,
        details=f"Action '{payload.action}' par {current_user.prenom} {current_user.nom}",
        request=request,
    )
    return evenement


# ---------------------------------------------------------------------------
# Pièces jointes (cahier des charges 3.2) — voir app/storage.py.
# ---------------------------------------------------------------------------


@router.get("/{preuve_id}/pieces-jointes", response_model=List[schemas.PieceJointeOut])
def list_pieces_jointes(preuve_id: str, db: Session = Depends(get_db)):
    preuve = db.query(models.Preuve).filter(models.Preuve.id == preuve_id).first()
    if not preuve:
        raise HTTPException(status_code=404, detail="Preuve introuvable")
    return (
        db.query(models.PieceJointe)
        .filter(models.PieceJointe.preuve_id == preuve_id)
        .order_by(models.PieceJointe.date_ajout.asc())
        .all()
    )


@router.post("/{preuve_id}/pieces-jointes", response_model=schemas.PieceJointeOut, status_code=201)
def upload_piece_jointe(
    preuve_id: str,
    request: Request,
    db: Session = Depends(get_db),
    fichier: UploadFile = File(...),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    """Ajoute une pièce jointe (photo, document, PDF...) à une preuve.

    L'ajout est aussi journalisé comme un maillon de la chaîne de custody
    (le fichier fait désormais partie de la preuve), pas seulement dans le
    journal d'audit générique.
    """
    preuve = db.query(models.Preuve).filter(models.Preuve.id == preuve_id).first()
    if not preuve:
        raise HTTPException(status_code=404, detail="Preuve introuvable")

    content_type = fichier.content_type or "application/octet-stream"
    try:
        chemin_stockage, hash_sha256, taille = storage.save_upload(fichier.file, content_type=content_type)
    except storage.TypeFichierNonAutorise as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    except storage.FichierTropVolumineux as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    piece = models.PieceJointe(
        preuve_id=preuve_id,
        nom_fichier=fichier.filename or "fichier",
        chemin_stockage=chemin_stockage,
        type_mime=content_type,
        taille_octets=taille,
        hash_sha256=hash_sha256,
        ajoute_par_id=current_user.id,
    )
    db.add(piece)

    dernier = (
        db.query(models.ChaineCustody)
        .filter(models.ChaineCustody.preuve_id == preuve_id)
        .order_by(models.ChaineCustody.date_heure.desc())
        .first()
    )
    previous_hash = dernier.horodatage_hash if dernier else GENESIS
    now = datetime.utcnow()
    action = f"ajout_piece_jointe:{piece.nom_fichier}"
    evenement = models.ChaineCustody(
        preuve_id=preuve_id,
        utilisateur_id=current_user.id,
        action=action,
        date_heure=now,
        horodatage_hash=_compute_hash(previous_hash, preuve_id, current_user.id, action, now),
    )
    db.add(evenement)
    preuve.hash_integrite = evenement.horodatage_hash

    db.commit()
    db.refresh(piece)

    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="piece_jointe",
        ressource_id=piece.id,
        details=f"Pièce jointe '{piece.nom_fichier}' ajoutée à la preuve {preuve_id}",
        request=request,
    )
    return piece


@router.get("/{preuve_id}/pieces-jointes/{piece_id}/telechargement")
def download_piece_jointe(
    preuve_id: str,
    piece_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    piece = (
        db.query(models.PieceJointe)
        .filter(models.PieceJointe.id == piece_id, models.PieceJointe.preuve_id == preuve_id)
        .first()
    )
    if not piece:
        raise HTTPException(status_code=404, detail="Pièce jointe introuvable")

    if not storage.verify_integrity(piece.chemin_stockage, piece.hash_sha256):
        # Rupture d'intégrité du fichier lui-même : même logique d'alerte
        # que pour la chaîne de custody (3.2).
        audit.log(
            db,
            user=current_user,
            action="alerte_integrite",
            ressource_type="piece_jointe",
            ressource_id=piece.id,
            details="Hash du fichier sur disque différent du hash enregistré en base",
            request=request,
        )
        raise HTTPException(status_code=409, detail="Intégrité du fichier compromise — téléchargement bloqué")

    audit.log(
        db,
        user=current_user,
        action="consultation",
        ressource_type="piece_jointe",
        ressource_id=piece.id,
        request=request,
    )
    chemin = storage.resolve_path(piece.chemin_stockage)
    return FileResponse(
        path=chemin,
        media_type=piece.type_mime or "application/octet-stream",
        filename=piece.nom_fichier,
    )


@router.delete("/{preuve_id}/pieces-jointes/{piece_id}", status_code=204)
def delete_piece_jointe(
    preuve_id: str,
    piece_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_roles("opj", "administrateur")),
):
    """Suppression réservée à OPJ/administrateur : retirer une pièce d'un
    dossier de preuve est un acte sensible (cf. rôles définis en 4.3)."""
    piece = (
        db.query(models.PieceJointe)
        .filter(models.PieceJointe.id == piece_id, models.PieceJointe.preuve_id == preuve_id)
        .first()
    )
    if not piece:
        raise HTTPException(status_code=404, detail="Pièce jointe introuvable")

    storage.delete_file(piece.chemin_stockage)
    db.delete(piece)
    db.commit()

    audit.log(
        db,
        user=current_user,
        action="suppression",
        ressource_type="piece_jointe",
        ressource_id=piece_id,
        details=f"Pièce jointe '{piece.nom_fichier}' supprimée de la preuve {preuve_id}",
        request=request,
    )
    return None


# ---------------------------------------------------------------------------
# Export CSV / PDF de l'historique de custody (exigence "Interopérabilité" :
# "formats d'export standards (CSV, PDF) pour transmission judiciaire").
# ---------------------------------------------------------------------------

_CUSTODY_HEADERS = ["Date/heure (UTC)", "Action", "Agent", "Rôle", "Hash horodatage"]


def _custody_export_rows(db: Session, preuve_id: str) -> list:
    evenements = (
        db.query(models.ChaineCustody)
        .filter(models.ChaineCustody.preuve_id == preuve_id)
        .order_by(models.ChaineCustody.date_heure.asc())
        .all()
    )
    rows = []
    for evt in evenements:
        agent = evt.utilisateur
        nom_agent = f"{agent.prenom} {agent.nom}" if agent else evt.utilisateur_id
        rows.append(
            [
                evt.date_heure.strftime("%d/%m/%Y %H:%M:%S"),
                evt.action,
                nom_agent,
                agent.role if agent else "",
                evt.horodatage_hash,
            ]
        )
    return rows


@router.get("/{preuve_id}/custody/export.csv")
def export_custody_csv(
    preuve_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    preuve = db.query(models.Preuve).filter(models.Preuve.id == preuve_id).first()
    if not preuve:
        raise HTTPException(status_code=404, detail="Preuve introuvable")

    buffer = export.rows_to_csv(_CUSTODY_HEADERS, _custody_export_rows(db, preuve_id))

    audit.log(
        db,
        user=current_user,
        action="export",
        ressource_type="chaine_custody",
        ressource_id=preuve_id,
        details="Export CSV de l'historique de custody",
        request=request,
    )
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="custody_{preuve_id}.csv"'},
    )


@router.get("/{preuve_id}/custody/export.pdf")
def export_custody_pdf(
    preuve_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    preuve = db.query(models.Preuve).filter(models.Preuve.id == preuve_id).first()
    if not preuve:
        raise HTTPException(status_code=404, detail="Preuve introuvable")

    buffer = export.build_pdf_report(
        titre="Historique de chaîne de custody",
        sous_titre=f"Preuve {preuve_id} — Incident {preuve.incident_id}",
        headers=_CUSTODY_HEADERS,
        rows=_custody_export_rows(db, preuve_id),
        genere_par=f"{current_user.prenom} {current_user.nom} ({current_user.role})",
        notes=(
            "Document généré automatiquement à partir de la chaîne de custody horodatée "
            "(hash-chain SHA-256). Toute rupture de chaîne est signalée séparément via "
            "GET /preuves/{id}/custody."
        ),
    )

    audit.log(
        db,
        user=current_user,
        action="export",
        ressource_type="chaine_custody",
        ressource_id=preuve_id,
        details="Export PDF de l'historique de custody",
        request=request,
    )
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="custody_{preuve_id}.pdf"'},
    )
