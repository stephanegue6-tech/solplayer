import React, { useEffect, useState, createContext, useContext } from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { TokenStore } from "./src/api";
import { colors } from "./src/theme/tokens";

import LoginScreen from "./src/screens/LoginScreen";
import DashboardScreen from "./src/screens/DashboardScreen";
import IncidentsListScreen from "./src/screens/IncidentsListScreen";
import IncidentDetailScreen from "./src/screens/IncidentDetailScreen";

// Contexte session minimal : qui est connecté, et comment se déconnecter.
// Un vrai store (zustand/redux) vaut le coup dès que l'app dépasse ce
// scaffold — inutile d'en ajouter un avant d'avoir plus de deux écrans qui
// partagent un état mutable.
export const SessionContext = createContext(null);
export const useSession = () => useContext(SessionContext);

const Stack = createNativeStackNavigator();

const navTheme = {
  dark: true,
  colors: {
    primary: colors.seal,
    background: colors.ink,
    card: colors.panel,
    text: colors.text,
    border: colors.border,
    notification: colors.seal,
  },
};

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    TokenStore.getUser().then((u) => {
      setUser(u);
      setChecking(false);
    });
  }, []);

  if (checking) return null; // remplacer par un écran de démarrage soigné

  return (
    <SessionContext.Provider value={{ user, setUser }}>
      <NavigationContainer theme={navTheme}>
        <StatusBar style="light" />
        <Stack.Navigator
          screenOptions={{
            headerStyle: { backgroundColor: colors.panel },
            headerTintColor: colors.text,
            contentStyle: { backgroundColor: colors.ink },
          }}
        >
          {!user ? (
            <Stack.Screen name="Connexion" component={LoginScreen} options={{ headerShown: false }} />
          ) : (
            <>
              <Stack.Screen name="Tableau de bord" component={DashboardScreen} />
              <Stack.Screen name="Incidents" component={IncidentsListScreen} />
              <Stack.Screen name="Détail incident" component={IncidentDetailScreen} />
            </>
          )}
        </Stack.Navigator>
      </NavigationContainer>
    </SessionContext.Provider>
  );
}
