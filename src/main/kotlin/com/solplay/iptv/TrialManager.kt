package com.solplay.iptv

import android.content.Context
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.coroutines.resume

/**
 * Gère l'essai gratuit de 24 heures et l'activation de la licence Pro
 * (avec date d'expiration).
 *
 * L'activation Pro fonctionne via Firebase Realtime Database :
 * 1. L'app génère une "clé appareil" unique (voir DeviceKeyManager).
 * 2. Le client envoie cette clé à l'administrateur (email/WhatsApp).
 * 3. L'administrateur active cette clé depuis le panneau admin (admin_panel.html)
 *    en choisissant une durée (test en heures, ou abonnement en mois).
 * 4. L'app vérifie en ligne le statut de cette clé, mémorise la date
 *    d'expiration localement et fonctionne ensuite hors-ligne jusqu'à expiration.
 */
object TrialManager {

    private const val PREFS = "solplay_prefs"
    private const val KEY_FIRST_LAUNCH = "first_launch_time"
    private const val KEY_LICENSED = "is_licensed"
    private const val KEY_LICENSE_EXPIRES_AT = "license_expires_at"
    private const val KEY_LICENSE_PLAN_LABEL = "license_plan_label"
    private const val KEY_SERVER_TIME_OFFSET = "server_time_offset_millis"

    /**
     * Essai gratuit désactivé : l'application nécessite désormais une
     * activation par l'administrateur (clé appareil) dès le premier lancement.
     * On garde TRIAL_HOURS = 0 (plutôt que de supprimer tout le mécanisme)
     * pour ne pas casser les autres écrans qui référencent encore ces
     * fonctions : avec 0h, isTrialActive() est toujours false et
     * canAccessApp() ne dépend donc plus que de la licence.
     */
    private const val TRIAL_HOURS = 0L
    private const val MILLIS_PER_HOUR = 1000L * 60 * 60
    private const val TRIAL_MILLIS = TRIAL_HOURS * MILLIS_PER_HOUR

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /**
     * Heure "de confiance", corrigée de l'éventuel décalage entre l'horloge
     * du boîtier/téléphone et l'heure réelle du serveur Firebase.
     *
     * Pourquoi : de nombreux boîtiers Android TV bas de gamme ont une
     * horloge système mal réglée (pas de synchronisation NTP, date/heure
     * manuelle incorrecte). Comme expiresAt est calculé côté admin avec
     * l'heure réelle, comparer expiresAt à System.currentTimeMillis() sur
     * un appareil dont l'horloge est fausse (ex: en avance d'1h) donne un
     * temps restant complètement faux (ex: "1min restant" au lieu de
     * "59min restant"), et peut même faire passer une licence valide pour
     * expirée. On corrige donc System.currentTimeMillis() avec l'offset
     * mesuré via ".info/serverTimeOffset" (mis à jour à chaque vérification
     * en ligne, voir checkOnlineLicense) plutôt que de faire confiance à
     * l'horloge locale telle quelle.
     */
    private fun trustedNow(context: Context): Long {
        val offset = prefs(context).getLong(KEY_SERVER_TIME_OFFSET, 0L)
        return System.currentTimeMillis() + offset
    }

    /**
     * Décalage (en millisecondes) détecté entre l'heure du serveur Firebase
     * et l'horloge locale de l'appareil, tel que mesuré lors du dernier
     * appel réussi à [checkOnlineLicense]. Positif si l'horloge locale est
     * en retard sur le serveur, négatif si elle est en avance. 0 si aucune
     * mesure n'a encore été faite (ou hors-ligne depuis le premier lancement).
     *
     * Exposé uniquement pour un affichage de debug (voir [getDebugOffsetInfo]) :
     * ça permet de vérifier sur le terrain qu'une horloge mal réglée est bien
     * détectée et corrigée, sans avoir à instrumenter le code autrement.
     */
    fun getServerTimeOffsetMillis(context: Context): Long =
        prefs(context).getLong(KEY_SERVER_TIME_OFFSET, 0L)

