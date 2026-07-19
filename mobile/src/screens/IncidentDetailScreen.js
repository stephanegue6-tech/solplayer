import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from "react-native";

import { Api } from "../api";
import { colors } from "../theme/tokens";

export default function IncidentDetailScreen({ route }) {
  const { id } = route.params;
  const [incident, setIncident] = useState(null);

  useEffect(() => {
    Api.incident(id).then(setIncident);
  }, [id]);

  if (!incident) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.seal} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ padding: 20 }}>
      <Text style={styles.title}>{incident.type_infraction}</Text>
      <Field label="Statut" value={incident.statut} />
      <Field label="Gravité" value={incident.gravite} />
      <Field label="Adresse" value={incident.adresse} />
      <Field label="Date / heure" value={incident.date_heure} />
      <Field label="Unité en charge" value={incident.unite_en_charge} />

      {/* Prochaine étape naturelle : intégrer react-native-maps ici pour
          afficher latitude/longitude, et un onglet "Chronologie" en
          rappelant GET /incidents/{id}/chronologie. Volontairement omis du
          scaffold pour rester lisible. */}
    </ScrollView>
  );
}

function Field({ label, value }) {
  if (!value) return null;
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.ink },
  center: { flex: 1, backgroundColor: colors.ink, justifyContent: "center", alignItems: "center" },
  title: { color: colors.text, fontSize: 22, fontWeight: "600", marginBottom: 20 },
  field: { marginBottom: 16, borderBottomWidth: 1, borderBottomColor: colors.border, paddingBottom: 10 },
  label: { color: colors.textFaint, fontSize: 11, textTransform: "uppercase", letterSpacing: 1 },
  value: { color: colors.text, fontSize: 15, marginTop: 4 },
});
