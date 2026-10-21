import { useState } from "react";
import {
  Image,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";

import { supabase } from "../lib/supabase";
import { Button, Card, Note, TextField } from "../components/ui";
import { C, FontFamily, Spacing, Type } from "../constants/theme";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleLogin = async () => {
    setErrorMessage("");

    if (!email.trim() || !password) {
      setErrorMessage("Enter your email and password.");
      return;
    }

    try {
      setLoading(true);

      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });

      if (error) {
        setErrorMessage(error.message);
        return;
      }

      if (!data.session || !data.user) {
        setErrorMessage(
          "Sign-in did not return a session. Please try again."
        );
        return;
      }

      router.replace("/");
    } catch (error) {
      console.error("Login error:", error);

      setErrorMessage(
        error instanceof Error
          ? error.message
          : "An unexpected error occurred."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.screen}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.brand}>
            <Image
              source={require("../../assets/images/lungsight-mark.png")}
              style={styles.mark}
              accessibilityIgnoresInvertColors
            />
            <Text style={styles.wordmark}>
              LungSight<Text style={styles.wordmarkAccent}>AI</Text>
            </Text>
            <Text style={[Type.body, styles.tagline]}>
              AI-assisted chest X-ray screening for hospital teams
            </Text>
          </View>

          <Card style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={Type.title} accessibilityRole="header">
                Sign in
              </Text>
              <Text style={Type.caption}>
                For authorized hospital personnel only.
              </Text>
            </View>

            {errorMessage ? (
              <Note tone="danger" icon="alert-circle-outline">
                {errorMessage}
              </Note>
            ) : null}

            <TextField
              label="Email"
              placeholder="name@hospital.org"
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
              textContentType="emailAddress"
              value={email}
              onChangeText={setEmail}
              returnKeyType="next"
            />

            <TextField
              label="Password"
              placeholder="Your password"
              secureTextEntry
              autoComplete="password"
              textContentType="password"
              value={password}
              onChangeText={setPassword}
              returnKeyType="go"
              onSubmitEditing={() => void handleLogin()}
            />

            <Button
              label="Sign in"
              icon="log-in-outline"
              onPress={() => void handleLogin()}
              loading={loading}
            />
          </Card>

          <Text style={[Type.caption, styles.footer]}>
            Hospital administration is available on the LungSightAI web app.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: C.background,
  },
  flex: {
    flex: 1,
  },
  content: {
    flexGrow: 1,
    justifyContent: "center",
    padding: Spacing[5],
    gap: Spacing[5],
  },
  brand: {
    alignItems: "center",
    gap: Spacing[2],
  },
  mark: {
    width: 72,
    height: 72,
  },
  wordmark: {
    fontFamily: FontFamily.extrabold,
    fontSize: 28,
    color: C.ink,
    letterSpacing: -0.4,
  },
  wordmarkAccent: {
    color: C.primary,
  },
  tagline: {
    textAlign: "center",
  },
  card: {
    gap: Spacing[4],
    padding: Spacing[5],
  },
  cardHeader: {
    gap: 2,
  },
  footer: {
    textAlign: "center",
  },
});
