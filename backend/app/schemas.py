from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


class IncidentBase(BaseModel):
    type_infraction: str
    date_heure: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    adresse: Optional[str] = None
    statut: str = "ouvert"
    gravite: str = "faible"
    unite_en_charge: Optional[str] = None


class IncidentCreate(IncidentBase):
    pass


class IncidentOut(IncidentBase):
    model_config = ConfigDict(from_attributes=True)
    id: str


# ---------------------------------------------------------------------------
# Personnes
# ---------------------------------------------------------------------------


class PersonneBase(BaseModel):
    nom: str
    prenom: str
    date_naissance: Optional[datetime] = None
    role: Optional[str] = None
    signalement: Optional[str] = None
    photo_ref: Optional[str] = None
    statut: Optional[str] = None


class PersonneCreate(PersonneBase):
    pass


class PersonneOut(PersonneBase):
    model_config = ConfigDict(from_attributes=True)
    id: str


# ---------------------------------------------------------------------------
# Véhicules
# ---------------------------------------------------------------------------


class VehiculeBase(BaseModel):
    plaque_immatriculation: str
    marque: Optional[str] = None
    modele: Optional[str] = None
    couleur: Optional[str] = None
    proprietaire_id: Optional[str] = None
    statut: Optional[str] = None


class VehiculeCreate(VehiculeBase):
    pass


class VehiculeOut(VehiculeBase):
    model_config = ConfigDict(from_attributes=True)
    id: str


# ---------------------------------------------------------------------------
# Relations (table brute)
# ---------------------------------------------------------------------------


class RelationBase(BaseModel):
    personne_a_id: str
    personne_b_id: str
    type_relation: str
    source_incident_id: Optional[str] = None
    poids: int = 1


class RelationCreate(RelationBase):
    pass


class RelationOut(RelationBase):
    model_config = ConfigDict(from_attributes=True)
    id: str


# ---------------------------------------------------------------------------
# Graphe de relations (Module 3, format consommé par le frontend)
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    id: str
    type: str  # "personne" | "vehicule" | "lieu"
    label: str
    role: Optional[str] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type_relation: str
    poids: int
    source_incident_id: Optional[str] = None


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class CheminResponse(BaseModel):
    """Résultat d'une recherche de chemin entre deux individus (cahier des
    charges 3.3)."""

    trouve: bool
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    longueur: int = 0


# ---------------------------------------------------------------------------
# Authentification / Utilisateurs (RBAC — cahier des charges 4.3)
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    nom: str
    prenom: str
    role: str = "enqueteur"  # enqueteur | analyste | opj | administrateur


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    nom: str
    prenom: str
    role: str
    actif: bool
    date_creation: datetime


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    nom: str
    prenom: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Preuves & chaîne de custody (Module 2, cahier des charges 3.2)
# ---------------------------------------------------------------------------


class PreuveBase(BaseModel):
    incident_id: str
    type: Optional[str] = None
    description: Optional[str] = None
    localisation_stockage: Optional[str] = None


class PreuveCreate(PreuveBase):
    pass


