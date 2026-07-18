package com.solplay.iptv

import android.content.Context
import com.google.firebase.database.FirebaseDatabase
import java.util.UUID

/**
 * Synchronise les playlists que l'administrateur a assignées DIRECTEMENT à la
 * clé appareil de cet utilisateur, depuis le panneau admin (nœud Firebase
 * "device_playlists/{deviceKey}/{id}").
 *
 * Contrairement à CodeRedeemer (où le client doit lui-même saisir un code),
 * ce mécanisme ne demande AUCUNE action au client : dès que l'admin assigne
 * une playlist à sa clé appareil, elle apparaît automatiquement dans "Mes
 * playlists" la prochaine fois que l'app se connecte à internet.
 */
object DevicePlaylistSync {

    suspend fun sync(context: Context) {
        val deviceKey = DeviceKeyManager.getDeviceKey(context)
        try {
            val snapshot = FirebaseDatabase.getInstance()
                .getReference("device_playlists")
                .child(deviceKey)
                .get()
                .await()

            val existing = PlaylistStore.getAll(context)

            // Tags ("device:remoteId") des assignations encore actives et non
            // expirées après ce passage - sert à nettoyer en fin de fonction
            // toute playlist locale "device:*" qui ne s'y retrouve plus, y
            // compris quand l'admin a carrément SUPPRIMÉ l'assignation côté
            // Firebase (elle n'apparaît alors plus du tout dans
            // snapshot.children, donc jamais vue par la boucle ci-dessous -
            // sans ce nettoyage final, elle restait affichée indéfiniment
            // côté app tant que l'utilisateur ne la supprimait pas lui-même).
            val stillValidTags = mutableSetOf<String>()

            if (snapshot.exists()) {
                for (child in snapshot.children) {
                    val remoteId = child.key ?: continue
                    val tag = "device:$remoteId"
                    val active = child.child("active").getValue(Boolean::class.java) ?: true
                    val expiresAt = child.child("expiresAt").getValue(Long::class.java) ?: 0L
                    // Même correction d'horloge que TrialManager (offset serveur Firebase),
                    // pour éviter qu'un simple changement de date locale sur l'appareil
                    // ne prolonge artificiellement une assignation expirée.
                    val trustedNow = System.currentTimeMillis() + TrialManager.getServerTimeOffsetMillis(context)
                    val expired = expiresAt > 0L && trustedNow >= expiresAt
                    val alreadySaved = existing.firstOrNull { it.fromCode == tag }

                    if (!active || expired) {
                        // L'admin a désactivé cette assignation, ou sa durée est
                        // écoulée : on enlève la copie locale.
                        alreadySaved?.let { PlaylistStore.delete(context, it.id) }
                        continue
                    }

                    stillValidTags += tag

                    val type = child.child("type").getValue(String::class.java) ?: "m3u"
                    val name = child.child("name").getValue(String::class.java)
                        ?.takeIf { it.isNotBlank() } ?: "Playlist"

                    val playlist = if (type == "xtream") {
                        SavedPlaylist(
                            id = alreadySaved?.id ?: UUID.randomUUID().toString(),
                            name = name,
                            mode = PlaylistMode.XTREAM,
                            xtreamServer = child.child("xtreamServer").getValue(String::class.java) ?: "",
                            xtreamUsername = child.child("xtreamUsername").getValue(String::class.java) ?: "",
                            xtreamPassword = child.child("xtreamPassword").getValue(String::class.java) ?: "",
                            fromCode = tag
                        )
                    } else {
                        SavedPlaylist(
                            id = alreadySaved?.id ?: UUID.randomUUID().toString(),
                            name = name,
                            mode = PlaylistMode.M3U,
                            m3uUrl = child.child("m3uUrl").getValue(String::class.java) ?: "",
                            fromCode = tag
                        )
                    }
                    PlaylistStore.save(context, playlist)
                }
            }

            // Nettoyage final : toute playlist locale marquée "device:*" dont le
            // tag n'est plus dans stillValidTags a été retirée/supprimée côté
            // admin (partiellement ou entièrement) - on la retire ici, qu'elle
            // ait été vue désactivée dans la boucle ci-dessus OU carrément
            // absente de snapshot.children (assignation supprimée) OU que
            // snapshot n'existe plus du tout (toutes les assignations supprimées).
            existing
                .filter { it.fromCode?.startsWith("device:") == true && it.fromCode !in stillValidTags }
                .forEach { PlaylistStore.delete(context, it.id) }
        } catch (e: Exception) {
            // Silencieux : pas grave si hors-ligne, on retentera à la prochaine ouverture de l'écran.
        }
    }

