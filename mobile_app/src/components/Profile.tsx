import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";

import { getCurrentUserProfile, type UserProfile } from "../lib/user";
import { supabase } from "../lib/supabase";

type EditableProfile = {
  user_fname: string;
  user_mname: string;
  user_lname: string;
  user_birthdate: string;
  user_sex: string;
  user_contact_number: string;
  user_address: string;
  user_department: string;
};

const EMPTY_FORM: EditableProfile = {
  user_fname: "",
  user_mname: "",
  user_lname: "",
  user_birthdate: "",
  user_sex: "",
  user_contact_number: "",
  user_address: "",
  user_department: "",
};

export default function Profile() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [form, setForm] = useState<EditableProfile>(EMPTY_FORM);
  const [originalForm, setOriginalForm] =
    useState<EditableProfile>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [editing, setEditing] = useState(false);

  const loadProfile = useCallback(async () => {
    const currentUser = await getCurrentUserProfile();

    const {
      data: { user: authUser },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError) throw authError;
    if (!authUser) throw new Error("You are not logged in.");
    console.log("Authenticated user ID:", authUser.id);

    const { data, error } = await supabase
      .from("user_profiles")
      .select(
        "user_fname, user_mname, user_lname, user_birthdate, user_sex, user_contact_number, user_address, user_department"
      )
      .eq("user_id", authUser.id)
      .maybeSingle();

    if (error) throw error;
    if (!data) throw new Error("Your profile could not be found.");

    const loadedForm: EditableProfile = {
      user_fname: data.user_fname ?? "",
      user_mname: data.user_mname ?? "",
      user_lname: data.user_lname ?? "",
      user_birthdate: data.user_birthdate ?? "",
      user_sex: data.user_sex ?? "",
      user_contact_number: data.user_contact_number ?? "",
      user_address: data.user_address ?? "",
      user_department: data.user_department ?? "",
    };

    setUser(currentUser);
    setForm(loadedForm);
    setOriginalForm(loadedForm);
  }, []);

  useEffect(() => {
    const initialize = async () => {
      try {
        await loadProfile();
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to load your profile.";
        Alert.alert("Profile Error", message);
      } finally {
        setLoading(false);
      }
    };

    void initialize();
  }, [loadProfile]);

  const updateField = (field: keyof EditableProfile, value: string) => {
    setForm((previous) => ({ ...previous, [field]: value }));
  };

  const handleSave = async () => {
    const firstName = form.user_fname.trim();
    const middleName = form.user_mname.trim();
    const lastName = form.user_lname.trim();
    const birthdate = form.user_birthdate.trim();
    const sex = form.user_sex.trim();

    if (!firstName || !lastName) {
      Alert.alert("Required Fields", "First name and last name are required.");
      return;
    }

    if (birthdate) {
      const match = birthdate.match(/^(\d{4})-(\d{2})-(\d{2})$/);

      if (!match) {
        Alert.alert(
          "Invalid Birthdate",
          "Use YYYY-MM-DD format, for example 2004-08-25."
        );
        return;
      }

      const year = Number(match[1]);
      const month = Number(match[2]);
      const day = Number(match[3]);
      const date = new Date(Date.UTC(year, month - 1, day));

      if (
        date.getUTCFullYear() !== year ||
        date.getUTCMonth() !== month - 1 ||
        date.getUTCDate() !== day
      ) {
        Alert.alert("Invalid Birthdate", "Enter a valid calendar date.");
        return;
      }
    }

    if (sex && !["Male", "Female"].includes(sex)) {
      Alert.alert("Invalid Sex", "Choose Male or Female, or leave it blank.");
      return;
    }

    try {
      setSaving(true);

      const {
        data: { user: authUser },
        error: authError,
      } = await supabase.auth.getUser();

      if (authError) throw authError;
      if (!authUser) throw new Error("Your session has expired. Please log in again.");

      const { data: updatedProfile, error: updateError } = await supabase
        .from("user_profiles")
        .update({
          user_fname: firstName,
          user_mname: middleName || null,
          user_lname: lastName,
          user_birthdate: birthdate || null,
          user_sex: sex || null,
          user_contact_number: form.user_contact_number.trim() || null,
          user_address: form.user_address.trim() || null,
          user_department: form.user_department.trim() || null,
          updated_at: new Date().toISOString(),
        })
        .eq("user_id", authUser.id)
        .select(
          "user_id, user_fname, user_mname, user_lname, user_birthdate, user_sex, user_contact_number, user_address, user_department"
        )
        .maybeSingle();

      if (updateError) {
        throw new Error(`Database update failed: ${updateError.message}`);
      }

      if (!updatedProfile) {
        throw new Error(
          "No profile row was updated. Check that your profile user_id matches your authenticated user ID and that your Supabase UPDATE and SELECT policies allow this operation."
        );
      }

      if (
        updatedProfile.user_fname !== firstName ||
        updatedProfile.user_lname !== lastName
      ) {
        throw new Error(
          "The database returned a different name from the one you entered."
        );
      }

      const savedForm: EditableProfile = {
        user_fname: updatedProfile.user_fname ?? "",
        user_mname: updatedProfile.user_mname ?? "",
        user_lname: updatedProfile.user_lname ?? "",
        user_birthdate: updatedProfile.user_birthdate ?? "",
        user_sex: updatedProfile.user_sex ?? "",
        user_contact_number: updatedProfile.user_contact_number ?? "",
        user_address: updatedProfile.user_address ?? "",
        user_department: updatedProfile.user_department ?? "",
      };

      setForm(savedForm);
      setOriginalForm(savedForm);
      await loadProfile();
      setEditing(false);

      Alert.alert("Success", "Your profile changes have been saved.");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to save your profile.";
      Alert.alert("Save Failed", message);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    Alert.alert("Discard Changes", "Discard your unsaved changes?", [
      { text: "Keep Editing", style: "cancel" },
      {
        text: "Discard",
        style: "destructive",
        onPress: () => {
          setForm(originalForm);
          setEditing(false);
        },
      },
    ]);
  };

  const handleLogout = () => {
    Alert.alert("Log Out", "Are you sure you want to log out?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Log Out",
        style: "destructive",
        onPress: () => void performLogout(),
      },
    ]);
  };

  const performLogout = async () => {
    try {
      setLoggingOut(true);
      const { error } = await supabase.auth.signOut();

      if (error) throw error;

      router.replace("/login");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to log out.";
      Alert.alert("Logout Failed", message);
      setLoggingOut(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#2563EB" />
        <Text style={styles.loadingText}>Loading profile...</Text>
      </View>
    );
  }

  if (!user) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>Unable to display your profile.</Text>
        <Pressable
          style={styles.primaryButton}
          onPress={async () => {
            try {
              setLoading(true);
              await loadProfile();
            } catch (error) {
              Alert.alert(
                "Profile Error",
                error instanceof Error ? error.message : "Unable to load profile."
              );
            } finally {
              setLoading(false);
            }
          }}
        >
          <Text style={styles.primaryButtonText}>Try Again</Text>
        </Pressable>
        <Pressable style={styles.logoutButton} onPress={handleLogout}>
          <Text style={styles.logoutButtonText}>Log Out</Text>
        </Pressable>
      </View>
    );
  }

  const roleLabels: Record<UserProfile["role"], string> = {
    radiologist: "Radiologist",
    radiologic_technologist: "Radiologic Technologist",
    staff: "Staff",
    hospital_admin: "Hospital Admin",
    superadmin: "Superadmin",
  };

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {(form.user_fname.charAt(0) || "U").toUpperCase()}
            </Text>
          </View>
          <Text style={styles.title}>My Profile</Text>
          <Text style={styles.subtitle}>Manage your personal information</Text>
        </View>

        <View style={styles.card}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Personal Information</Text>
            {!editing && (
              <Pressable
                style={styles.editButton}
                onPress={() => setEditing(true)}
              >
                <Text style={styles.editButtonText}>Edit Profile</Text>
              </Pressable>
            )}
          </View>

          {editing ? (
            <>
              <Field
                label="First Name *"
                value={form.user_fname}
                onChangeText={(value) => updateField("user_fname", value)}
              />
              <Field
                label="Middle Name"
                value={form.user_mname}
                onChangeText={(value) => updateField("user_mname", value)}
              />
              <Field
                label="Last Name *"
                value={form.user_lname}
                onChangeText={(value) => updateField("user_lname", value)}
              />
              <Field
                label="Birthdate (YYYY-MM-DD)"
                value={form.user_birthdate}
                onChangeText={(value) => updateField("user_birthdate", value)}
                placeholder="2004-08-25"
              />

              <Text style={styles.fieldLabel}>Sex</Text>
              <View style={styles.sexOptions}>
                {["Male", "Female"].map((option) => (
                  <Pressable
                    key={option}
                    style={[
                      styles.sexOption,
                      form.user_sex === option && styles.sexOptionSelected,
                    ]}
                    onPress={() =>
                      updateField(
                        "user_sex",
                        form.user_sex === option ? "" : option
                      )
                    }
                  >
                    <Text
                      style={[
                        styles.sexOptionText,
                        form.user_sex === option &&
                          styles.sexOptionTextSelected,
                      ]}
                    >
                      {option}
                    </Text>
                  </Pressable>
                ))}
              </View>

              <Field
                label="Contact Number"
                value={form.user_contact_number}
                onChangeText={(value) =>
                  updateField("user_contact_number", value)
                }
                keyboardType="phone-pad"
              />
              <Field
                label="Address"
                value={form.user_address}
                onChangeText={(value) => updateField("user_address", value)}
                multiline
              />
              <Field
                label="Department"
                value={form.user_department}
                onChangeText={(value) => updateField("user_department", value)}
              />

              <View style={styles.actionRow}>
                <Pressable
                  style={[styles.secondaryButton, styles.actionButton]}
                  onPress={handleCancel}
                  disabled={saving}
                >
                  <Text style={styles.secondaryButtonText}>Cancel</Text>
                </Pressable>
                <Pressable
                  style={[styles.primaryButton, styles.actionButton]}
                  onPress={() => void handleSave()}
                  disabled={saving}
                >
                  {saving ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <Text style={styles.primaryButtonText}>Save Changes</Text>
                  )}
                </Pressable>
              </View>
            </>
          ) : (
            <>
              <Detail label="First Name" value={form.user_fname} />
              <Detail label="Middle Name" value={form.user_mname} />
              <Detail label="Last Name" value={form.user_lname} />
              <Detail label="Birthdate" value={form.user_birthdate} />
              <Detail label="Sex" value={form.user_sex} />
              <Detail label="Contact Number" value={form.user_contact_number} />
              <Detail label="Address" value={form.user_address} />
              <Detail label="Department" value={form.user_department} />
            </>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Account Information</Text>
          <Detail label="Email Address" value={user.email} />
          <Detail label="Role" value={roleLabels[user.role] ?? user.role} />
          <Detail label="Hospital" value={user.hospitalName || "Not assigned"} />
        </View>

        <Pressable
          style={[styles.logoutButton, loggingOut && styles.disabledButton]}
          onPress={handleLogout}
          disabled={loggingOut}
        >
          {loggingOut ? (
            <ActivityIndicator color="#DC2626" />
          ) : (
            <Text style={styles.logoutButtonText}>Log Out</Text>
          )}
        </Pressable>

        <Text style={styles.footer}>LungSight · Profile Settings</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

type FieldProps = {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  keyboardType?: "default" | "phone-pad";
  multiline?: boolean;
};

function Field({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType = "default",
  multiline = false,
}: FieldProps) {
  return (
    <View style={styles.fieldContainer}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        style={[styles.input, multiline && styles.multilineInput]}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder ?? `Enter ${label.toLowerCase()}`}
        placeholderTextColor="#9CA3AF"
        keyboardType={keyboardType}
        multiline={multiline}
        textAlignVertical={multiline ? "top" : "center"}
        autoCapitalize="sentences"
      />
    </View>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value?.trim() || "Not provided"}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#F3F6FB",
  },
  content: {
    padding: 20,
    paddingBottom: 36,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: "#F3F6FB",
  },
  loadingText: {
    marginTop: 12,
    color: "#64748B",
    fontSize: 14,
  },
  errorText: {
    color: "#B91C1C",
    fontSize: 15,
    marginBottom: 16,
  },
  header: {
    alignItems: "center",
    marginTop: 12,
    marginBottom: 24,
  },
  avatar: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: "#DBEAFE",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 14,
  },
  avatarText: {
    fontSize: 30,
    fontWeight: "700",
    color: "#1D4ED8",
  },
  title: {
    fontSize: 25,
    fontWeight: "700",
    color: "#0F172A",
  },
  subtitle: {
    fontSize: 14,
    color: "#64748B",
    marginTop: 5,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 18,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E5EAF2",
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: "700",
    color: "#0F172A",
    marginBottom: 12,
  },
  editButton: {
    backgroundColor: "#EFF6FF",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  editButtonText: {
    color: "#1D4ED8",
    fontSize: 13,
    fontWeight: "600",
  },
  detailRow: {
    paddingVertical: 11,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  detailLabel: {
    fontSize: 12,
    color: "#64748B",
    marginBottom: 5,
  },
  detailValue: {
    fontSize: 15,
    color: "#0F172A",
    fontWeight: "500",
  },
  fieldContainer: {
    marginBottom: 15,
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: "#334155",
    marginBottom: 7,
  },
  input: {
    minHeight: 46,
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: "#0F172A",
    backgroundColor: "#FFFFFF",
    fontSize: 14,
  },
  multilineInput: {
    minHeight: 90,
  },
  sexOptions: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 16,
  },
  sexOption: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#CBD5E1",
    alignItems: "center",
  },
  sexOptionSelected: {
    borderColor: "#2563EB",
    backgroundColor: "#EFF6FF",
  },
  sexOptionText: {
    color: "#475569",
    fontWeight: "500",
  },
  sexOptionTextSelected: {
    color: "#1D4ED8",
    fontWeight: "700",
  },
  actionRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 8,
  },
  actionButton: {
    flex: 1,
  },
  primaryButton: {
    minHeight: 46,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: "#2563EB",
    alignItems: "center",
    justifyContent: "center",
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
  secondaryButton: {
    minHeight: 46,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryButtonText: {
    color: "#334155",
    fontSize: 14,
    fontWeight: "600",
  },
  logoutButton: {
    minHeight: 48,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#DC2626",
    borderRadius: 10,
    paddingVertical: 13,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 8,
    marginBottom: 12,
  },
  logoutButtonText: {
    color: "#DC2626",
    fontSize: 15,
    fontWeight: "700",
  },
  disabledButton: {
    opacity: 0.6,
  },
  footer: {
    color: "#94A3B8",
    fontSize: 12,
    textAlign: "center",
    marginTop: 8,
  },
});