    /**
     * Petite chaîne lisible pour un écran/log de debug, résumant l'offset
     * détecté et son effet sur l'heure "de confiance" utilisée par le
     * TrialManager. Exemple : "Offset serveur : +54 min (horloge locale en retard)".
     */
    fun getDebugOffsetInfo(context: Context): String {
        val offset = getServerTimeOffsetMillis(context)
        // En dessous d'1 minute, l'écart est négligeable (latence réseau, etc.) :
        // on l'affiche comme "horloge OK" plutôt que d'annoncer un faux
        // retard/avance de "+0min" qui serait trompeur pour la lecture debug.
        val oneMinute = 60_000L
        if (kotlin.math.abs(offset) < oneMinute) {
            return "Offset serveur : horloge OK (écart < 1min)"
        }
        val sign = if (offset > 0) "+" else "-"
        val direction = if (offset > 0) "horloge locale en retard" else "horloge locale en avance"
        return "Offset serveur : $sign${formatDuration(kotlin.math.abs(offset))} ($direction)"
    }

    /** Doit être appelé une fois au démarrage de l'app (ex: SplashActivity). */
    fun ensureFirstLaunchRecorded(context: Context) {
        val p = prefs(context)
        if (p.getLong(KEY_FIRST_LAUNCH, 0L) == 0L) {
            p.edit().putLong(KEY_FIRST_LAUNCH, trustedNow(context)).apply()
        }
    }

    // ---------------------------------------------------------------------
    // Essai gratuit (24h)
    // ---------------------------------------------------------------------

    /** Millisecondes restantes dans l'essai gratuit (0 si terminé). */
    fun getRemainingTrialMillis(context: Context): Long {
        val first = prefs(context).getLong(KEY_FIRST_LAUNCH, trustedNow(context))
        val elapsed = trustedNow(context) - first
        return (TRIAL_MILLIS - elapsed).coerceAtLeast(0)
    }

    fun isTrialActive(context: Context): Boolean = getRemainingTrialMillis(context) > 0

    // ---------------------------------------------------------------------
    // Licence payante (avec expiration)
    // ---------------------------------------------------------------------

    /** true si une licence est active ET pas encore expirée. */
    fun isLicensed(context: Context): Boolean {
        val p = prefs(context)
        if (!p.getBoolean(KEY_LICENSED, false)) return false
        val expiresAt = p.getLong(KEY_LICENSE_EXPIRES_AT, 0L)
        // expiresAt == 0L est traité comme "sans expiration" (compatibilité/illimité)
        if (expiresAt == 0L) return true
        return trustedNow(context) < expiresAt
    }

    fun getLicenseExpiresAt(context: Context): Long = prefs(context).getLong(KEY_LICENSE_EXPIRES_AT, 0L)

    fun getLicensePlanLabel(context: Context): String? = prefs(context).getString(KEY_LICENSE_PLAN_LABEL, null)

    /** Millisecondes restantes sur la licence payante (0 si expirée ou sans licence). */
    fun getRemainingLicenseMillis(context: Context): Long {
        // On vérifie d'abord isLicensed() (qui contrôle le flag KEY_LICENSED
        // ET l'expiration) : sans ce contrôle, un appareil jamais licencié
        // (expiresAt == 0L par défaut) se voyait renvoyer Long.MAX_VALUE
        // ("illimité") au lieu de 0 — sans impact concret aujourd'hui, car
        // aucun appel actuel n'atteint ce chemin sans licence active, mais
        // un bug latent si ce champ est réutilisé ailleurs plus tard.
        if (!isLicensed(context)) return 0L
        val expiresAt = getLicenseExpiresAt(context)
        if (expiresAt == 0L) return Long.MAX_VALUE // licence sans expiration
        return (expiresAt - trustedNow(context)).coerceAtLeast(0)
    }

    /** L'utilisateur peut utiliser l'app s'il est licencié (et pas expiré) OU encore dans l'essai. */
    fun canAccessApp(context: Context): Boolean = isLicensed(context) || isTrialActive(context)

