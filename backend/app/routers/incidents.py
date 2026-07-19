import math
from collections import defaultdict
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import audit, auth, models, schemas
from ..database import get_db
from ..export import build_map_pdf_report, build_pdf_report, rows_to_csv

router = APIRouter(prefix="/incidents", tags=["incidents"], dependencies=[Depends(auth.get_current_user)])

METRES_PAR_DEGRE_LAT = 111_320.0


def _filtered_incidents_query(
    db: Session,
    statut: Optional[str],
    type_infraction: Optional[str],
    date_debut: Optional[datetime] = None,
    date_fin: Optional[datetime] = None,
    adresse: Optional[str] = None,
):
    query = db.query(models.Incident)
    if statut:
        query = query.filter(models.Incident.statut == statut)
    if type_infraction:
        query = query.filter(models.Incident.type_infraction == type_infraction)
    if date_debut:
        query = query.filter(models.Incident.date_heure >= date_debut)
    if date_fin:
        query = query.filter(models.Incident.date_heure <= date_fin)
    if adresse:
        # Filtre "zone" (cahier des charges 3.1 : "filtres par période, type
        # d'infraction et zone") : recherche approximative sur l'adresse
        # tant qu'aucune extension géospatiale (PostGIS) n'est branchée.
        query = query.filter(models.Incident.adresse.ilike(f"%{adresse}%"))
    return query.order_by(models.Incident.date_heure.desc())


