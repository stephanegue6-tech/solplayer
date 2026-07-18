package com.solplay.iptv

/**
 * Représente un "bouquet" (= catégorie / group-title) avec le nombre de chaînes qu'il contient.
 * Utilisé par l'écran maître-détail : colonne de gauche = liste des bouquets,
 * colonne de droite = chaînes du bouquet sélectionné.
 */
data class Bouquet(
    val name: String,
    val channelCount: Int
)
