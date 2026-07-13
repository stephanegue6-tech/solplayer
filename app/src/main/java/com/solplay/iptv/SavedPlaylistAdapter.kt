package com.solplay.iptv

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class SavedPlaylistAdapter(
    private val playlists: List<SavedPlaylist>,
    private val activeId: String?,
    private val onConnect: (SavedPlaylist) -> Unit,
    private val onEdit: (SavedPlaylist) -> Unit,
    private val onDelete: (SavedPlaylist) -> Unit
) : RecyclerView.Adapter<SavedPlaylistAdapter.ViewHolder>() {

    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.tvPlaylistName)
        val details: TextView = view.findViewById(R.id.tvPlaylistDetails)
        val btnConnect: TextView = view.findViewById(R.id.btnConnect)
        val btnEdit: TextView = view.findViewById(R.id.btnEdit)
        val btnDelete: TextView = view.findViewById(R.id.btnDelete)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_saved_playlist, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val playlist = playlists[position]
        val isActive = playlist.id == activeId

        val modeLabel = if (playlist.mode == PlaylistMode.XTREAM) "Xtream Codes" else "Lien M3U"
        val sourceLabel = if (playlist.fromCode != null) " · Code admin" else ""
        holder.name.text = (if (isActive) "✅ " else "") + playlist.name
        holder.details.text = modeLabel + sourceLabel

        holder.btnConnect.text = if (isActive) "Connectée" else "Connecter"
        holder.btnConnect.setOnClickListener { onConnect(playlist) }
        holder.btnEdit.setOnClickListener { onEdit(playlist) }
        holder.btnDelete.setOnClickListener { onDelete(playlist) }
    }

    override fun getItemCount(): Int = playlists.size
}