@router.get("", response_model=List[schemas.IncidentOut])
def list_incidents(
    statut: Optional[str] = None,
    type_infraction: Optional[str] = None,
    date_debut: Optional[datetime] = None,
    date_fin: Optional[datetime] = None,
    adresse: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """Liste des incidents, filtrable par statut, type d'infraction, période
    et zone (adresse). Consommé par le Tableau de bord, la liste Incidents
    et la Carte interactive du frontend.
    """
    return _filtered_incidents_query(db, statut, type_infraction, date_debut, date_fin, adresse).limit(limit).all()


_EXPORT_HEADERS = [
    "ID",
    "Type d'infraction",
    "Date/heure",
    "Statut",
    "Gravité",
    "Latitude",
    "Longitude",
    "Adresse",
    "Unité en charge",
]


def _incident_row(inc: models.Incident) -> list:
    return [
        inc.id,
        inc.type_infraction,
        inc.date_heure.strftime("%d/%m/%Y %H:%M") if inc.date_heure else "",
        inc.statut,
        inc.gravite,
        inc.latitude,
        inc.longitude,
        inc.adresse,
        inc.unite_en_charge,
    ]


@router.get("/export/csv")
def export_incidents_csv(
    statut: Optional[str] = None,
    type_infraction: Optional[str] = None,
    date_debut: Optional[datetime] = None,
    date_fin: Optional[datetime] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    """Export CSV des incidents (cahier des charges 3.1 + exigence "Interopérabilité")."""
    incidents = _filtered_incidents_query(db, statut, type_infraction, date_debut, date_fin).all()
    buffer = rows_to_csv(_EXPORT_HEADERS, (_incident_row(i) for i in incidents))

    audit.log(
        db, user=current_user, action="export", ressource_type="incident",
        details=f"Export CSV de {len(incidents)} incident(s)", request=request,
    )
    filename = f"incidents_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/pdf")
def export_incidents_pdf(
    statut: Optional[str] = None,
    type_infraction: Optional[str] = None,
    date_debut: Optional[datetime] = None,
    date_fin: Optional[datetime] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    """Export PDF (rapport cartographique imprimable) des incidents."""
    incidents = _filtered_incidents_query(db, statut, type_infraction, date_debut, date_fin).all()
    filtres = ", ".join(
        f"{k}={v}" for k, v in [("statut", statut), ("type", type_infraction),
                                 ("du", date_debut), ("au", date_fin)] if v
    ) or "aucun"
    buffer = build_pdf_report(
        titre="CrimTrack — Rapport d'incidents",
        sous_titre=f"Filtres : {filtres} — {len(incidents)} incident(s)",
        headers=_EXPORT_HEADERS,
        rows=(_incident_row(i) for i in incidents),
        genere_par=f"{current_user.prenom} {current_user.nom} ({current_user.role})",
    )

    audit.log(
        db, user=current_user, action="export", ressource_type="incident",
        details=f"Export PDF de {len(incidents)} incident(s)", request=request,
    )
    filename = f"incidents_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/carte.pdf")
def export_carte_pdf(
    statut: Optional[str] = None,
    type_infraction: Optional[str] = None,
    date_debut: Optional[datetime] = None,
    date_fin: Optional[datetime] = None,
    adresse: Optional[str] = None,
    rayon_metres: float = 500.0,
    min_incidents: int = 3,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    """Rapport cartographique imprimable pour un briefing d'unité (cahier des
    charges 3.1). Contrairement à `/export/pdf` (tableau seul), celui-ci
    dessine réellement les incidents géolocalisés et les hotspots détectés.
    """
    incidents = _filtered_incidents_query(db, statut, type_infraction, date_debut, date_fin, adresse).all()
    hotspots = get_hotspots(
        type_infraction=type_infraction, date_debut=date_debut, date_fin=date_fin,
        adresse=adresse, rayon_metres=rayon_metres, min_incidents=min_incidents, db=db,
    )
    filtres = ", ".join(
        f"{k}={v}" for k, v in [("statut", statut), ("type", type_infraction),
                                 ("zone", adresse), ("du", date_debut), ("au", date_fin)] if v
    ) or "aucun"
    buffer = build_map_pdf_report(
        titre="CrimTrack — Rapport cartographique",
        sous_titre=f"Filtres : {filtres} — {len(incidents)} incident(s), {len(hotspots)} hotspot(s)",
        incidents=incidents,
        hotspots=hotspots,
        genere_par=f"{current_user.prenom} {current_user.nom} ({current_user.role})",
    )

    audit.log(
        db, user=current_user, action="export", ressource_type="incident",
        details=f"Export carte PDF de {len(incidents)} incident(s) / {len(hotspots)} hotspot(s)", request=request,
    )
    filename = f"carte_incidents_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/analyse/hotspots", response_model=List[schemas.HotspotOut])
def get_hotspots(
    type_infraction: Optional[str] = None,
    date_debut: Optional[datetime] = None,
    date_fin: Optional[datetime] = None,
    adresse: Optional[str] = None,
    rayon_metres: float = 500.0,
    min_incidents: int = 3,
    db: Session = Depends(get_db),
):
    """Détection automatique de zones à forte concentration d'incidents
    (cahier des charges 3.1 : "Détection automatique de zones à forte
    concentration (hotspots)", exigence non fonctionnelle "< 2s").

    Deux implémentations, choisies automatiquement selon la base :
    - PostgreSQL/PostGIS (production, cf. docker-compose.yml qui utilise déjà
      l'image `postgis/postgis`) : clustering exécuté nativement en base via
      `ST_ClusterDBSCAN`, largement plus rapide qu'un aller-retour de toutes
      les lignes vers Python sur un gros volume.
    - SQLite (dev local, pas d'extension géospatiale) : repli sur l'ancien
      clustering par grille en Python, fonctionnellement équivalent mais pas
      dimensionné pour la production.

    Périmètre volontairement limité à l'agrégation géographique de faits
    déjà survenus (analyse rétrospective de zones), et non à une prédiction
    ou une notation d'individus — cf. cahier des charges 6.3.
    """
    if rayon_metres <= 0:
        raise HTTPException(status_code=422, detail="rayon_metres doit être positif")
    if min_incidents < 1:
        raise HTTPException(status_code=422, detail="min_incidents doit être >= 1")

    if db.bind.dialect.name == "postgresql":
        return _hotspots_postgis(db, type_infraction, date_debut, date_fin, adresse, rayon_metres, min_incidents)
    return _hotspots_python(db, type_infraction, date_debut, date_fin, adresse, rayon_metres, min_incidents)


def _hotspots_postgis(
    db: Session,
    type_infraction: Optional[str],
    date_debut: Optional[datetime],
    date_fin: Optional[datetime],
    adresse: Optional[str],
    rayon_metres: float,
    min_incidents: int,
) -> List[schemas.HotspotOut]:
    # Même approximation degrés/mètres que l'implémentation Python (voir
    # METRES_PAR_DEGRE_LAT) : suffisant à l'échelle d'une ville/région, et
    # garde un comportement cohérent entre les deux chemins.
    eps_degres = rayon_metres / METRES_PAR_DEGRE_LAT

    conditions = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    params: dict = {"eps_degres": eps_degres, "min_incidents": min_incidents}
    if type_infraction:
        conditions.append("type_infraction = :type_infraction")
        params["type_infraction"] = type_infraction
    if date_debut:
        conditions.append("date_heure >= :date_debut")
        params["date_debut"] = date_debut
    if date_fin:
        conditions.append("date_heure <= :date_fin")
        params["date_fin"] = date_fin
    if adresse:
        conditions.append("adresse ILIKE :adresse")
        params["adresse"] = f"%{adresse}%"
    where_clause = " AND ".join(conditions)

    sql = text(
        f"""
        WITH clustered AS (
            SELECT
                id,
                type_infraction,
                latitude,
                longitude,
                ST_ClusterDBSCAN(
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
                    eps := :eps_degres,
                    minpoints := :min_incidents
                ) OVER () AS cluster_id
            FROM incidents
            WHERE {where_clause}
        )
        SELECT
            AVG(latitude) AS lat_moy,
            AVG(longitude) AS lon_moy,
            COUNT(*) AS nb,
            array_agg(DISTINCT type_infraction ORDER BY type_infraction) AS types,
            array_agg(id) AS ids
        FROM clustered
        WHERE cluster_id IS NOT NULL
        GROUP BY cluster_id
        ORDER BY nb DESC
        """
    )
    rows = db.execute(sql, params).fetchall()
    return [
        schemas.HotspotOut(
            latitude=row.lat_moy,
            longitude=row.lon_moy,
            nombre_incidents=row.nb,
            types_infraction=list(row.types),
            rayon_metres=rayon_metres,
            incident_ids=list(row.ids),
        )
        for row in rows
    ]


def _hotspots_python(
    db: Session,
    type_infraction: Optional[str],
    date_debut: Optional[datetime],
    date_fin: Optional[datetime],
    adresse: Optional[str],
    rayon_metres: float,
    min_incidents: int,
) -> List[schemas.HotspotOut]:
    query = db.query(models.Incident).filter(
        models.Incident.latitude.isnot(None), models.Incident.longitude.isnot(None)
    )
    if type_infraction:
        query = query.filter(models.Incident.type_infraction == type_infraction)
    if date_debut:
        query = query.filter(models.Incident.date_heure >= date_debut)
    if date_fin:
        query = query.filter(models.Incident.date_heure <= date_fin)
    if adresse:
        query = query.filter(models.Incident.adresse.ilike(f"%{adresse}%"))

    incidents = query.all()
    if not incidents:
        return []

    # Taille de cellule en degrés, approximative (suffisant pour du
    # regroupement à l'échelle d'une ville/région).
    pas_lat = rayon_metres / METRES_PAR_DEGRE_LAT
    lat_ref = sum(i.latitude for i in incidents) / len(incidents)
    metres_par_degre_lon = METRES_PAR_DEGRE_LAT * max(math.cos(math.radians(lat_ref)), 0.01)
    pas_lon = rayon_metres / metres_par_degre_lon

    cellules: dict[tuple[int, int], list[models.Incident]] = defaultdict(list)
    for inc in incidents:
        cle = (round(inc.latitude / pas_lat), round(inc.longitude / pas_lon))
        cellules[cle].append(inc)

    hotspots: List[schemas.HotspotOut] = []
    for membres in cellules.values():
        if len(membres) < min_incidents:
            continue
        lat_moy = sum(m.latitude for m in membres) / len(membres)
        lon_moy = sum(m.longitude for m in membres) / len(membres)
        hotspots.append(
            schemas.HotspotOut(
                latitude=lat_moy,
                longitude=lon_moy,
                nombre_incidents=len(membres),
                types_infraction=sorted({m.type_infraction for m in membres}),
                rayon_metres=rayon_metres,
                incident_ids=[m.id for m in membres],
            )
        )

    hotspots.sort(key=lambda h: h.nombre_incidents, reverse=True)
    return hotspots


@router.get("/{incident_id}/chronologie", response_model=List[schemas.EvenementChronologieOut])
def get_chronologie(incident_id: str, db: Session = Depends(get_db)):
    """Chronologie des faits d'une affaire (cahier des charges 3.2).

    Fusionne :
    - les événements saisis manuellement (dépositions, constatations...) ;
    - les événements déjà tracés ailleurs et reconstitués à la volée pour
      ne rien dupliquer : chaque maillon de la chaîne de custody des
      preuves rattachées, et chaque ajout de pièce jointe.

    Le tout est trié chronologiquement pour donner une vue unique du
    déroulé de l'affaire, plutôt que de forcer l'enquêteur à recouper
    manuellement plusieurs onglets (preuves / custody / pièces jointes).
    """
    incident = db.query(models.Incident).filter(models.Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident introuvable")

    evenements: List[schemas.EvenementChronologieOut] = [
        schemas.EvenementChronologieOut.model_validate(e) for e in incident.chronologie
    ]

    preuve_ids = [p.id for p in incident.preuves]
    if preuve_ids:
        for cc in (
            db.query(models.ChaineCustody)
            .filter(models.ChaineCustody.preuve_id.in_(preuve_ids))
            .order_by(models.ChaineCustody.date_heure)
            .all()
        ):
            evenements.append(
                schemas.EvenementChronologieOut(
                    id=f"auto-custody-{cc.id}",
                    incident_id=incident_id,
                    date_heure=cc.date_heure,
                    titre=f"Chaîne de custody — {cc.action}",
                    description=f"Preuve {cc.preuve_id}",
                    origine="auto",
                    ressource_type="chaine_custody",
                    ressource_id=cc.id,
                    auteur_id=cc.utilisateur_id,
                    date_creation=cc.date_heure,
                )
            )
        for pj in (
            db.query(models.PieceJointe)
            .filter(models.PieceJointe.preuve_id.in_(preuve_ids))
            .order_by(models.PieceJointe.date_ajout)
            .all()
        ):
            evenements.append(
                schemas.EvenementChronologieOut(
                    id=f"auto-piece-{pj.id}",
                    incident_id=incident_id,
                    date_heure=pj.date_ajout,
                    titre=f"Pièce jointe ajoutée — {pj.nom_fichier}",
                    description=f"Preuve {pj.preuve_id}",
                    origine="auto",
                    ressource_type="piece_jointe",
                    ressource_id=pj.id,
                    auteur_id=pj.ajoute_par_id,
                    date_creation=pj.date_ajout,
                )
            )

    evenements.sort(key=lambda e: e.date_heure)
    return evenements


@router.post("/{incident_id}/chronologie", response_model=schemas.EvenementChronologieOut, status_code=201)
def create_evenement_chronologie(
    incident_id: str,
    payload: schemas.EvenementChronologieCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    incident = db.query(models.Incident).filter(models.Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident introuvable")

    evenement = models.EvenementChronologie(
        incident_id=incident_id,
        date_heure=payload.date_heure,
        titre=payload.titre,
        description=payload.description,
        origine="manuel",
        auteur_id=current_user.id,
    )
    db.add(evenement)
    db.commit()
    db.refresh(evenement)

    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="evenement_chronologie",
        ressource_id=evenement.id,
        details=f"Événement ajouté à la chronologie de l'incident {incident_id}",
        request=request,
    )
    return evenement


@router.get("/{incident_id}", response_model=schemas.IncidentOut)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(models.Incident).filter(models.Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident introuvable")
    return incident


@router.post("", response_model=schemas.IncidentOut, status_code=201)
def create_incident(
    payload: schemas.IncidentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    incident = models.Incident(**payload.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)

    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="incident",
        ressource_id=incident.id,
        request=request,
    )
    return incident
