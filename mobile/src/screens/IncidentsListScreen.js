import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet, FlatList, Pressable, ActivityIndicator } from "react-native";

import { Api } from "../api";
import { colors, radius, graviteColor } from "../theme/tokens";

export default function IncidentsListScreen({ navigation }) {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Api.incidents()
      .then((data) => setIncidents(Array.isArray(data) ? data : data.items || []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.seal} />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.screen}
      contentContainerStyle={{ padding: 16 }}
      data={incidents}
      keyExtractor={(item) => item.id}
      ListEmptyComponent={<Text style={styles.muted}>Aucun incident.</Text>}
      renderItem={({ item }) => (
        <Pressable style={styles.row} onPress={() => navigation.navigate("Détail incident", { id: item.id })}>
          <View style={[styles.severityDot, { backgroundColor: graviteColor(item.gravite) }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.type}>{item.type_infraction}</Text>
            <Text style={styles.meta}>{item.adresse || "Lieu non précisé"}</Text>
          </View>
          <Text style={styles.statut}>{item.statut}</Text>
        </Pressable>
      )}
    />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.ink },
  center: { flex: 1, backgroundColor: colors.ink, justifyContent: "center", alignItems: "center" },
  muted: { color: colors.textFaint, textAlign: "center", marginTop: 40 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius,
    padding: 14,
    marginBottom: 8,
  },
  severityDot: { width: 8, height: 8, borderRadius: 4 },
  type: { color: colors.text, fontWeight: "600" },
  meta: { color: colors.textDim, fontSize: 12, marginTop: 2 },
  statut: { color: colors.textFaint, fontSize: 11, textTransform: "uppercase" },
});
