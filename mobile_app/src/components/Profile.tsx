import React, { useCallback, useEffect, useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";

import { getCurrentUserProfile, type UserProfile } from "../lib/user";
import { supabase } from "../lib/supabase";
import { C, FontFamily, Radius, Spacing, TouchTarget, Type } from "../constants/theme";
import {
  Button,
  Card,
  DetailRow,
  PageHeader,
  Pill,
  Screen,
  StateView,
  TextField,
} from "./ui";

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
    return <StateView kind="loading" title="Loading your profile" />;
  }

  if (!user) {
    return (
      <StateView
        kind="error"
        title="Unable to display your profile"
        message="Check your connection and try again."
        actionLabel="Try again"
        onAction={async () => {
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
        secondaryLabel="Log out"
        onSecondary={handleLogout}
      />
    );
  }

  const roleLabels: Record<UserProfile["role"], string> = {
    radiologist: "Radiologist",
    radiologic_technologist: "Radiologic Technologist",
    staff: "Staff",
    hospital_admin: "Hospital Admin",
    superadmin: "Superadmin",
  };

  const displayName =
    [form.user_fname, form.user_lname].filter(Boolean).join(" ") || user.fullName;

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Screen>
        <PageHeader title="Profile" caption="Your account and personal information." />

        <Card style={styles.identity}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initialsOf(displayName)}</Text>
          </View>
          <View style={styles.identityText}>
            <Text style={Type.heading} numberOfLines={1}>
              {displayName}
            </Text>
            <Text style={Type.caption} numberOfLines={1}>
              {user.email}
            </Text>
            <Pill label={roleLabels[user.role] ?? user.role} tone="primary" />
          </View>
        </Card>

        <Card>
          <View style={styles.sectionHeader}>
            <Text style={Type.title}>Personal information</Text>
            {!editing && (
              <Button
                label="Edit"
                icon="create-outline"
                variant="secondary"
                onPress={() => setEditing(true)}
                style={styles.editButton}
              />
            )}
          </View>

          {editing ? (
            <>
              <TextField
                label="First name *"
                value={form.user_fname}
                onChangeText={(value) => updateField("user_fname", value)}
                autoCapitalize="words"
              />
              <TextField
                label="Middle name"
                value={form.user_mname}
                onChangeText={(value) => updateField("user_mname", value)}
                autoCapitalize="words"
              />
              <TextField
                label="Last name *"
                value={form.user_lname}
                onChangeText={(value) => updateField("user_lname", value)}
                autoCapitalize="words"
              />
              <TextField
                label="Birthdate (YYYY-MM-DD)"
                value={form.user_birthdate}
                onChangeText={(value) => updateField("user_birthdate", value)}
                placeholder="2004-08-25"
                keyboardType="numbers-and-punctuation"
              />

              <View style={styles.choiceGroup}>
                <Text style={styles.choiceLabel}>Sex</Text>
                <View style={styles.choiceRow}>
                  {["Male", "Female"].map((option) => {
                    const selected = form.user_sex === option;

                    return (
                      <Pressable
                        key={option}
                        accessibilityRole="radio"
                        accessibilityState={{ selected }}
                        style={[styles.choice, selected && styles.choiceSelected]}
                        onPress={() =>
                          updateField("user_sex", selected ? "" : option)
                        }
                      >
                        <Text
                          style={[
                            Type.bodyStrong,
                            selected && styles.choiceTextSelected,
                          ]}
                        >
                          {option}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              </View>

              <TextField
                label="Contact number"
                value={form.user_contact_number}
                onChangeText={(value) => updateField("user_contact_number", value)}
                keyboardType="phone-pad"
              />
              <TextField
                label="Address"
                value={form.user_address}
                onChangeText={(value) => updateField("user_address", value)}
                multiline
              />
              <TextField
                label="Department"
                value={form.user_department}
                onChangeText={(value) => updateField("user_department", value)}
              />

              <View style={styles.actionRow}>
                <Button
                  label="Cancel"
                  variant="secondary"
                  onPress={handleCancel}
                  disabled={saving}
                  style={styles.actionButton}
                />
                <Button
                  label="Save changes"
                  onPress={() => void handleSave()}
                  loading={saving}
                  style={styles.actionButton}
                />
              </View>
            </>
          ) : (
            <View>
              <DetailRow label="First name" value={form.user_fname} />
              <DetailRow label="Middle name" value={form.user_mname} />
              <DetailRow label="Last name" value={form.user_lname} />
              <DetailRow label="Birthdate" value={form.user_birthdate} />
              <DetailRow label="Sex" value={form.user_sex} />
              <DetailRow label="Contact number" value={form.user_contact_number} />
              <DetailRow label="Address" value={form.user_address} />
              <DetailRow label="Department" value={form.user_department} />
            </View>
          )}
        </Card>

        <Card>
          <Text style={Type.title}>Account</Text>
          <View>
            <DetailRow label="Email address" value={user.email} />
            <DetailRow label="Role" value={roleLabels[user.role] ?? user.role} />
            <DetailRow label="Hospital" value={user.hospitalName || "Not assigned"} />
          </View>
          <Text style={Type.caption}>
            Password and profile picture changes are available on the LungSightAI web app.
          </Text>
        </Card>

        <Button
          label="Log out"
          icon="log-out-outline"
          variant="danger"
          onPress={handleLogout}
          loading={loggingOut}
        />
      </Screen>
    </KeyboardAvoidingView>
  );
}

function initialsOf(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);

  if (words.length === 0) return "U";
  if (words.length === 1) return words[0][0].toUpperCase();

  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: C.background,
  },
  identity: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing[4],
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: C.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    fontFamily: FontFamily.bold,
    fontSize: 20,
    color: C.primary,
  },
  identityText: {
    flex: 1,
    gap: 4,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  editButton: {
    minHeight: 40,
    paddingHorizontal: Spacing[3],
  },
  choiceGroup: {
    gap: 6,
  },
  choiceLabel: {
    ...Type.label,
    color: C.textSoft,
  },
  choiceRow: {
    flexDirection: "row",
    gap: Spacing[2],
  },
  choice: {
    flex: 1,
    minHeight: TouchTarget,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  choiceSelected: {
    borderColor: C.primary,
    backgroundColor: C.primarySoft,
  },
  choiceTextSelected: {
    color: C.primary,
  },
  actionRow: {
    flexDirection: "row",
    gap: Spacing[3],
    marginTop: Spacing[2],
  },
  actionButton: {
    flex: 1,
  },
});
