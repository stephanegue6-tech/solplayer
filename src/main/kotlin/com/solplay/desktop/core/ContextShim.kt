package android.content

import org.json.JSONObject
import java.io.File

/**
 * Remplace android.content.Context / SharedPreferences sur desktop.
 *
 * Pourquoi un faux paquet du même nom qu'Android : la quasi-totalité des
 * fichiers métier de l'app (TrialManager, DeviceKeyManager,
 * DevicePlaylistSync, ChannelCacheStore...) n'utilisent Context QUE pour
 * appeler `context.getSharedPreferences(nom, mode)`. En fournissant ici une
 * classe Context avec la même méthode, ces fichiers sont copiés depuis
 * l'app Android SANS AUCUNE MODIFICATION de leur logique - seul le
 * "backend" de stockage change (fichiers JSON dans le dossier utilisateur
 * Windows au lieu du système SharedPreferences d'Android).
 *
 * Dossier de stockage sur Windows : %APPDATA%\SolPlay\prefs\<nom>.json
 */
class Context private constructor(val storageDir: File) {

    companion object {
        const val MODE_PRIVATE = 0

        /** Instance unique côté desktop (une seule "app" tourne à la fois, pas besoin de multi-contexte). */
        val APP: Context by lazy {
            val base = System.getenv("APPDATA")?.let { File(it, "SolPlay") }
                ?: File(System.getProperty("user.home"), ".solplay")
            val prefsDir = File(base, "prefs")
            prefsDir.mkdirs()
            Context(prefsDir)
        }
    }

    val applicationContext: Context get() = this

    /**
     * Équivalent d'Android Context.filesDir : un dossier de fichiers internes
     * à l'app, distinct des préférences (utilisé par ChannelCacheStore.kt,
     * porté tel quel depuis l'app Android, pour le cache JSON des chaînes).
     * Même dossier parent que les préférences, sous-dossier "files".
     */
    val filesDir: File by lazy {
        File(storageDir.parentFile ?: storageDir, "files").apply { mkdirs() }
    }

    fun getSharedPreferences(name: String, mode: Int): SharedPreferences =
        SharedPreferences(File(storageDir, "$name.json"))
}

/**
 * Équivalent minimal d'android.content.SharedPreferences : mêmes signatures
 * (getString/getLong/getBoolean, edit().put...().apply()), stockées dans un
 * simple fichier JSON. Suffisant pour tout ce qu'utilisent les fichiers
 * portés (aucun n'utilise les Set<String> ou les listeners de préférences).
 */
class SharedPreferences(private val file: File) {

    private fun readAll(): JSONObject =
        if (file.exists()) {
            try { JSONObject(file.readText()) } catch (e: Exception) { JSONObject() }
        } else JSONObject()

    fun getString(key: String, default: String?): String? {
        val o = readAll()
        return if (o.has(key) && !o.isNull(key)) o.getString(key) else default
    }

    fun getLong(key: String, default: Long): Long {
        val o = readAll()
        return if (o.has(key)) o.optLong(key, default) else default
    }

    fun getBoolean(key: String, default: Boolean): Boolean {
        val o = readAll()
        return if (o.has(key)) o.optBoolean(key, default) else default
    }

    fun contains(key: String): Boolean = readAll().has(key)

    fun edit(): Editor = Editor(file, readAll())

    class Editor(private val file: File, private val data: JSONObject) {
        fun putString(key: String, value: String?): Editor {
            if (value == null) data.put(key, JSONObject.NULL) else data.put(key, value)
            return this
        }
        fun putLong(key: String, value: Long): Editor { data.put(key, value); return this }
        fun putBoolean(key: String, value: Boolean): Editor { data.put(key, value); return this }
        fun remove(key: String): Editor { data.remove(key); return this }
        fun clear(): Editor {
            val keys = data.keys().asSequence().toList()
            keys.forEach { data.remove(it) }
            return this
        }
        /** Synchrone sur desktop (pas de vrai intérêt à différer l'écriture comme sur Android). */
        fun apply() {
            file.parentFile?.mkdirs()
            file.writeText(data.toString())
        }
    }
}
