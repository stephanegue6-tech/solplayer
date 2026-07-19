import React, { useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Api, TokenStore, ApiError } from "../api";
import { useSession } from "../../App";
import { colors, radius } from "../theme/tokens";

export default function LoginScreen() {
  const { setUser } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleLogin() {
    setError(null);
    setLoading(true);
    try {
      const tokenResponse = await Api.login(email.trim(), password);
      await TokenStore.save(tokenResponse);
      setUser(await TokenStore.getUser());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Connexion impossible");
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.brand}>
        <Text style={styles.brandTitle}>CrimTrack</Text>
        <Text style={styles.brandSub}>Console d'enquête — accès mobile</Text>
      </View>

      <View style={styles.form}>
        <Text style={styles.label}>Identifiant</Text>
        <TextInput
          style={styles.input}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          placeholder="prenom.nom@unite.gouv"
          placeholderTextColor={colors.textFaint}
        />

        <Text style={styles.label}>Mot de passe</Text>
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder="••••••••"
          placeholderTextColor={colors.textFaint}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={({ pressed }) => [styles.button, pressed && { opacity: 0.85 }]}
          onPress={handleLogin}
          disabled={loading}
        >
          {loading ? <ActivityIndicator color={colors.ink} /> : <Text style={styles.buttonText}>Se connecter</Text>}
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.ink, justifyContent: "center", padding: 24 },
  brand: { marginBottom: 40, alignItems: "center" },
  brandTitle: { color: colors.text, fontSize: 32, fontWeight: "600", letterSpacing: 0.5 },
  brandSub: { color: colors.textDim, marginTop: 6, fontSize: 13 },
  form: { gap: 4 },
  label: { color: colors.textFaint, fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginTop: 16, marginBottom: 6 },
  input: {
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius,
    padding: 12,
    color: colors.text,
    fontSize: 15,
  },
  error: { color: colors.danger, marginTop: 14, fontSize: 13 },
  button: {
    marginTop: 28,
    backgroundColor: colors.seal,
    borderRadius: radius,
    padding: 14,
    alignItems: "center",
  },
  buttonText: { color: colors.ink, fontWeight: "700", fontSize: 15 },
});
