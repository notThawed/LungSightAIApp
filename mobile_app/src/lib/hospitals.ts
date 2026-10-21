import { supabase } from "./supabase";

export type Hospital = {
  hospital_id: string;
  hospital_name: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
};

/** Active partner hospitals, alphabetically. */
export async function fetchActiveHospitals(): Promise<Hospital[]> {
  const { data, error } = await supabase
    .from("hospitals")
    .select("hospital_id, hospital_name, address, latitude, longitude")
    .eq("is_active", true)
    .order("hospital_name", { ascending: true });

  if (error) {
    throw new Error(error.message);
  }

  return (data ?? []) as Hospital[];
}

export function hasValidCoordinates(hospital: Hospital): boolean {
  return (
    hospital.latitude !== null &&
    hospital.longitude !== null &&
    Number.isFinite(Number(hospital.latitude)) &&
    Number.isFinite(Number(hospital.longitude)) &&
    Math.abs(Number(hospital.latitude)) <= 90 &&
    Math.abs(Number(hospital.longitude)) <= 180
  );
}
