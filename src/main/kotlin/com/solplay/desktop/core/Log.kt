package android.util

import java.util.Base64 as JavaBase64

/**
 * Remplace android.util.Base64 sur desktop, en s'appuyant sur java.util.Base64
 * (disponible nativement depuis Java 8). Utilisé par XtreamApiClient pour
 * décoder certains champs encodés en base64 renvoyés par l'API Xtream.
 */
object Base64 {
    const val DEFAULT = 0

    fun decode(input: String, flags: Int): ByteArray =
        JavaBase64.getMimeDecoder().decode(input)
}

/**
 * Remplace android.util.Log sur desktop : même signature (d/e/w/i), pour que
 * les fichiers portés depuis l'app Android (XtreamApiClient, TmdbClient,
 * UpdateChecker...) n'aient besoin d'AUCUNE modification sur leurs lignes de
 * log - seul le "import android.util.Log" continue de fonctionner tel quel
 * grâce à ce faux paquet du même nom.
 */
object Log {
    fun d(tag: String, msg: String): Int { println("[D/$tag] $msg"); return 0 }
    fun i(tag: String, msg: String): Int { println("[I/$tag] $msg"); return 0 }
    fun w(tag: String, msg: String): Int { println("[W/$tag] $msg"); return 0 }
    fun e(tag: String, msg: String): Int { System.err.println("[E/$tag] $msg"); return 0 }
    fun e(tag: String, msg: String, tr: Throwable): Int {
        System.err.println("[E/$tag] $msg: ${tr.message}")
        return 0
    }
}
