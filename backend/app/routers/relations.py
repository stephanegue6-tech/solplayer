import hashlib
from collections import deque
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit, auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/relations", tags=["relations"], dependencies=[Depends(auth.get_current_user)])


def _personne_label(personne: models.Personne) -> str:
    initiale = personne.prenom[:1].upper() if personne.prenom else ""
    return f"{initiale}. {personne.nom}" if initiale else personne.nom


def _lieu_id(adresse: str) -> str:
    """Identifiant stable d'un lieu à partir de son adresse : deux incidents
    à la même adresse (au casse/espaces près) se rattachent au même nœud
    "lieu", ce qui fait ressortir les adresses récurrentes dans le graphe.
    Préfixé "lieu-" pour ne jamais entrer en collision avec un UUID de
    personne/véhicule.
    """
    cle = " ".join(adresse.strip().lower().split())
    return "lieu-" + hashlib.md5(cle.encode("utf-8")).hexdigest()[:12]


def _collect_edges(
    db: Session, type_relation: Optional[str], poids_min: Optional[int]
) -> Tuple[List[schemas.GraphEdge], Dict[str, str]]:
    """Construit toutes les arêtes du graphe de relations (cahier des
    charges 3.3), à partir de quatre sources — une seule table saisie
    manuellement, les trois autres déduites automatiquement pour éviter
    toute ressaisie :

    - `relations` : liens personne <-> personne saisis ou déduits des
      rapports d'incidents communs ;
    - `vehicules.proprietaire_id` : lien "proprietaire" personne <-> véhicule ;
    - incidents multi-rattachés : lien "vu_ensemble" personne <-> véhicule
      quand les deux sont rattachés au même incident (au-delà du seul lien
      de propriété — ex. un véhicule prêté ou volé impliqué avec quelqu'un
      d'autre que son propriétaire) ;
    - adresse des incidents : lien "lieu_incident" personne/véhicule <-> lieu,
      pour faire apparaître les lieux comme nœuds à part entière du graphe
      (cahier 3.3 : "liens entre individus, véhicules et lieux").

    Retourne aussi `lieu_labels` (id de lieu -> libellé d'adresse), car les
    lieux n'ont pas de table dédiée : ils sont reconstitués à la volée.
    """
    edges: List[schemas.GraphEdge] = []
    lieu_labels: Dict[str, str] = {}

    relations_query = db.query(models.Relation)
    if type_relation:
        relations_query = relations_query.filter(models.Relation.type_relation == type_relation)
    if poids_min is not None:
        relations_query = relations_query.filter(models.Relation.poids >= poids_min)
    for rel in relations_query.all():
        edges.append(
            schemas.GraphEdge(
                id=rel.id,
                source=rel.personne_a_id,
                target=rel.personne_b_id,
                type_relation=rel.type_relation,
                poids=rel.poids,
                source_incident_id=rel.source_incident_id,
            )
        )

    if not type_relation or type_relation == "proprietaire":
        poids = 10
        if poids_min is None or poids >= poids_min:
            for vehicule in db.query(models.Vehicule).filter(models.Vehicule.proprietaire_id.isnot(None)).all():
                edges.append(
                    schemas.GraphEdge(
                        id=f"own-{vehicule.id}",
                        source=vehicule.proprietaire_id,
                        target=vehicule.id,
                        type_relation="proprietaire",
                        poids=poids,
                        source_incident_id=None,
                    )
                )

    need_incidents = (not type_relation) or type_relation in ("vu_ensemble", "lieu_incident")
    if need_incidents:
        incidents = db.query(models.Incident).all()
        for inc in incidents:
            if (not type_relation or type_relation == "vu_ensemble") and (poids_min is None or 3 >= poids_min):
                for p in inc.personnes:
                    for v in inc.vehicules:
                        edges.append(
                            schemas.GraphEdge(
                                id=f"co-{inc.id}-{p.id}-{v.id}",
                                source=p.id,
                                target=v.id,
                                type_relation="vu_ensemble",
                                poids=3,
                                source_incident_id=inc.id,
                            )
                        )

            if (not type_relation or type_relation == "lieu_incident") and inc.adresse and (poids_min is None or 1 >= poids_min):
                lieu_id = _lieu_id(inc.adresse)
                lieu_labels.setdefault(lieu_id, inc.adresse.strip())
                for p in inc.personnes:
                    edges.append(
                        schemas.GraphEdge(
                            id=f"lieu-{inc.id}-p-{p.id}",
                            source=p.id,
                            target=lieu_id,
                            type_relation="lieu_incident",
                            poids=1,
                            source_incident_id=inc.id,
                        )
                    )
                for v in inc.vehicules:
                    edges.append(
                        schemas.GraphEdge(
                            id=f"lieu-{inc.id}-v-{v.id}",
                            source=v.id,
                            target=lieu_id,
                            type_relation="lieu_incident",
                            poids=1,
                            source_incident_id=inc.id,
                        )
                    )

    return edges, lieu_labels


