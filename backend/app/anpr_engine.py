"""Détection + lecture de plaques sur image/vidéo — Module 4 (cahier des
charges 3.4, "détection/lecture réelle de plaque sur image ou vidéo").

Pipeline 100% local (aucun appel externe) :
1. localisation de la région de plaque, par cascade de Haar
   (`haarcascade_russian_plate_number.xml`, fournie avec OpenCV — fonctionne
   raisonnablement sur des plaques rectangulaires génériques) puis, si rien
   n'est trouvé, par une méthode de repli à base de contours (Canny + filtre
   sur le ratio largeur/hauteur typique d'une plaque) ;
2. pour chaque région candidate : upscale, filtre bilatéral, seuillage
   d'Otsu, puis OCR (tesseract, mode `--psm 7` = ligne de texte unique) ;
3. normalisation du texte lu (majuscules, caractères alphanumériques
   uniquement) puis tentative de correspondance avec les deux formats de
   plaques ivoiriennes connus (voir `canonicaliser_plaque`) — un candidat
   dont le format est reconnu est toujours préféré à un candidat non
   reconnu, même à confiance OCR brute plus faible, car la structure
   attendue est un indice plus fiable que le score pixel-par-pixel.

Formats de plaques reconnus (Côte d'Ivoire) :
- ancien format : 4 chiffres + 2 lettres + 2 chiffres, ex. "1234 GA 01" ;
- nouveau format : 2 lettres + 3 chiffres + 2 lettres, ex. "AB-123-CD".
Si le texte lu ne correspond à aucun des deux gabarits (même après
correction des confusions OCR classiques 0/O, 1/I, 5/S, 8/B, 2/Z, 6/G), le
texte normalisé brut est renvoyé tel quel — utile pour les plaques
étrangères/anciennes non standard, mais à vérifier plus attentivement par
l'agent.

Limites connues (à documenter côté utilisateur) : performances dépendantes
de l'angle/éclairage/résolution de la source, cascade de détection
générique (pas de modèle spécifique aux plaques CEDEAO). Ceci reste une
aide au rapprochement, pas une lecture certifiée : la lecture proposée doit
être validée par un agent avant tout acte de procédure.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np
import pytesseract

_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
_cascade = cv2.CascadeClassifier(_CASCADE_PATH)

# Note : ne PAS utiliser tessedit_char_whitelist ici — sur ce build de
# tesseract, la liste blanche ramène `conf` à 0 pour tous les mots, ce qui
# rend le score de confiance inutilisable. Le nettoyage (garder seulement
# A-Z0-9) est fait a posteriori par `_normaliser_texte`.
_TESS_CONFIG = "--psm 7"


@dataclass
class CandidatPlaque:
    texte: str
    confiance: float
    bbox: tuple  # x, y, w, h
    format_reconnu: bool = False


def _normaliser_texte(texte: str) -> str:
    texte = texte.upper()
    texte = re.sub(r"[^A-Z0-9]", "", texte)
    return texte


# Gabarits des deux formats de plaques ivoiriennes ("D" = chiffre, "L" =
# lettre). L'ancien format n'a pas d'espaces dans le texte OCR normalisé
# (ils sont retirés par `_normaliser_texte`), d'où les gabarits "compacts".
_GABARIT_ANCIEN = "DDDDLLDD"  # "1234 GA 01" -> 1234GA01
_GABARIT_NOUVEAU = "LLDDDLL"  # "AB-123-CD" -> AB123CD

# Confusions OCR classiques, utilisées uniquement pour forcer un caractère
# vers la classe (chiffre/lettre) attendue à sa position dans le gabarit —
# jamais pour deviner un caractère manquant.
_VERS_LETTRE = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
_VERS_CHIFFRE = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2", "G": "6", "D": "0"}


def _forcer_classe(caractere: str, attendu: str) -> str:
    if attendu == "D":
        if caractere.isdigit():
            return caractere
        return _VERS_CHIFFRE.get(caractere, caractere)
    if caractere.isalpha():
        return caractere
    return _VERS_LETTRE.get(caractere, caractere)


def _essayer_gabarit(texte: str, gabarit: str) -> Optional[str]:
    if len(texte) != len(gabarit):
        return None
    corrige = "".join(_forcer_classe(c, g) for c, g in zip(texte, gabarit))
    for c, g in zip(corrige, gabarit):
        if g == "D" and not c.isdigit():
            return None
        if g == "L" and not c.isalpha():
            return None
    return corrige


def canonicaliser_plaque(texte_normalise: str) -> tuple:
    """Tente de faire correspondre un texte OCR normalisé (A-Z0-9
    uniquement) à l'un des deux formats de plaques ivoiriennes connus, et
    le reformate avec la ponctuation standard. Corrige au passage les
    confusions OCR classiques sur les positions attendues (ex. un 'O' lu à
    la place d'un chiffre, un '0' lu à la place d'une lettre).

    Retourne (texte_final, format_reconnu). Si aucun gabarit ne
    correspond, renvoie le texte normalisé tel quel avec format_reconnu à
    False."""
    c = _essayer_gabarit(texte_normalise, _GABARIT_ANCIEN)
    if c:
        return f"{c[0:4]} {c[4:6]} {c[6:8]}", True
    c = _essayer_gabarit(texte_normalise, _GABARIT_NOUVEAU)
    if c:
        return f"{c[0:2]}-{c[2:5]}-{c[5:7]}", True
    return texte_normalise, False


def _ocr_region(gray_region: np.ndarray) -> Optional[CandidatPlaque]:
    # Upscale small regions to give tesseract more pixels to work with
    h, w = gray_region.shape[:2]
    if h == 0 or w == 0:
        return None
    scale = max(1, 300 // max(h, 1))
    resized = cv2.resize(gray_region, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    resized = cv2.bilateralFilter(resized, 11, 17, 17)
    _, thresh = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    data = pytesseract.image_to_data(
        thresh, config=_TESS_CONFIG, output_type=pytesseract.Output.DICT
    )
    mots = []
    confiances = []
    for i, txt in enumerate(data["text"]):
        txt = txt.strip()
        conf = float(data["conf"][i])
        # tesseract renvoie -1 pour les lignes qui ne sont pas des mots
        # (blocs/paragraphes) ; 0 est une confiance valide (basse) à garder.
        if txt and conf >= 0:
            mots.append(txt)
            confiances.append(conf)

    texte = _normaliser_texte("".join(mots))
    if not texte:
        return None
    texte_final, format_reconnu = canonicaliser_plaque(texte)
    confiance_moy = sum(confiances) / len(confiances) if confiances else 0.0
    return CandidatPlaque(
        texte=texte_final,
        confiance=round(confiance_moy / 100.0, 3),
        bbox=(0, 0, w, h),
        format_reconnu=format_reconnu,
    )


def _candidats_cascade(gray: np.ndarray) -> List[tuple]:
    plaques = _cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=4, minSize=(60, 20))
    return [tuple(p) for p in plaques]


def _candidats_contours(gray: np.ndarray) -> List[tuple]:
    """Repli si le cascade ne trouve rien : détection par contours (bords +
    filtrage sur le ratio largeur/hauteur typique d'une plaque, ~2:1 à 5:1)."""
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(filtered, 30, 200)
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

    candidats = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if h == 0:
            continue
        ratio = w / h
        if 2.0 <= ratio <= 6.0 and w > 60 and h > 15:
            candidats.append((x, y, w, h))
    return candidats


def _detecter_dans_gray(gray: np.ndarray, max_candidats: int = 5) -> List[CandidatPlaque]:
    """Cœur du pipeline détection+OCR, opérant directement sur une image en
    niveaux de gris déjà décodée — partagé entre `detecter_plaques` (image
    fixe) et `detecter_plaques_video` (une frame à la fois), pour éviter de
    ré-encoder/décoder inutilement chaque frame d'une vidéo."""
    regions = _candidats_cascade(gray)
    if not regions:
        regions = _candidats_contours(gray)

    resultats = []
    vus = set()
    for (x, y, w, h) in regions:
        if len(resultats) >= max_candidats:
            break
        region = gray[y:y + h, x:x + w]
        candidat = _ocr_region(region)
        if not candidat or len(candidat.texte) < 4:
            continue
        # Déduplication : les contours renvoient parfois deux fois quasiment
        # le même rectangle, et la même plaque peut être lue par le cascade
        # et par les contours à la fois.
        cle = candidat.texte
        if cle in vus:
            continue
        vus.add(cle)
        resultats.append(
            CandidatPlaque(
                texte=candidat.texte,
                confiance=candidat.confiance,
                bbox=(x, y, w, h),
                format_reconnu=candidat.format_reconnu,
            )
        )

    # Un format reconnu (structure de plaque valide) est un indice plus
    # fiable que le score OCR brut : il passe toujours devant, la confiance
    # ne départageant qu'à égalité de reconnaissance de format.
    resultats.sort(key=lambda c: (c.format_reconnu, c.confiance), reverse=True)
    return resultats


def detecter_plaques(image_bytes: bytes, max_candidats: int = 5) -> List[CandidatPlaque]:
    """Détecte les régions plausibles de plaque dans une image et effectue
    l'OCR sur chacune. Retourne les candidats triés (format reconnu puis
    confiance, décroissant)."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Image illisible ou format non supporté")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return _detecter_dans_gray(gray, max_candidats=max_candidats)


@dataclass
class LecturePlaqueVideo:
    """Meilleure lecture d'une plaque donnée sur l'ensemble des frames
    échantillonnées d'une vidéo/flux."""

    texte: str
    confiance: float
    format_reconnu: bool
    frame_index: int
    timestamp_s: float
    frame_jpeg: bytes  # frame où cette lecture a été obtenue, encodée JPEG


@dataclass
class ResultatDetectionVideo:
    lectures: List[LecturePlaqueVideo]
    frames_analysees: int
    duree_video_s: Optional[float]


def detecter_plaques_video(
    source,
    intervalle_secondes: float = 1.0,
    max_frames_analysees: int = 300,
    max_plaques: int = 20,
) -> ResultatDetectionVideo:
    """Détecte des plaques sur une vidéo ou un flux caméra (cahier 3.4,
    "lecture réelle de plaque sur image OU VIDÉO").

    `source` est soit un chemin de fichier vidéo local, soit une URL de
    flux (ex. RTSP `rtsp://...`, HTTP MJPEG) — `cv2.VideoCapture` accepte
    les deux de façon transparente, donc le même code gère l'upload de
    vidéo et la connexion à une caméra IP.

    La vidéo n'est pas analysée image par image en continu : on échantillonne
    une frame toutes les `intervalle_secondes` (les plaques ne changent pas
    d'une frame à l'autre à 25-30 fps, inutile de tout traiter) et on ne
    garde, par plaque distincte lue, que la meilleure occurrence (format
    reconnu, puis confiance la plus haute) sur l'ensemble des frames
    échantillonnées — c'est cette occurrence qui est renvoyée avec
    l'horodatage et la frame source correspondants.

    Lève `ValueError` si le flux/fichier ne peut pas être ouvert (fichier
    corrompu, codec non supporté, caméra injoignable, URL invalide...).
    """
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise ValueError(
            "Flux vidéo illisible : fichier corrompu/format non supporté, ou flux caméra injoignable"
        )

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    if fps <= 0:
        fps = 25.0
    pas_frames = max(1, round(fps * intervalle_secondes))

    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duree_video_s = round(total_frames / fps, 2) if total_frames and total_frames > 0 else None

    meilleurs = {}
    index = 0
    analysees = 0
    try:
        while analysees < max_frames_analysees:
            ret, frame = cap.read()
            if not ret:
                break
            if index % pas_frames == 0:
                analysees += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                for c in _detecter_dans_gray(gray):
                    existant = meilleurs.get(c.texte)
                    if existant is None or (c.format_reconnu, c.confiance) > (
                        existant.format_reconnu,
                        existant.confiance,
                    ):
                        ok, buf = cv2.imencode(".jpg", frame)
                        meilleurs[c.texte] = LecturePlaqueVideo(
                            texte=c.texte,
                            confiance=c.confiance,
                            format_reconnu=c.format_reconnu,
                            frame_index=index,
                            timestamp_s=round(index / fps, 2),
                            frame_jpeg=buf.tobytes() if ok else b"",
                        )
            index += 1
    finally:
        cap.release()

    lectures = sorted(meilleurs.values(), key=lambda r: (r.format_reconnu, r.confiance), reverse=True)
    return ResultatDetectionVideo(
        lectures=lectures[:max_plaques],
        frames_analysees=analysees,
        duree_video_s=duree_video_s,
    )
