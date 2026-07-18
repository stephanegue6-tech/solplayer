package com.solplay.iptv

/**
 * Conserve la liste des chaînes en mémoire, partagée entre PlaylistActivity
 * et ChannelsActivity.
 *
 * Pourquoi : Android limite à environ 1 Mo la taille des données qu'on peut
 * faire transiter d'un écran à l'autre via un Intent (limite du buffer de
 * transaction Binder). Les playlists IPTV contiennent souvent des milliers
 * de chaînes, ce qui dépasse largement cette limite et provoque un crash
 * "Failure from system" au moment de startActivity(). En passant par cet
 * objet en mémoire au lieu de intent.putExtra(), on évite complètement
 * cette limite.
 */
object ChannelRepository {
    var channels: List<Channel> = emptyList()
        private set

    /** Liste (filtrée par onglet/catégorie) en cours de visionnage, pour permettre
     * de changer de chaîne directement depuis le lecteur sans revenir en arrière. */
    var playingList: List<Channel> = emptyList()
        private set

    /** Chaînes Live à afficher dans la grille EPG (EpgGridActivity), déposées
     * ici par ChannelsActivity juste avant d'ouvrir cet écran (même
     * raisonnement que playingList : éviter la limite de taille des Intent). */
    var epgGridChannels: List<Channel> = emptyList()
        private set

    fun setChannels(newChannels: List<Channel>) {
        channels = newChannels
    }

    fun setPlayingList(list: List<Channel>) {
        playingList = list
    }

    fun setEpgGridChannels(list: List<Channel>) {
        epgGridChannels = list
    }

    fun clear() {
        channels = emptyList()
        playingList = emptyList()
        epgGridChannels = emptyList()
    }
}