def _build_nodes(db: Session, node_ids: set, lieu_labels: Dict[str, str]) -> List[schemas.GraphNode]:
    nodes: List[schemas.GraphNode] = []
    if not node_ids:
        return nodes

    for p in db.query(models.Personne).filter(models.Personne.id.in_(node_ids)).all():
        nodes.append(schemas.GraphNode(id=p.id, type="personne", label=_personne_label(p), role=p.role))

    for v in db.query(models.Vehicule).filter(models.Vehicule.id.in_(node_ids)).all():
        nodes.append(schemas.GraphNode(id=v.id, type="vehicule", label=v.plaque_immatriculation, role=v.statut))

    for node_id in node_ids:
        if node_id.startswith("lieu-") and node_id in lieu_labels:
            nodes.append(schemas.GraphNode(id=node_id, type="lieu", label=lieu_labels[node_id], role=None))

    return nodes


@router.get("", response_model=List[schemas.RelationOut])
def list_relations(db: Session = Depends(get_db)):
    return db.query(models.Relation).all()


@router.post("", response_model=schemas.RelationOut, status_code=201)
def create_relation(
    payload: schemas.RelationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.require_write),
):
    relation = models.Relation(**payload.model_dump())
    db.add(relation)
    db.commit()
    db.refresh(relation)

    audit.log(
        db,
        user=current_user,
        action="creation",
        ressource_type="relation",
        ressource_id=relation.id,
        request=request,
    )
    return relation


@router.get("/graphe", response_model=schemas.GraphResponse)
def get_graphe(
    type_relation: Optional[str] = None,
    poids_min: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Construction automatique du graphe de relations (cahier des charges 3.3) :
    individus, véhicules et lieux (cf. `_collect_edges`), filtrable par type
    de lien et par force minimale.

    Consommé par l'écran Réseaux criminels du frontend (`RelationsPage` /
    `RelationGraph` dans app.js).
    """
    edges, lieu_labels = _collect_edges(db, type_relation, poids_min)
    node_ids_needed: set = set()
    for edge in edges:
        node_ids_needed.add(edge.source)
        node_ids_needed.add(edge.target)

    nodes = _build_nodes(db, node_ids_needed, lieu_labels)
    return schemas.GraphResponse(nodes=nodes, edges=edges)


@router.get("/chemin", response_model=schemas.CheminResponse)
def get_chemin(
    depart_id: str,
    arrivee_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(auth.get_current_user),
):
    """Recherche de chemin entre deux individus ou entités (cahier des
    charges 3.3 : "recherche de chemins entre deux individus ou entités"),
    entités incluant désormais aussi les véhicules et les lieux.

    Construit le même graphe que `/relations/graphe` (non filtré), puis
    effectue un parcours en largeur (BFS) pour trouver le chemin le plus
    court en nombre de sauts entre `depart_id` et `arrivee_id`. Le nombre de
    sauts, et non la somme des poids, correspond le mieux à la question
    posée par un enquêteur ("par combien d'intermédiaires ces deux entités
    sont-elles reliées ?") ; le poids de chaque lien reste visible dans la
    réponse pour apprécier la force de chaque maillon du chemin trouvé.
    """
    edges, lieu_labels = _collect_edges(db, None, None)
    adjacency: Dict[str, List[schemas.GraphEdge]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append(edge)
        adjacency.setdefault(edge.target, []).append(edge)

    if depart_id == arrivee_id:
        raise HTTPException(status_code=400, detail="depart_id et arrivee_id doivent être différents")
    if depart_id not in adjacency or arrivee_id not in adjacency:
        # Consultation sensible même quand le chemin n'existe pas (6.2).
        audit.log(
            db,
            user=current_user,
            action="consultation",
            ressource_type="chemin_relations",
            ressource_id=f"{depart_id}->{arrivee_id}",
            details="Aucun des deux nœuds n'a de relation connue",
            request=request,
        )
        return schemas.CheminResponse(trouve=False)

    # BFS standard : file d'attente de nœuds, on remonte le chemin via `venant_de`.
    venant_de: Dict[str, tuple] = {}  # node_id -> (node_precedent, edge_utilisee)
    visites = {depart_id}
    file = deque([depart_id])
    trouve = False

    while file:
        courant = file.popleft()
        if courant == arrivee_id:
            trouve = True
            break
        for edge in adjacency.get(courant, []):
            voisin = edge.target if edge.source == courant else edge.source
            if voisin not in visites:
                visites.add(voisin)
                venant_de[voisin] = (courant, edge)
                file.append(voisin)

    audit.log(
        db,
        user=current_user,
        action="consultation",
        ressource_type="chemin_relations",
        ressource_id=f"{depart_id}->{arrivee_id}",
        details=f"Chemin trouvé : {trouve}",
        request=request,
    )

    if not trouve:
        return schemas.CheminResponse(trouve=False)

    # Reconstruction du chemin en remontant depuis arrivee_id.
    chemin_edges: List[schemas.GraphEdge] = []
    chemin_node_ids: List[str] = [arrivee_id]
    courant = arrivee_id
    while courant != depart_id:
        precedent, edge = venant_de[courant]
        chemin_edges.append(edge)
        chemin_node_ids.append(precedent)
        courant = precedent
    chemin_edges.reverse()
    chemin_node_ids.reverse()

    nodes = _build_nodes(db, set(chemin_node_ids), lieu_labels)
    # Conserve l'ordre du chemin plutôt que l'ordre de retour de la requête SQL.
    nodes_by_id = {n.id: n for n in nodes}
    ordered_nodes = [nodes_by_id[nid] for nid in chemin_node_ids if nid in nodes_by_id]

    return schemas.CheminResponse(
        trouve=True,
        nodes=ordered_nodes,
        edges=chemin_edges,
        longueur=len(chemin_edges),
    )
