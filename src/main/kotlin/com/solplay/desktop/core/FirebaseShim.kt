package com.google.firebase.database

import kotlinx.coroutines.Deferred
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject

/**
 * Remplace le SDK Android com.google.firebase.database.* sur desktop, en
 * s'appuyant sur l'API REST publique de Firebase Realtime Database
 * (n'importe quel chemin + ".json" en HTTPS) au lieu du SDK Android natif
 * (absent hors Android). Reproduit volontairement la même API
 * (getReference/child/get()/await()/exists()/children/getValue) pour que
 * TrialManager.kt, DevicePlaylistSync.kt et CodeRedeemer.kt soient copiés
 * depuis l'app Android SANS AUCUNE MODIFICATION de leur logique métier.
 *
 * Limite volontaire de ce shim (lecture seule) : ces 3 fichiers ne font que
 * des LECTURES (get), jamais d'écriture - donc set()/update()/push() ne
 * sont pas implémentés ici. Les écritures depuis le poste client (aucune
 * dans ces 3 fichiers) resteraient de toute façon à éviter sans règles de
 * sécurité Firebase adaptées, exactement comme sur Android.
 */
private const val DATABASE_URL = "https://solplay-2ec6c-default-rtdb.europe-west1.firebasedatabase.app"

private val httpClient = OkHttpClient()

class FirebaseDatabase private constructor() {
    companion object {
        private val instance = FirebaseDatabase()
        fun getInstance(): FirebaseDatabase = instance
    }

    fun getReference(path: String): DatabaseReference = DatabaseReference(path.trim('/'))
}

class DatabaseReference internal constructor(private val path: String) {

    fun child(name: String): DatabaseReference =
        DatabaseReference(if (path.isEmpty()) name else "$path/$name")

    /** Reproduit `.get()` (Task<DataSnapshot>) : ici directement une coroutine `Deferred`. */
    fun get(): GetOperation = GetOperation(path)

    /**
     * Reproduit addValueEventListener/removeEventListener (utilisés par
     * TrialManager pour ".info/serverTimeOffset"). Simplification assumée
     * pour desktop : contrairement au SDK websocket Android qui attend une
     * synchro pleinement établie, ce shim REST déclenche onDataChange dès
     * qu'une réponse HTTP est reçue - la valeur REST reflète déjà l'état
     * serveur au moment de la requête, donc ça reste correct pour ce cas
     * d'usage précis (mesure ponctuelle de l'offset d'horloge), juste sans
     * l'attente de "warm-up" websocket propre à Android.
     */
    fun addValueEventListener(listener: ValueEventListener) {
        try {
            listener.onDataChange(fetchJson(path))
        } catch (e: Exception) {
            listener.onCancelled(DatabaseError(e.message ?: "Erreur réseau"))
        }
    }

    fun removeEventListener(listener: ValueEventListener) {
        // Rien à faire : notre implémentation ne conserve pas de listener actif (appel synchrone one-shot).
    }
}

interface ValueEventListener {
    fun onDataChange(snapshot: DataSnapshot)
    fun onCancelled(error: DatabaseError)
}

class DatabaseError internal constructor(val message: String)

/** Petit objet intermédiaire pour que `.get().await()` s'écrive exactement comme sur Android. */
class GetOperation internal constructor(private val path: String) {
    suspend fun await(): DataSnapshot = coroutineScope {
        val deferred: Deferred<DataSnapshot> = async {
            fetchJson(path)
        }
        deferred.await()
    }
}

private fun fetchJson(path: String): DataSnapshot {
    val url = "$DATABASE_URL/$path.json"
    val request = Request.Builder().url(url).get().build()
    httpClient.newCall(request).execute().use { response ->
        if (!response.isSuccessful) return DataSnapshot(JSONObject.NULL, path.substringAfterLast('/'))
        val body = response.body?.string()?.trim()
        if (body.isNullOrEmpty() || body == "null") {
            return DataSnapshot(JSONObject.NULL, path.substringAfterLast('/'))
        }
        // La réponse REST est soit un objet JSON, soit une valeur "brute"
        // (nombre, booléen, chaîne) pour les feuilles - org.json ne parse
        // que des objets/tableaux, donc on enveloppe les valeurs brutes.
        return try {
            DataSnapshot(JSONObject(body), path.substringAfterLast('/'))
        } catch (e: Exception) {
            DataSnapshot(JSONObject().put("_raw", JSONObject.wrap(parseLeaf(body))), path.substringAfterLast('/'), rawLeaf = parseLeaf(body))
        }
    }
}

private fun parseLeaf(body: String): Any? = when {
    body == "true" -> true
    body == "false" -> false
    body.toLongOrNull() != null -> body.toLong()
    body.toDoubleOrNull() != null -> body.toDouble()
    body.startsWith("\"") && body.endsWith("\"") -> body.substring(1, body.length - 1)
    else -> body
}

/**
 * Équivalent minimal d'android's DataSnapshot : exists(), child(key),
 * getValue(Class), children (itération), key.
 */
class DataSnapshot internal constructor(
    private val json: Any,
    val key: String?,
    private val rawLeaf: Any? = null
) {
    fun exists(): Boolean = json != JSONObject.NULL && !(json is JSONObject && json.length() == 0 && rawLeaf == null)

    fun child(name: String): DataSnapshot {
        if (json !is JSONObject || !json.has(name)) return DataSnapshot(JSONObject.NULL, name)
        val value = json.get(name)
        return if (value is JSONObject) DataSnapshot(value, name) else DataSnapshot(JSONObject.NULL, name, rawLeaf = value)
    }

    val children: Iterable<DataSnapshot>
        get() {
            if (json !is JSONObject) return emptyList()
            return json.keys().asSequence().map { k ->
                val v = json.get(k)
                if (v is JSONObject) DataSnapshot(v, k) else DataSnapshot(JSONObject.NULL, k, rawLeaf = v)
            }.toList()
        }

    fun <T> getValue(clazz: Class<T>): T? {
        val value = rawLeaf ?: (if (json == JSONObject.NULL) null else json)
        if (value == null) return null
        return try {
            @Suppress("UNCHECKED_CAST")
            when (clazz) {
                java.lang.Boolean::class.java, Boolean::class.java -> (value as? Boolean ?: value.toString().toBoolean()) as T
                java.lang.Long::class.java, Long::class.java -> when (value) {
                    is Long -> value as T
                    is Double -> value.toLong() as T
                    is Int -> value.toLong() as T
                    else -> value.toString().toLongOrNull() as T?
                }
                java.lang.Double::class.java, Double::class.java -> when (value) {
                    is Double -> value as T
                    is Long -> value.toDouble() as T
                    else -> value.toString().toDoubleOrNull() as T?
                }
                String::class.java -> value.toString() as T
                else -> value as T
            }
        } catch (e: Exception) {
            null
        }
    }
}
