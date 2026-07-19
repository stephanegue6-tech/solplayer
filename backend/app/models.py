import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import relationship

from .database import Base


def _uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Rôles RBAC (cahier des charges 4.3) : enquêteur, analyste, OPJ, administrateur
# ---------------------------------------------------------------------------

ROLES = ("enqueteur", "analyste", "opj", "administrateur")


# ---------------------------------------------------------------------------
# Tables de liaison plusieurs-à-plusieurs (cf. cahier des charges 4.1)
# ---------------------------------------------------------------------------

incident_personnes = Table(
    "incident_personnes",
    Base.metadata,
    Column("incident_id", String, ForeignKey("incidents.id"), primary_key=True),
    Column("personne_id", String, ForeignKey("personnes.id"), primary_key=True),
    Column("role_dans_incident", String, nullable=True),
)

incident_vehicules = Table(
    "incident_vehicules",
    Base.metadata,
    Column("incident_id", String, ForeignKey("incidents.id"), primary_key=True),
    Column("vehicule_id", String, ForeignKey("vehicules.id"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Tables centrales
# ---------------------------------------------------------------------------


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=_uuid)
    type_infraction = Column(String, nullable=False, index=True)
    date_heure = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    adresse = Column(String, nullable=True)
    statut = Column(String, nullable=False, default="ouvert", index=True)
    gravite = Column(String, nullable=False, default="faible")
    unite_en_charge = Column(String, nullable=True)

    preuves = relationship("Preuve", back_populates="incident")
    personnes = relationship("Personne", secondary=incident_personnes, back_populates="incidents")
    vehicules = relationship("Vehicule", secondary=incident_vehicules, back_populates="incidents")
    chronologie = relationship(
        "EvenementChronologie", back_populates="incident", order_by="EvenementChronologie.date_heure"
    )


class Personne(Base):
    __tablename__ = "personnes"

    id = Column(String, primary_key=True, default=_uuid)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    date_naissance = Column(DateTime, nullable=True)
    role = Column(String, nullable=True)  # suspect / victime / témoin...
    signalement = Column(String, nullable=True)
    photo_ref = Column(String, nullable=True)
    statut = Column(String, nullable=True)

    incidents = relationship("Incident", secondary=incident_personnes, back_populates="personnes")
    vehicules_possedes = relationship("Vehicule", back_populates="proprietaire")


class Vehicule(Base):
    __tablename__ = "vehicules"

    id = Column(String, primary_key=True, default=_uuid)
    plaque_immatriculation = Column(String, nullable=False, unique=True, index=True)
    marque = Column(String, nullable=True)
    modele = Column(String, nullable=True)
    couleur = Column(String, nullable=True)
    proprietaire_id = Column(String, ForeignKey("personnes.id"), nullable=True)
    statut = Column(String, nullable=True)  # normal / signalé / volé

    proprietaire = relationship("Personne", back_populates="vehicules_possedes")
    incidents = relationship("Incident", secondary=incident_vehicules, back_populates="vehicules")
    lectures_anpr = relationship("LectureAnpr", back_populates="vehicule")


class Preuve(Base):
    __tablename__ = "preuves"

    id = Column(String, primary_key=True, default=_uuid)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=False)
    type = Column(String, nullable=True)
    description = Column(String, nullable=True)
    hash_integrite = Column(String, nullable=True)
    localisation_stockage = Column(String, nullable=True)

    incident = relationship("Incident", back_populates="preuves")
    chaine_custody = relationship("ChaineCustody", back_populates="preuve")
    pieces_jointes = relationship("PieceJointe", back_populates="preuve", cascade="all, delete-orphan")


class ChaineCustody(Base):
    """Horodatage infalsifiable de chaque manipulation de preuve (hash-chain).

    ⚠️ `utilisateur_id` référence l'AGENT (compte RBAC, table `utilisateurs`)
    qui a manipulé la preuve — pas un suspect/témoin de la table `personnes`.
    Avant correction, ce champ pointait par erreur vers `personnes`, ce qui
    aurait permis d'attribuer la garde d'une preuve à un suspect au lieu de
    l'enquêteur/OPJ réel. Il est désormais dérivé automatiquement de
    l'utilisateur authentifié (JWT) plutôt que fourni par le client — voir
    app/routers/preuves.py — pour empêcher toute usurpation d'identité dans
    la chaîne de custody.
    """

    __tablename__ = "chaine_custody"

    id = Column(String, primary_key=True, default=_uuid)
    preuve_id = Column(String, ForeignKey("preuves.id"), nullable=False)
    utilisateur_id = Column(String, ForeignKey("utilisateurs.id"), nullable=False)
    date_heure = Column(DateTime, nullable=False, default=datetime.utcnow)
    action = Column(String, nullable=False)  # collecte / transfert / analyse / restitution...
    horodatage_hash = Column(String, nullable=True)

    preuve = relationship("Preuve", back_populates="chaine_custody")
    utilisateur = relationship("Utilisateur", back_populates="garde_de_preuves")


class PieceJointe(Base):
    """Fichier rattaché à une preuve (cahier des charges 3.2 : "témoins,
    preuves, pièces jointes, chronologie"). Le fichier lui-même est stocké
    sur disque (voir STORAGE_DIR dans app/storage.py) ; cette table ne
    conserve que les métadonnées + un hash SHA-256 du contenu, qui permet de
    vérifier a posteriori que le fichier n'a pas été altéré (même logique
    d'intégrité que la chaîne de custody).
    """

    __tablename__ = "pieces_jointes"

    id = Column(String, primary_key=True, default=_uuid)
    preuve_id = Column(String, ForeignKey("preuves.id"), nullable=False)
    nom_fichier = Column(String, nullable=False)
    chemin_stockage = Column(String, nullable=False)
    type_mime = Column(String, nullable=True)
    taille_octets = Column(Integer, nullable=False, default=0)
    hash_sha256 = Column(String, nullable=False)
    ajoute_par_id = Column(String, ForeignKey("utilisateurs.id"), nullable=True)
    date_ajout = Column(DateTime, nullable=False, default=datetime.utcnow)

    preuve = relationship("Preuve", back_populates="pieces_jointes")
    ajoute_par = relationship("Utilisateur")


class EvenementChronologie(Base):
    """Chronologie des faits d'une affaire (cahier des charges 3.2 : "Fiche
    d'affaire centralisée : témoins, preuves, pièces jointes, chronologie
    des faits."). Jusqu'ici, il n'existait pas d'objet dédié pour ça : seule
    la date de l'incident et les horodatages de la chaîne de custody étaient
    disponibles, ce qui ne permet pas de documenter le déroulé des faits
    eux-mêmes (dépositions, constatations, actes d'enquête...).

    Deux origines possibles, distinguées par `origine` :
    - "manuel" : saisi par un enquêteur/OPJ (déposition d'un témoin, fait
      constaté, acte de procédure...) ;
    - "auto" : généré automatiquement pour relier un événement déjà tracé
      ailleurs (ajout d'une preuve, maillon de chaîne de custody) sans dupliquer
      la donnée — seule une référence (`ressource_type`/`ressource_id`) est
      stockée, pas de copie du contenu.
    """

    __tablename__ = "evenements_chronologie"

    id = Column(String, primary_key=True, default=_uuid)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=False, index=True)
    date_heure = Column(DateTime, nullable=False, index=True)
    titre = Column(String, nullable=False)
    description = Column(String, nullable=True)
    origine = Column(String, nullable=False, default="manuel")  # manuel / auto
    ressource_type = Column(String, nullable=True)  # ex: "preuve", "chaine_custody" si origine=auto
    ressource_id = Column(String, nullable=True)
    auteur_id = Column(String, ForeignKey("utilisateurs.id"), nullable=True)
    date_creation = Column(DateTime, nullable=False, default=datetime.utcnow)

    incident = relationship("Incident", back_populates="chronologie")
    auteur = relationship("Utilisateur")


