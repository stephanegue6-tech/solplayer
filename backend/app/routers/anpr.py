"""Lectures ANPR — Module 4 (cahier des charges 3.4).

Ce module reçoit des lectures de plaques déjà décodées (upstream : caméra +
moteur OCR/ANPR externe — hors périmètre de cette API) et effectue le
rapprochement automatique avec la base "véhicules" pour lever une alerte en
cas de correspondance avec un véhicule signalé/volé.
"""

from datetime import datetime
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import anpr_engine, audit, auth, models, schemas, storage
from ..database import get_db

router = APIRouter(prefix="/anpr", tags=["anpr"], dependencies=[Depends(auth.get_current_user)])

STATUTS_ALERTE = {"signalé", "signale", "volé", "vole"}


@router.get("/lectures", response_model=List[schemas.LectureAnprOut])
def list_lectures(
    plaque: Optional[str] = None,
    vehicule_id: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    query = db.query(models.LectureAnpr)
    if plaque:
        query = query.filter(models.LectureAnpr.plaque_lue == plaque)
    if vehicule_id:
        query = query.filter(models.LectureAnpr.vehicule_id == vehicule_id)
    return query.order_by(models.LectureAnpr.date_heure.desc()).limit(limit).all()


@router.get("/lectures/{lecture_id}", response_model=schemas.LectureAnprOut)
def get_lecture(lecture_id: str, db: Session = Depends(get_db)):
    lecture = db.query(models.LectureAnpr).filter(models.LectureAnpr.id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture ANPR introuvable")
    return lecture


def _rapprocher(db: Session, plaque_lue: str) -> Optional[models.Vehicule]:
    return (
        db.query(models.Vehicule)
        .filter(models.Vehicule.plaque_immatriculation == plaque_lue)
        .first()
    )


def _statut_alerte(vehicule: Optional[models.Vehicule]) -> tuple:
    if vehicule and vehicule.statut and vehicule.statut.lower() in STATUTS_ALERTE:
        return True, f"Véhicule {vehicule.plaque_immatriculation} au statut '{vehicule.statut}'"
    return False, None


def _journaliser_lecture(db, request, current_user, lecture, alerte, motif_alerte):
    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="lecture_anpr",
        ressource_id=lecture.id,
        details=(
            f"Plaque {lecture.plaque_lue} — ALERTE ({motif_alerte})" if alerte else f"Plaque {lecture.plaque_lue}"
        ),
        request=request,
    )


@router.post("/lectures", response_model=schemas.LectureAnprResult, status_code=201)
def create_lecture(
    payload: schemas.LectureAnprCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    """Enregistre une lecture ANPR et effectue le rapprochement automatique
    avec la base véhicules (cahier 3.4 : "Rapprochement automatique avec la
    base véhicules" + "Alerte en cas de correspondance avec un véhicule
    recherché").

    Réservé aux plaques déjà décodées en amont (saisie manuelle ou moteur
    OCR tiers). Pour une image brute, voir `POST /anpr/lectures/depuis-image`.
    """
    vehicule = _rapprocher(db, payload.plaque_lue)

    lecture = models.LectureAnpr(
        plaque_lue=payload.plaque_lue,
        date_heure=payload.date_heure or datetime.utcnow(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        camera_id=payload.camera_id,
        confiance_ocr=payload.confiance_ocr,
        vehicule_id=vehicule.id if vehicule else None,
        source="manuel",
    )
    db.add(lecture)
    db.commit()
    db.refresh(lecture)

    alerte, motif_alerte = _statut_alerte(vehicule)
    _journaliser_lecture(db, request, current_user, lecture, alerte, motif_alerte)

    return schemas.LectureAnprResult(
        lecture=lecture,
        vehicule_reconnu=vehicule,
        alerte=alerte,
        motif_alerte=motif_alerte,
    )


@router.post("/lectures/depuis-image", response_model=schemas.DetectionAnprResult, status_code=201)
def create_lecture_depuis_image(
    request: Request,
    db: Session = Depends(get_db),
    fichier: UploadFile = File(...),
    camera_id: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    """Détecte et lit une plaque directement depuis une image téléversée
    (cahier 3.4 : détection/lecture réelle de plaque, jusque-là absente —
    le module ne faisait que du rapprochement sur des plaques déjà
    décodées).

    Pipeline local (`app/anpr_engine.py`, OpenCV + tesseract, aucun appel
    externe) : localisation de la région de plaque puis OCR. Le meilleur
    candidat est enregistré comme une lecture normale (même rapprochement
    et même alerte que `POST /anpr/lectures`) ; les autres candidats sont
    renvoyés pour permettre à un agent de corriger si l'OCR s'est trompé
    (voir `PATCH /anpr/lectures/{id}`). L'image source est conservée
    (mêmes garanties d'intégrité que les pièces jointes, `app/storage.py`)
    pour permettre une revérification a posteriori.
    """
    content_type = fichier.content_type or "application/octet-stream"
    try:
        chemin_stockage, hash_sha256, _taille = storage.save_upload(fichier.file, content_type=content_type)
    except storage.TypeFichierNonAutorise as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    except storage.FichierTropVolumineux as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    chemin_abs = storage.resolve_path(chemin_stockage)
    try:
        with open(chemin_abs, "rb") as f:
            candidats = anpr_engine.detecter_plaques(f.read())
    except ValueError as exc:
        storage.delete_file(chemin_stockage)
        raise HTTPException(status_code=422, detail=str(exc))

    if not candidats:
        storage.delete_file(chemin_stockage)
        raise HTTPException(
            status_code=422,
            detail="Aucune plaque détectée sur l'image (angle, résolution ou éclairage insuffisants ?)",
        )

    meilleur = candidats[0]
    vehicule = _rapprocher(db, meilleur.texte)

    lecture = models.LectureAnpr(
        plaque_lue=meilleur.texte,
        date_heure=datetime.utcnow(),
        latitude=latitude,
        longitude=longitude,
        camera_id=camera_id,
        confiance_ocr=meilleur.confiance,
        vehicule_id=vehicule.id if vehicule else None,
        source="image",
        image_chemin=chemin_stockage,
        image_hash_sha256=hash_sha256,
    )
    db.add(lecture)
    db.commit()
    db.refresh(lecture)

    alerte, motif_alerte = _statut_alerte(vehicule)
    _journaliser_lecture(db, request, current_user, lecture, alerte, motif_alerte)

    return schemas.DetectionAnprResult(
        lecture=lecture,
        vehicule_reconnu=vehicule,
        alerte=alerte,
        motif_alerte=motif_alerte,
        candidats=[
            schemas.CandidatPlaqueOut(
                texte=c.texte, confiance=c.confiance, bbox=list(c.bbox), format_reconnu=c.format_reconnu
            )
            for c in candidats
        ],
    )


@router.post("/lectures/depuis-video", response_model=schemas.DetectionAnprVideoResult, status_code=201)
def create_lectures_depuis_video(
    request: Request,
    db: Session = Depends(get_db),
    fichier: Optional[UploadFile] = File(None),
    url_flux: Optional[str] = None,
    camera_id: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    intervalle_secondes: float = 1.0,
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    """Détecte et lit les plaques présentes sur une vidéo téléversée ou sur
    un flux caméra en direct (cahier 3.4 : lecture réelle de plaque sur
    image *ou vidéo* — partie vidéo, jusque-là absente).

    Deux sources possibles, au choix (jamais les deux) :
    - `fichier` : une vidéo téléversée (ex. export d'un enregistrement
      caméra) — stockée comme les pièces jointes, avec les mêmes garanties
      d'intégrité ;
    - `url_flux` : une URL de flux caméra en direct (ex. `rtsp://...`,
      `http://.../mjpeg`), lue directement sans être stockée telle quelle —
      seules les frames où une plaque a été détectée sont conservées.

    La vidéo/le flux est échantillonné(e) toutes les `intervalle_secondes`
    (pas d'analyse frame par frame en continu, inutile à 25-30 fps) et une
    seule lecture est créée par plaque distincte trouvée — la meilleure
    occurrence sur l'ensemble des frames analysées, avec son horodatage
    dans la vidéo et la frame correspondante comme image source (mêmes
    rapprochement et alerte que pour une lecture manuelle/image).
    """
    if bool(fichier) == bool(url_flux):
        raise HTTPException(
            status_code=422,
            detail="Fournir soit une vidéo (fichier), soit une URL de flux caméra (url_flux) — pas les deux, pas aucun",
        )

    video_chemin_stockage = None
    if fichier:
        content_type = fichier.content_type or "application/octet-stream"
        try:
            video_chemin_stockage, _hash, _taille = storage.save_upload(fichier.file, content_type=content_type)
        except storage.TypeFichierNonAutorise as exc:
            raise HTTPException(status_code=415, detail=str(exc))
        except storage.FichierTropVolumineux as exc:
            raise HTTPException(status_code=413, detail=str(exc))
        source_cv2 = str(storage.resolve_path(video_chemin_stockage))
    else:
        # Flux caméra en direct : lu directement par OpenCV (RTSP/HTTP),
        # jamais écrit sur disque tel quel — ce n'est pas un fichier
        # téléversé mais une source réseau externe.
        source_cv2 = url_flux

    try:
        resultat = anpr_engine.detecter_plaques_video(
            source_cv2, intervalle_secondes=max(0.2, intervalle_secondes)
        )
    except ValueError as exc:
        if video_chemin_stockage:
            storage.delete_file(video_chemin_stockage)
        raise HTTPException(status_code=422, detail=str(exc))

    if not resultat.lectures:
        if video_chemin_stockage:
            storage.delete_file(video_chemin_stockage)
        raise HTTPException(
            status_code=422,
            detail="Aucune plaque détectée sur la vidéo/le flux (angle, résolution, éclairage ou durée insuffisants ?)",
        )

    items = []
    for det in resultat.lectures:
        image_chemin, image_hash = None, None
        if det.frame_jpeg:
            try:
                image_chemin, image_hash, _t = storage.save_upload(
                    BytesIO(det.frame_jpeg), content_type="image/jpeg"
                )
            except (storage.TypeFichierNonAutorise, storage.FichierTropVolumineux):
                pass  # la lecture reste valable même sans frame de référence conservée

        vehicule = _rapprocher(db, det.texte)
        lecture = models.LectureAnpr(
            plaque_lue=det.texte,
            date_heure=datetime.utcnow(),
            latitude=latitude,
            longitude=longitude,
            camera_id=camera_id,
            confiance_ocr=det.confiance,
            vehicule_id=vehicule.id if vehicule else None,
            source="video",
            image_chemin=image_chemin,
            image_hash_sha256=image_hash,
            video_chemin=video_chemin_stockage,
            video_timestamp_s=det.timestamp_s,
        )
        db.add(lecture)
        db.commit()
        db.refresh(lecture)

        alerte, motif_alerte = _statut_alerte(vehicule)
        _journaliser_lecture(db, request, current_user, lecture, alerte, motif_alerte)

        items.append(
            schemas.LectureVideoItem(
                lecture=lecture,
                vehicule_reconnu=vehicule,
                alerte=alerte,
                motif_alerte=motif_alerte,
                timestamp_s=det.timestamp_s,
            )
        )

    return schemas.DetectionAnprVideoResult(
        lectures=items,
        frames_analysees=resultat.frames_analysees,
        duree_video_s=resultat.duree_video_s,
    )


@router.get("/lectures/{lecture_id}/image")
def get_lecture_image(
    lecture_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    """Télécharge l'image source d'une lecture obtenue par détection
    automatique, pour permettre à un agent de revérifier la lecture."""
    lecture = db.query(models.LectureAnpr).filter(models.LectureAnpr.id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture ANPR introuvable")
    if not lecture.image_chemin:
        raise HTTPException(status_code=404, detail="Cette lecture n'a pas d'image source (lecture manuelle)")

    if not storage.verify_integrity(lecture.image_chemin, lecture.image_hash_sha256):
        audit.log(
            db,
            user=current_user,
            action="alerte_integrite",
            ressource_type="lecture_anpr",
            ressource_id=lecture.id,
            details="Hash de l'image source différent du hash enregistré en base",
            request=request,
        )
        raise HTTPException(status_code=409, detail="Intégrité de l'image compromise — téléchargement bloqué")

    audit.log(
        db,
        user=current_user,
        action="consultation",
        ressource_type="lecture_anpr",
        ressource_id=lecture.id,
        details="Consultation de l'image source",
        request=request,
    )
    chemin = storage.resolve_path(lecture.image_chemin)
    return FileResponse(path=chemin, media_type="image/jpeg", filename=f"anpr_{lecture.id}.jpg")


@router.patch("/lectures/{lecture_id}", response_model=schemas.LectureAnprResult)
def corriger_lecture(
    lecture_id: str,
    payload: schemas.LectureAnprCorrection,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    """Corrige la plaque d'une lecture (utile après une détection
    automatique dont l'OCR s'est trompé) et refait le rapprochement avec la
    base véhicules à partir de la valeur corrigée."""
    lecture = db.query(models.LectureAnpr).filter(models.LectureAnpr.id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture ANPR introuvable")

    ancienne_plaque = lecture.plaque_lue
    lecture.plaque_lue = payload.plaque_lue
    vehicule = _rapprocher(db, payload.plaque_lue)
    lecture.vehicule_id = vehicule.id if vehicule else None
    db.commit()
    db.refresh(lecture)

    alerte, motif_alerte = _statut_alerte(vehicule)
    audit.log(
        db,
        user=current_user,
        action="modification",
        ressource_type="lecture_anpr",
        ressource_id=lecture.id,
        details=f"Plaque corrigée : '{ancienne_plaque}' -> '{lecture.plaque_lue}'",
        request=request,
    )

    return schemas.LectureAnprResult(
        lecture=lecture,
        vehicule_reconnu=vehicule,
        alerte=alerte,
        motif_alerte=motif_alerte,
    )
