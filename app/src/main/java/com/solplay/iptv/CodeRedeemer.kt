package com.solplay.iptv

import com.google.firebase.database.FirebaseDatabase
import kotlinx.coroutines.tasks.await

/** Résultat de la vérification d'un code M3U/Xtream auprès de l'administrateur (Firebase). */
sealed class RedeemResult {
    data class Success(val playlist: SavedPlaylist) : RedeemResult()
    data class Failure(val message: String) : RedeemResult()
}

object CodeRedeemer {

    /**
     * Vérifie en ligne si le code existe et est actif (nœud Firebase
     * "playlist_codes/{code}", géré depuis admin_panel.html), et construit
     * la playlist correspondante si oui.
     */
    suspend fun redeem(code: String): RedeemResult {
        val trimmed = code.trim()
        if (trimmed.isEmpty()) return RedeemResult.Failure("Merci de saisir un code.")

        return try {
            val snapshot = FirebaseDatabase.getInstance()
                .getReference("playlist_codes")
                .child(trimmed)
                .get()
                .await()

            if (!snapshot.exists()) {
                return RedeemResult.Failure("Ce code n'existe pas. Vérifiez auprès de votre fournisseur.")
            }

            val active = snapshot.child("active").getValue(Boolean::class.java) ?: false
            if (!active) {
                return RedeemResult.Failure("Ce code a été désactivé. Contactez votre fournisseur.")
            }

            val type = snapshot.child("type").getValue(String::class.java) ?: "m3u"
            val name = snapshot.child("name").getValue(String::class.java)
                ?.takeIf { it.isNotBlank() } ?: "Code $trimmed"

            val playlist = if (type == "xtream") {
                SavedPlaylist(
                    name = name,
                    mode = PlaylistMode.XTREAM,
                    xtreamServer = snapshot.child("xtreamServer").getValue(String::class.java) ?: "",
                    xtreamUsername = snapshot.child("xtreamUsername").getValue(String::class.java) ?: "",
                    xtreamPassword = snapshot.child("xtreamPassword").getValue(String::class.java) ?: "",
                    fromCode = trimmed
                )
            } else {
                SavedPlaylist(
                    name = name,
                    mode = PlaylistMode.M3U,
                    m3uUrl = snapshot.child("m3uUrl").getValue(String::class.java) ?: "",
                    fromCode = trimmed
                )
            }
            RedeemResult.Success(playlist)
        } catch (e: Exception) {
            RedeemResult.Failure("Erreur réseau : ${e.message ?: "impossible de vérifier le code"}.")
        }
    }
}