class Relation(Base):
    """Lien personne-personne, utilisé pour construire le graphe (Module 3)."""

    __tablename__ = "relations"

    id = Column(String, primary_key=True, default=_uuid)
    personne_a_id = Column(String, ForeignKey("personnes.id"), nullable=False)
    personne_b_id = Column(String, ForeignKey("personnes.id"), nullable=False)
    type_relation = Column(String, nullable=False)
    source_incident_id = Column(String, ForeignKey("incidents.id"), nullable=True)
    poids = Column(Integer, nullable=False, default=1)


class LectureAnpr(Base):
    __tablename__ = "lectures_anpr"

    id = Column(String, primary_key=True, default=_uuid)
    plaque_lue = Column(String, nullable=False, index=True)
    date_heure = Column(DateTime, nullable=False, default=datetime.utcnow)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    camera_id = Column(String, nullable=True)
    confiance_ocr = Column(Float, nullable=True)
    vehicule_id = Column(String, ForeignKey("vehicules.id"), nullable=True)

    # Source de la lecture : "manuel" (plaque saisie/transmise déjà décodée,
    # comportement d'origine du module), "image" (détection + OCR locaux à
    # partir d'une image téléversée) ou "video" (idem à partir d'une vidéo
    # téléversée ou d'un flux caméra) — voir app/anpr_engine.py.
    source = Column(String, nullable=False, default="manuel")
    image_chemin = Column(String, nullable=True)
    image_hash_sha256 = Column(String, nullable=True)
    video_chemin = Column(String, nullable=True)
    video_timestamp_s = Column(Float, nullable=True)

    vehicule = relationship("Vehicule", back_populates="lectures_anpr")


