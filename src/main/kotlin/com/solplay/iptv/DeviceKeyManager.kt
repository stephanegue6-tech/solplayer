package com.solplay.iptv

import android.content.Context
import java.util.UUID

/**
 * Génère et conserve une clé d'appareil unique et permanente.
 *
 * Pourquoi pas la vraie adresse MAC ? Depuis Android 6, Google interdit à
 * toute application d'accéder à l'adresse MAC réelle du Wi-Fi pour protéger
 * la vie privée des utilisateurs (aucune app, même Netflix ou WhatsApp, ne
 * peut l'obtenir). Cette "clé appareil" joue exactement le même rôle
 * (identifiant unique et stable par appareil) et est la méthode utilisée en
 * pratique par la quasi-totalité des vraies applications IPTV.
 */
object DeviceKeyManager {

    private const val PREFS = "solplay_prefs"
    private const val KEY_DEVICE_KEY = "device_key"

    fun getDeviceKey(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        var key = prefs.getString(KEY_DEVICE_KEY, null)
        if (key.isNullOrEmpty()) {
            key = UUID.randomUUID().toString().replace("-", "").take(16).uppercase()
            prefs.edit().putString(KEY_DEVICE_KEY, key).apply()
        }
        return key
    }
}
