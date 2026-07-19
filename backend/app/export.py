"""Export CSV / PDF réutilisable par les différents modules.

- CSV : simple, standard, consommable par n'importe quel tableur ou système
  tiers (cahier des charges, exigence non fonctionnelle "Interopérabilité").
- PDF : mise en page présentable, adaptée à une pièce versée à une procédure
  judiciaire (Module 2) ou à un rapport imprimable (Module 1).
"""

import csv
import io
from datetime import datetime
from typing import Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Mêmes couleurs que la carte Leaflet du frontend (GRAVITE_COLORS dans
# app.js), pour que le rapport imprimé et l'écran restent cohérents.
GRAVITE_COLORS_PDF = {
    "faible": colors.HexColor("#5b8c5a"),
    "moyenne": colors.HexColor("#c2703d"),
    "eleve": colors.HexColor("#bd4d3f"),
    "élevé": colors.HexColor("#bd4d3f"),
    "critique": colors.HexColor("#8a1f1f"),
}
_DEFAULT_POINT_COLOR = colors.HexColor("#5578c9")


def rows_to_csv(headers: Sequence[str], rows: Iterable[Sequence]) -> io.BytesIO:
    """Construit un CSV en mémoire (UTF-8 avec BOM pour un Excel FR sans souci d'accents)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    encoded = io.BytesIO()
    encoded.write(b"\xef\xbb\xbf")  # BOM UTF-8
    encoded.write(buffer.getvalue().encode("utf-8"))
    encoded.seek(0)
    return encoded


def build_pdf_report(
    *,
    titre: str,
    sous_titre: str = "",
    headers: Sequence[str],
    rows: Iterable[Sequence],
    genere_par: str = "",
    notes: str = "",
) -> io.BytesIO:
    """Génère un PDF tabulaire simple (rapport / pièce de procédure).

    Volontairement générique : utilisé aussi bien pour un export d'incidents
    (Module 1) que pour l'historique d'une chaîne de custody (Module 2).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(titre, styles["Title"]))
    if sous_titre:
        elements.append(Paragraph(sous_titre, styles["Normal"]))
    meta = f"Généré le {datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
    if genere_par:
        meta += f" par {genere_par}"
    elements.append(Paragraph(meta, styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    table_data = [list(headers)] + [["" if v is None else str(v) for v in row] for row in rows]
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B1D21")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)

    if notes:
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph(notes, styles["Italic"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


class MapPlot(Flowable):
    """Rendu schématique d'une carte (projection équirectangulaire simple,
    suffisante à l'échelle d'un briefing d'unité — pas de fond de plan
    OpenStreetMap embarqué dans un PDF généré côté serveur sans navigateur).

    Dessine les incidents en points colorés par gravité et les hotspots en
    cercles semi-transparents, avec une grille de repère et un cadre. Comble
    l'écart signalé sur `/incidents/export/pdf`, qui ne produisait qu'un
    tableau et pas une carte (cahier des charges 3.1 : "Export de rapports
    cartographiques pour les briefings d'unité").
    """

    def __init__(self, incidents, hotspots, width=17 * cm, height=13 * cm):
        super().__init__()
        self.incidents = incidents
        self.hotspots = hotspots or []
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def _bounds(self):
        lats = [i.latitude for i in self.incidents if i.latitude is not None]
        lons = [i.longitude for i in self.incidents if i.longitude is not None]
        for h in self.hotspots:
            lats.append(h.latitude)
            lons.append(h.longitude)
        if not lats:
            return (48.80, 48.92, 2.25, 2.45)  # repli : région parisienne
        pad_lat = max((max(lats) - min(lats)) * 0.12, 0.01)
        pad_lon = max((max(lons) - min(lons)) * 0.12, 0.01)
        return (min(lats) - pad_lat, max(lats) + pad_lat, min(lons) - pad_lon, max(lons) + pad_lon)

    def draw(self):
        c = self.canv
        lat_min, lat_max, lon_min, lon_max = self._bounds()
        lat_span = max(lat_max - lat_min, 1e-6)
        lon_span = max(lon_max - lon_min, 1e-6)

        def project(lat, lon):
            x = (lon - lon_min) / lon_span * self.width
            y = (lat - lat_min) / lat_span * self.height
            return x, y

        # Cadre + grille de repère (pas de tuiles de fond, cf. docstring).
        c.setStrokeColor(colors.HexColor("#c9c9c9"))
        c.setFillColor(colors.HexColor("#fbfbfb"))
        c.rect(0, 0, self.width, self.height, stroke=1, fill=1)
        for i in range(1, 4):
            c.line(0, self.height * i / 4, self.width, self.height * i / 4)
            c.line(self.width * i / 4, 0, self.width * i / 4, self.height)

        # Hotspots : cercles semi-transparents dessinés sous les points.
        c.setFillColor(colors.HexColor("#c2703d"))
        for h in self.hotspots:
            x, y = project(h.latitude, h.longitude)
            r = 4 + min(h.nombre_incidents, 20)
            c.saveState()
            c.setFillAlpha(0.18)
            c.setStrokeColor(colors.HexColor("#c2703d"))
            c.circle(x, y, r, stroke=1, fill=1)
            c.restoreState()

        # Incidents : points colorés par gravité.
        for inc in self.incidents:
            if inc.latitude is None or inc.longitude is None:
                continue
            x, y = project(inc.latitude, inc.longitude)
            c.setFillColor(GRAVITE_COLORS_PDF.get(inc.gravite, _DEFAULT_POINT_COLOR))
            c.circle(x, y, 2.4, stroke=0, fill=1)

        c.setStrokeColor(colors.HexColor("#888888"))
        c.rect(0, 0, self.width, self.height, stroke=1, fill=0)


def build_map_pdf_report(
    *,
    titre: str,
    sous_titre: str,
    incidents,
    hotspots,
    genere_par: str = "",
) -> io.BytesIO:
    """Rapport cartographique imprimable (Module 1) : carte des incidents +
    hotspots, suivie du détail tabulaire — distinct de `build_pdf_report`,
    qui reste utilisé pour les exports purement tabulaires (Module 2 etc.).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(titre, styles["Title"])]
    if sous_titre:
        elements.append(Paragraph(sous_titre, styles["Normal"]))
    meta = f"Généré le {datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
    if genere_par:
        meta += f" par {genere_par}"
    elements.append(Paragraph(meta, styles["Normal"]))
    elements.append(Spacer(1, 0.4 * cm))

    elements.append(MapPlot(incidents, hotspots))
    legende = (
        "Points colorés par gravité (vert = faible, orange = moyenne/élevée, rouge foncé = critique) "
        f"— {len(hotspots)} hotspot(s) détecté(s), cercles orange proportionnels au nombre d'incidents."
    )
    elements.append(Spacer(1, 0.25 * cm))
    elements.append(Paragraph(legende, styles["Italic"]))
    elements.append(Spacer(1, 0.6 * cm))

    headers = ["Type", "Date/heure", "Statut", "Gravité", "Adresse", "Unité"]
    rows = [
        [i.type_infraction, i.date_heure.strftime("%d/%m/%Y %H:%M") if i.date_heure else "", i.statut,
         i.gravite, i.adresse or "", i.unite_en_charge or ""]
        for i in incidents
    ]
    table_data = [headers] + [["" if v is None else str(v) for v in row] for row in rows]
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B1D21")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