# ---------------------------------------------------------------------------
# Authentification / RBAC (cahier des charges 4.3)
# ---------------------------------------------------------------------------


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    role = Column(String, nullable=False, default="enqueteur")  # cf. ROLES
    actif = Column(Boolean, nullable=False, default=True)
    date_creation = Column(DateTime, nullable=False, default=datetime.utcnow)

    garde_de_preuves = relationship("ChaineCustody", back_populates="utilisateur")


# ---------------------------------------------------------------------------
# Journalisation (audit trail) — cahier des charges 2.2 / 4.3 / 6.2 :
# traçabilité de chaque consultation et modification.
# ---------------------------------------------------------------------------


class JournalAudit(Base):
    __tablename__ = "journal_audit"

    id = Column(String, primary_key=True, default=_uuid)
    utilisateur_id = Column(String, ForeignKey("utilisateurs.id"), nullable=True)
    utilisateur_email = Column(String, nullable=True)  # snapshot, survit à une suppression de compte
    action = Column(String, nullable=False, index=True)  # connexion / echec_connexion / creation / consultation / modification
    ressource_type = Column(String, nullable=False, index=True)
    ressource_id = Column(String, nullable=True, index=True)
    date_heure = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    details = Column(String, nullable=True)
    adresse_ip = Column(String, nullable=True)


# ---------------------------------------------------------------------------
# Cycle de vie des tokens JWT (révocation + rotation) — corrige l'absence
# totale de révocation/rotation signalée sur la version précédente : sans
# ça, un token volé restait valide jusqu'à sa date d'expiration naturelle,
# même après une déconnexion explicite.
# ---------------------------------------------------------------------------


class RefreshToken(Base):
    """Jeton de rafraîchissement longue durée, à rotation à chaque usage :
    utiliser un refresh token en génère un nouveau et invalide l'ancien
    (`revoked=True`), ce qui permet de détecter un vol (réutilisation d'un
    token déjà consommé). Seul le hash SHA-256 du token est stocké, jamais
    le token en clair (même logique qu'un mot de passe).
    """

    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    utilisateur_id = Column(String, ForeignKey("utilisateurs.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    date_creation = Column(DateTime, nullable=False, default=datetime.utcnow)
    date_expiration = Column(DateTime, nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)


class RevokedAccessToken(Base):
    """Liste noire des access tokens (JWT) explicitement révoqués avant leur
    expiration naturelle (déconnexion, compte désactivé...). On ne stocke
    que le `jti` (identifiant unique du token) + sa date d'expiration
    d'origine, pour purger la ligne une fois le token expiré de toute façon.
    """

    __tablename__ = "revoked_access_tokens"

    jti = Column(String, primary_key=True)
    date_expiration = Column(DateTime, nullable=False)