    /**
     * Vérifie en ligne (Firebase) si la clé de cet appareil a été activée par
     * l'administrateur, et récupère sa date d'expiration éventuelle.
     * Nécessite une connexion internet.
     * Retourne true si activée ET non expirée (et mémorise le statut
     * localement pour un accès hors-ligne par la suite), false sinon.
     */
    suspend fun checkOnlineLicense(context: Context): Boolean {
        val deviceKey = DeviceKeyManager.getDeviceKey(context)
        return try {
            // 1) Mesure l'écart entre l'horloge de l'appareil et l'heure
            //    réelle du serveur Firebase, et le mémorise pour que toutes
            //    les comparaisons (isLicensed, getRemainingLicenseMillis...)
            //    restent fiables même si l'horloge locale est mal réglée.
            //    ".info/serverTimeOffset" renvoie directement, en millis,
            //    la différence (heure serveur - heure locale).
            refreshServerTimeOffset(context)

            val ref = FirebaseDatabase.getInstance()
                .getReference("licenses")
                .child(deviceKey)
            val snapshot = ref.get().await()
            val active = snapshot.child("active").getValue(Boolean::class.java) ?: false
            val expiresAt = snapshot.child("expiresAt").getValue(Long::class.java) ?: 0L
            val planLabel = snapshot.child("planLabel").getValue(String::class.java)

            val stillValid = active && (expiresAt == 0L || trustedNow(context) < expiresAt)

            val p = prefs(context)
            p.edit()
                .putBoolean(KEY_LICENSED, active)
                .putLong(KEY_LICENSE_EXPIRES_AT, expiresAt)
                .putString(KEY_LICENSE_PLAN_LABEL, planLabel)
                .apply()

            stillValid
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Mesure l'écart entre l'horloge locale et l'heure réelle du serveur
     * Firebase, et met à jour [KEY_SERVER_TIME_OFFSET] en conséquence.
     *
     * Pourquoi un listener plutôt qu'un simple .get() :
     * ".info/serverTimeOffset" n'est fiable qu'une fois la connexion
     * websocket Firebase pleinement établie et synchronisée. Un .get()
     * ponctuel peut renvoyer 0 (sans lever d'erreur) si on l'interroge
     * juste après le lancement de l'app, avant la fin de la synchro — ce
     * qui écraserait un offset correct par un faux "0" et ferait passer
     * une licence valide pour expirée sur un appareil dont l'horloge est
     * mal réglée. Un ValueEventListener, lui, ne se déclenche qu'une fois
     * la valeur réellement poussée par le serveur.
     *
     * Sécurité : cette fonction ne fait que fiabiliser la MESURE de
     * l'écart d'horloge. Elle ne change rien à la logique de confiance :
     * la comparaison de la licence reste toujours basée sur l'heure
     * serveur corrigée (trustedNow), jamais sur l'horloge locale brute.
     * En cas d'échec/timeout, on conserve simplement le dernier offset
     * connu (ou 0 par défaut au tout premier lancement) au lieu d'en
     * enregistrer un potentiellement faux.
     */
    private suspend fun refreshServerTimeOffset(context: Context) {
        val offsetMillis = withTimeoutOrNull(8_000L) {
            suspendCancellableCoroutine<Long?> { cont ->
                val ref = FirebaseDatabase.getInstance().getReference(".info/serverTimeOffset")
                val listener = object : ValueEventListener {
                    override fun onDataChange(snapshot: DataSnapshot) {
                        val value = snapshot.getValue(Long::class.java)
                            ?: snapshot.getValue(Double::class.java)?.toLong()
                        ref.removeEventListener(this)
                        if (cont.isActive) cont.resume(value)
                    }

                    override fun onCancelled(error: DatabaseError) {
                        ref.removeEventListener(this)
                        if (cont.isActive) cont.resume(null)
                    }
                }
                ref.addValueEventListener(listener)
                cont.invokeOnCancellation { ref.removeEventListener(listener) }
            }
        }
        // On n'écrase l'offset mémorisé que si on a bien reçu une valeur
        // confirmée par le serveur. Sinon (timeout, erreur, hors-ligne),
        // on garde volontairement le dernier offset connu.
        if (offsetMillis != null) {
            prefs(context).edit().putLong(KEY_SERVER_TIME_OFFSET, offsetMillis).apply()
        }
    }

    // ---------------------------------------------------------------------
    // Formatage de durée / dates pour l'affichage
    // ---------------------------------------------------------------------

    /** Formate une durée en millisecondes en "Xj Xh Xmin" (ou "Xh Xmin" / "Xmin"). */
    fun formatDuration(millis: Long): String {
        if (millis <= 0) return "0 min"
        if (millis == Long.MAX_VALUE) return "illimité"
        val totalMinutes = millis / 60000
        val days = totalMinutes / (60 * 24)
        val hours = (totalMinutes % (60 * 24)) / 60
        val minutes = totalMinutes % 60
        return when {
            days > 0 -> "${days}j ${hours}h ${minutes}min"
            hours > 0 -> "${hours}h ${minutes}min"
            else -> "${minutes}min"
        }
    }

    fun formatDate(millis: Long): String {
        if (millis == 0L) return "-"
        val sdf = SimpleDateFormat("dd/MM/yyyy 'à' HH:mm", Locale.FRENCH)
        return sdf.format(Date(millis))
    }
}