class PreuveOut(PreuveBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hash_integrite: Optional[str] = None


class ChaineCustodyCreate(BaseModel):
    action: str  # collecte / transfert / analyse / restitution...
    # Pas de champ "utilisateur_id" ici : l'agent est dérivé de l'utilisateur
    # authentifié (JWT), jamais fourni par le client — voir
    # app/routers/preuves.py. Avant correction, ce champ existait
    # (`personne_id`) et pointait vers un suspect/témoin au lieu de l'agent
    # réel, en plus de permettre à n'importe quel appelant de désigner
    # n'importe qui comme dépositaire de la preuve.


class ChaineCustodyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    preuve_id: str
    utilisateur_id: str
    date_heure: datetime
    action: str
    horodatage_hash: Optional[str] = None


class ChaineCustodyChainOut(BaseModel):
    """Chaîne de custody d'une preuve, avec vérification d'intégrité (hash-chain)."""

    preuve_id: str
    evenements: List[ChaineCustodyOut]
    chaine_intacte: bool
    alerte_rupture: bool


# ---------------------------------------------------------------------------
# Pièces jointes (Module 2, cahier des charges 3.2 : "témoins, preuves,
# pièces jointes, chronologie")
# ---------------------------------------------------------------------------


class PieceJointeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    preuve_id: str
    nom_fichier: str
    type_mime: Optional[str] = None
    taille_octets: int
    hash_sha256: str
    ajoute_par_id: Optional[str] = None
    date_ajout: datetime


# ---------------------------------------------------------------------------
# Lectures ANPR (Module 4, cahier des charges 3.4)
# ---------------------------------------------------------------------------


class LectureAnprCreate(BaseModel):
    plaque_lue: str
    date_heure: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    camera_id: Optional[str] = None
    confiance_ocr: Optional[float] = None


class LectureAnprOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    plaque_lue: str
    date_heure: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    camera_id: Optional[str] = None
    confiance_ocr: Optional[float] = None
    vehicule_id: Optional[str] = None
    source: str = "manuel"
    image_chemin: Optional[str] = None
    video_chemin: Optional[str] = None
    video_timestamp_s: Optional[float] = None


class LectureAnprResult(BaseModel):
    """Résultat d'une lecture ANPR après rapprochement automatique (cahier 3.4)."""

    lecture: LectureAnprOut
    vehicule_reconnu: Optional[VehiculeOut] = None
    alerte: bool = False
    motif_alerte: Optional[str] = None


class CandidatPlaqueOut(BaseModel):
    """Un candidat de lecture détecté sur l'image (avant sélection)."""

    texte: str
    confiance: float
    bbox: List[int]  # [x, y, w, h] dans le repère de l'image source
    format_reconnu: bool = False


class DetectionAnprResult(BaseModel):
    """Résultat du pipeline de détection+OCR sur une image téléversée
    (POST /anpr/lectures/depuis-image).

    `lecture` reprend le meilleur candidat (confiance la plus haute) et a
    déjà été enregistrée + rapprochée avec la base véhicules, comme pour une
    lecture manuelle. `candidats` liste toutes les lectures alternatives
    détectées, pour qu'un agent puisse corriger une lecture erronée sans
    reprendre la photo (cf. `PATCH /anpr/lectures/{id}`).
    """

    lecture: LectureAnprOut
    vehicule_reconnu: Optional[VehiculeOut] = None
    alerte: bool = False
    motif_alerte: Optional[str] = None
    candidats: List[CandidatPlaqueOut] = []


class LectureAnprCorrection(BaseModel):
    """Correction manuelle de la plaque lue par le pipeline automatique
    (l'OCR n'est jamais garanti à 100% — un agent doit pouvoir corriger)."""

    plaque_lue: str


class LectureVideoItem(BaseModel):
    """Une lecture issue de la détection vidéo (une par plaque distincte
    trouvée sur la vidéo/le flux, cf. DetectionAnprVideoResult)."""

    lecture: LectureAnprOut
    vehicule_reconnu: Optional[VehiculeOut] = None
    alerte: bool = False
    motif_alerte: Optional[str] = None
    timestamp_s: float


class DetectionAnprVideoResult(BaseModel):
    """Résultat du pipeline de détection+OCR sur une vidéo téléversée ou un
    flux caméra (POST /anpr/lectures/depuis-video).

    Une lecture est créée par plaque distincte détectée (pas par frame —
    voir `app/anpr_engine.detecter_plaques_video`), chacune rapprochée
    individuellement avec la base véhicules comme pour une lecture image.
    """

    lectures: List[LectureVideoItem]
    frames_analysees: int
    duree_video_s: Optional[float] = None


# ---------------------------------------------------------------------------
# Hotspots (Module 1, cahier des charges 3.1)
# ---------------------------------------------------------------------------


class HotspotOut(BaseModel):
    latitude: float
    longitude: float
    nombre_incidents: int
    types_infraction: List[str]
    rayon_metres: float
    incident_ids: List[str]


# ---------------------------------------------------------------------------
# Audit trail (cahier des charges 2.2 / 4.3 / 6.2)
# ---------------------------------------------------------------------------


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    utilisateur_email: Optional[str] = None
    action: str
    ressource_type: str
    ressource_id: Optional[str] = None
    date_heure: datetime
    details: Optional[str] = None
    adresse_ip: Optional[str] = None


# ---------------------------------------------------------------------------
# Chronologie des faits (Module 2 — cahier des charges 3.2)
# ---------------------------------------------------------------------------


class EvenementChronologieCreate(BaseModel):
    date_heure: datetime
    titre: str
    description: Optional[str] = None


class EvenementChronologieOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    incident_id: str
    date_heure: datetime
    titre: str
    description: Optional[str] = None
    origine: str
    ressource_type: Optional[str] = None
    ressource_id: Optional[str] = None
    auteur_id: Optional[str] = None
    date_creation: datetime


# --- Intégrations systèmes nationaux (cahier des charges 2.3) -------------


class RapprochementPersonneIn(BaseModel):
    nom: str
    prenom: str
    date_naissance: Optional[str] = None


class RapprochementPersonneOut(BaseModel):
    trouve: bool
    source_systeme: str
    reference_externe: Optional[str] = None
    signalements: Optional[List[str]] = None
    horodatage_reponse: Optional[str] = None


class RapprochementVehiculeIn(BaseModel):
    plaque_immatriculation: str


class RapprochementVehiculeOut(BaseModel):
    trouve: bool
    source_systeme: str
    reference_externe: Optional[str] = None
    statut_externe: Optional[str] = None
    horodatage_reponse: Optional[str] = None
