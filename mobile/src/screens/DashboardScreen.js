import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet, Pressable, ScrollView, RefreshControl } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Api, TokenStore } from "../api";
import { useSession } from "../../App";
import { colors, radius } from "../theme/tokens";

// Objectif de cet écran : ce qu'un enquêteur de terrain regarde en premier
// en sortant du véhicule — incidents récents + accès rapide, pas une copie
// 1:1 du dashboard web (qui a plus d'espace pour des graphiques).
export default function DashboardScreen({ navigation }) {
  const { user, setUser } = useSession();
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const data = await Api.incidents({ limit: 5 });
      setIncidents(Array.isArray(data) ? data : data.items || []);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleLogout() {
    await TokenStore.clear();
    setUser(null);
  }

  return (
    <SafeAreaView style={styles.screen} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.seal} />}
      >
        <Text style={styles.greeting}>Bonjour {user?.prenom || ""}</Text>
        <Text style={styles.role}>{user?.role}</Text>

        <View style={styles.quickActions}>
          <QuickAction label="Incidents" onPress={() => navigation.navigate("Incidents")} />
          <QuickAction label="Carte" onPress={() => {}} note="à venir" />
          <QuickAction label="ANPR" onPress={() => {}} note="à venir" />
        </View>

        <Text style={styles.sectionTitle}>Incidents récents</Text>
        {loading ? (
          <Text style={styles.muted}>Chargement…</Text>
        ) : incidents.length === 0 ? (
          <Text style={styles.muted}>Aucun incident récent.</Text>
        ) : (
          incidents.map((inc) => (
            <Pressable
              key={inc.id}
              style={styles.incidentRow}
              onPress={() => navigation.navigate("Détail incident", { id: inc.id })}
            >
              <Text style={styles.incidentType}>{inc.type_infraction}</Text>
              <Text style={styles.incidentMeta}>{inc.adresse || "Lieu non précisé"} · {inc.statut}</Text>
            </Pressable>
          ))
        )}

        <Pressable style={styles.logout} onPress={handleLogout}>
          <Text style={styles.logoutText}>Se déconnecter</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

function QuickAction({ label, onPress, note }) {
  return (
    <Pressable style={styles.quickAction} onPress={onPress}>
      <Text style={styles.quickActionLabel}>{label}</Text>
      {note ? <Text style={styles.quickActionNote}>{note}</Text> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.ink },
  content: { padding: 20, paddingBottom: 40 },
  greeting: { color: colors.text, fontSize: 24, fontWeight: "600" },
  role: { color: colors.textFaint, fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginTop: 4 },
  quickActions: { flexDirection: "row", gap: 10, marginTop: 24 },
  quickAction: { flex: 1, backgroundColor: colors.panel, borderWidth: 1, borderColor: colors.border, borderRadius: radius, padding: 14, alignItems: "center" },
  quickActionLabel: { color: colors.text, fontWeight: "600" },
  quickActionNote: { color: colors.textFaint, fontSize: 10, marginTop: 4 },
  sectionTitle: { color: colors.textDim, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, marginTop: 32, marginBottom: 12 },
  muted: { color: colors.textFaint },
  incidentRow: { backgroundColor: colors.panel, borderRadius: radius, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 8 },
  incidentType: { color: colors.text, fontWeight: "600" },
  incidentMeta: { color: colors.textDim, fontSize: 12, marginTop: 4 },
  logout: { marginTop: 32, alignItems: "center", padding: 12 },
  logoutText: { color: colors.textFaint, fontSize: 13 },
});
