import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { router } from "expo-router";

export default function RadTechTest() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Rad Tech Test UI</Text>

      <Text style={styles.subtitle}>
        This is a separate screen for the Radiologic Technologist role.
      </Text>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.back()}
      >
        <Text style={styles.buttonText}>
          Back to Dashboard
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },

  title: {
    fontSize: 28,
    fontWeight: "bold",
  },

  subtitle: {
    marginTop: 10,
    textAlign: "center",
    color: "#666",
  },

  button: {
    marginTop: 30,
    backgroundColor: "#2563eb",
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 10,
  },

  buttonText: {
    color: "#fff",
    fontWeight: "bold",
  },
});