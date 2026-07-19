"""Point d'intégration avec les systèmes nationaux existants — cahier des
charges section 2.3 :

    "Intégration directe avec les systèmes nationaux existants (à évaluer
    en phase ultérieure, sous convention)."

Ce module ne se connecte à AUCUN système externe réel : aucune convention
n'est signée à ce stade, donc aucune donnée ne doit sortir de CrimTrack ni
y entrer par cette voie tant qu'une base légale et une convention formelle
ne sont pas en place. Ce qui est fourni ici est le POINT D'EXTENSION :
une interface stable, testable, et clairement gardée par un interrupteur
de configuration, sur laquelle un vrai connecteur pourra être branché une
fois la convention signée.

Principes de conception :

- Pattern adaptateur : `SystemeNationalAdapter` définit le contrat que
  tout futur connecteur (fichier des véhicules volés, fichier des
  personnes recherchées, etc.) doit respecter. Un connecteur réel se
  branche en implémentant cette classe, sans toucher aux routers.
- Fermé par défaut : `actif` doit être explicitement mis à True via
  variable d'environnement (ex. `SYSTEME_XYZ_ACTIF=true`) ET une
  référence de convention (`SYSTEME_XYZ_CONVENTION_REF`) doit être
  renseignée. Sans ces deux éléments, l'appel échoue proprement avec un
  message explicite plutôt que d'échouer silencieusement ou d'inventer
  une réponse.
- Traçabilité : toute tentative d'appel (réussie ou non) est journalisée
  dans le journal d'audit, y compris l'identité du système visé — cf.
  cahier des charges 6.2 "traçabilité de chaque consultation".
- Aucun secret ne transite par le code : les identifiants de connexion à
  un futur système national viennent uniquement de variables
  d'environnement (voir `.env.example`), jamais en dur dans le dépôt.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


class SystemeNonConfigureError(Exception):
    """Levée quand un système national n'est pas activé/conventionné."""

    def __init__(self, code_systeme: str):
        self.code_systeme = code_systeme
        super().__init__(
            f"Le système national « {code_systeme} » n'est pas activé. "
            "Une convention formelle et une configuration explicite "
            "(SYSTEME_{CODE}_ACTIF, SYSTEME_{CODE}_CONVENTION_REF) sont "
            "requises avant tout appel réel — voir national_systems.py."
        )


@dataclass
class ResultatRapprochementPersonne:
    trouve: bool
    source_systeme: str
    reference_externe: Optional[str] = None
    signalements: Optional[List[str]] = None
    horodatage_reponse: Optional[str] = None


@dataclass
class ResultatRapprochementVehicule:
    trouve: bool
    source_systeme: str
    reference_externe: Optional[str] = None
    statut_externe: Optional[str] = None
    horodatage_reponse: Optional[str] = None


class SystemeNationalAdapter(ABC):
    """Contrat que doit respecter tout connecteur vers un système national.

    Un vrai connecteur (ex. vers un fichier national des véhicules volés)
    hérite de cette classe et implémente les deux méthodes ci-dessous en
    y mettant l'appel réseau réel (avec authentification, mTLS, etc. selon
    les exigences de la convention signée avec l'organisme concerné).
    """

    code: str
    libelle: str

    @abstractmethod
    def rapprocher_personne(self, nom: str, prenom: str, date_naissance: Optional[str] = None) -> ResultatRapprochementPersonne:
        ...

    @abstractmethod
    def rapprocher_vehicule(self, plaque_immatriculation: str) -> ResultatRapprochementVehicule:
        ...


class _AdapterNonConfigure(SystemeNationalAdapter):
    """Adaptateur de repli : lève systématiquement une erreur explicite.

    Utilisé tant qu'aucun connecteur réel n'a été branché pour ce système,
    ou tant que la convention/activation n'est pas confirmée par la
    configuration.
    """

    def __init__(self, code: str, libelle: str):
        self.code = code
        self.libelle = libelle

    def rapprocher_personne(self, nom, prenom, date_naissance=None):
        raise SystemeNonConfigureError(self.code)

    def rapprocher_vehicule(self, plaque_immatriculation):
        raise SystemeNonConfigureError(self.code)


# Registre des systèmes nationaux prévus (extensible). Ajouter une entrée
# ici ne les active pas : ça les rend seulement visibles/configurables.
SYSTEMES_CONNUS = {
    "fnpc": "Fichier national des personnes recherchées (exemple générique)",
    "fnvv": "Fichier national des véhicules volés (exemple générique)",
}


def _est_actif(code: str) -> bool:
    env_actif = os.getenv(f"SYSTEME_{code.upper()}_ACTIF", "false").lower() == "true"
    convention_ref = os.getenv(f"SYSTEME_{code.upper()}_CONVENTION_REF", "").strip()
    return env_actif and bool(convention_ref)


def get_adapter(code: str) -> SystemeNationalAdapter:
    """Retourne l'adaptateur pour un système national donné.

    Tant qu'aucun connecteur réel n'est enregistré (voir
    `enregistrer_adapter`) et/ou que le système n'est pas activé par
    convention, retourne l'adaptateur de repli qui refuse tout appel.
    """
    if code not in SYSTEMES_CONNUS:
        raise ValueError(f"Système national inconnu : {code}")
    adapter = _REGISTRE.get(code)
    if adapter is not None and _est_actif(code):
        return adapter
    return _AdapterNonConfigure(code, SYSTEMES_CONNUS[code])


_REGISTRE: dict[str, SystemeNationalAdapter] = {}


def enregistrer_adapter(adapter: SystemeNationalAdapter) -> None:
    """Point d'extension pour brancher un vrai connecteur.

    Exemple d'usage futur, une fois une convention signée avec
    l'organisme gestionnaire du FNPC :

        from .connecteurs.fnpc_reel import ConnecteurFnpc
        national_systems.enregistrer_adapter(ConnecteurFnpc())

    Le connecteur reste inactif tant que SYSTEME_FNPC_ACTIF et
    SYSTEME_FNPC_CONVENTION_REF ne sont pas positionnés dans
    l'environnement de déploiement.
    """
    _REGISTRE[adapter.code] = adapter


def statut_systemes() -> List[dict]:
    """Vue d'ensemble pour l'endpoint d'administration."""
    out = []
    for code, libelle in SYSTEMES_CONNUS.items():
        out.append(
            {
                "code": code,
                "libelle": libelle,
                "connecteur_enregistre": code in _REGISTRE,
                "actif": _est_actif(code),
                "convention_reference": os.getenv(f"SYSTEME_{code.upper()}_CONVENTION_REF") or None,
            }
        )
    return out