    /**
     * Vérifie qu'une assignation "device:{remoteId}" est TOUJOURS active côté
     * Firebase, sans réécrire tout le stockage local (contrairement à [sync]).
     * Utilisé pendant une session déjà ouverte (écran Chaînes, lecteur en
     * cours) pour couper l'accès dès que l'admin supprime/désactive
     * l'assignation, au lieu d'attendre le prochain lancement de l'app ou le
     * prochain passage sur l'écran "Mes playlists" (seuls endroits où [sync]
     * est actuellement appelé).
     *
     * Renvoie true si la playlist n'est pas de type "device:*" (rien à
     * vérifier), ou en cas d'erreur réseau (on ne coupe jamais l'accès sur un
     * simple problème de connexion - seulement sur une suppression confirmée).
     */
    /**
     * Vérifie qu'une assignation ("device:{remoteId}") OU un code saisi par
     * le client (playlist_codes/{code}) est TOUJOURS actif côté Firebase,
     * sans réécrire tout le stockage local (contrairement à [sync]).
     * Utilisé pendant une session déjà ouverte pour couper l'accès dès que
     * l'admin désactive/supprime l'assignation OU le code - avant, un code
     * n'était vérifié qu'au moment de sa saisie initiale et jamais revérifié
     * ensuite, donc une désactivation de code n'avait aucun effet tant que
     * l'utilisateur ne supprimait pas lui-même la playlist.
     *
     * Renvoie true si [tag] est vide (rien à vérifier), ou en cas d'erreur
     * réseau (on ne coupe jamais l'accès sur un simple problème de connexion
     * - seulement sur une désactivation/suppression confirmée).
     */
    suspend fun checkStillAssigned(context: Context, tag: String?): Boolean {
        if (tag.isNullOrBlank()) return true

        return try {
            if (tag.startsWith("device:")) {
                val remoteId = tag.removePrefix("device:")
                val deviceKey = DeviceKeyManager.getDeviceKey(context)
                val snapshot = FirebaseDatabase.getInstance()
                    .getReference("device_playlists")
                    .child(deviceKey)
                    .child(remoteId)
                    .get()
                    .await()

                if (!snapshot.exists()) return false // supprimée côté admin

                val active = snapshot.child("active").getValue(Boolean::class.java) ?: true
                val expiresAt = snapshot.child("expiresAt").getValue(Long::class.java) ?: 0L
                val trustedNow = System.currentTimeMillis() + TrialManager.getServerTimeOffsetMillis(context)
                val expired = expiresAt > 0L && trustedNow >= expiresAt

                active && !expired
            } else {
                // Playlist obtenue via un code saisi par le client (CodeRedeemer) :
                // on revérifie le même nœud "playlist_codes/{code}" que celui
                // consulté lors de la saisie initiale du code.
                val snapshot = FirebaseDatabase.getInstance()
                    .getReference("playlist_codes")
                    .child(tag)
                    .get()
                    .await()

                if (!snapshot.exists()) return false // code supprimé côté admin

                snapshot.child("active").getValue(Boolean::class.java) ?: false
            }
        } catch (e: Exception) {
            true // hors-ligne/erreur réseau : on ne coupe pas l'accès à tort
        }
    }
}
