import { supabase } from "./supabase";

export type UserRole =
  | "radiologist"
  | "radiologic_technologist"
  | "staff"
  | "hospital_admin"
  | "superadmin";

export interface UserProfile {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  hospitalId: string | null;
  hospitalName: string;
}

export async function getCurrentUserProfile(): Promise<UserProfile> {
  // 1. Get the authenticated Supabase user
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError) {
    throw new Error(userError.message);
  }

  if (!user) {
    throw new Error("No authenticated user.");
  }

  // 2. Fetch the user's profile from the actual database table
  const { data: profile, error: profileError } = await supabase
    .from("user_profiles")
    .select(
      "user_id, user_fname, user_lname, role_id, hospital_id, is_active"
    )
    .eq("user_id", user.id)
    .maybeSingle();

  if (profileError) {
    throw new Error(`Failed to fetch user profile: ${profileError.message}`);
  }

  if (!profile) {
    throw new Error("User profile not found.");
  }

  if (!profile.is_active) {
    throw new Error("Your account is inactive. Contact your administrator.");
  }

  // 3. Fetch the role name using role_id
  const { data: roleRecord, error: roleError } = await supabase
    .from("roles")
    .select("role_id, role_name")
    .eq("role_id", profile.role_id)
    .maybeSingle();

  if (roleError) {
    throw new Error(`Failed to fetch user role: ${roleError.message}`);
  }

  if (!roleRecord) {
    throw new Error("No valid role is assigned to this account.");
  }

  // 4. Convert the database role to the app's internal role format
  const roleMap: Record<string, UserRole> = {
    Radiologist: "radiologist",
    "Radiologic Technologist": "radiologic_technologist",
    Staff: "staff",
    "Hospital Admin": "hospital_admin",
    Superadmin: "superadmin",
  };

  const normalizedRole = roleMap[roleRecord.role_name];

  if (!normalizedRole) {
    throw new Error(`Unsupported user role: ${roleRecord.role_name}`);
  }

  // 5. Fetch the hospital name, if the profile has a hospital_id
  let hospitalName = "";

  if (profile.hospital_id) {
    const { data: hospital, error: hospitalError } = await supabase
      .from("hospitals")
      .select("hospital_name")
      .eq("hospital_id", profile.hospital_id)
      .maybeSingle();

    if (hospitalError) {
      throw new Error(
        `Failed to fetch hospital: ${hospitalError.message}`
      );
    }

    hospitalName = hospital?.hospital_name ?? "";
  }

  // 6. Return a consistent profile object for the mobile app
  return {
    id: user.id,
    email: user.email ?? "",
    fullName: [profile.user_fname, profile.user_lname]
      .filter(Boolean)
      .join(" "),
    role: normalizedRole,
    hospitalId: profile.hospital_id ?? null,
    hospitalName,
  };
}

