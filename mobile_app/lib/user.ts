import { supabase } from "./supabase";

export type UserRole =
  | "physician"
  | "rad_tech"
  | "hospital_admin"
  | "super_admin";

export interface UserProfile {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  hospitalId: string | null;
  hospitalName: string;
}

export async function getCurrentUserProfile(): Promise<UserProfile> {
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

  const { data: profile, error: profileError } =
    await supabase
      .from("profiles")
      .select("full_name, role, hospital_id")
      .eq("id", user.id)
      .single();

  if (profileError) {
    throw new Error(profileError.message);
  }

  let hospitalName = "";

  if (profile.hospital_id) {
    const { data: hospital, error: hospitalError } =
      await supabase
        .from("hospitals")
        .select("name")
        .eq("id", profile.hospital_id)
        .single();

    if (hospitalError) {
      throw new Error(hospitalError.message);
    }

    hospitalName = hospital?.name ?? "";
  }

  return {
    id: user.id,
    email: user.email ?? "",
    fullName: profile.full_name ?? "",
    role: profile.role as UserRole,
    hospitalId: profile.hospital_id,
    hospitalName,
  };
}