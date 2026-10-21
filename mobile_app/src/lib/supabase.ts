import "react-native-url-polyfill/auto";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.EXPO_PUBLIC_SUPABASE_KEY;

if (!supabaseUrl || !supabaseKey) {
  throw new Error(
    "EXPO_PUBLIC_SUPABASE_URL / EXPO_PUBLIC_SUPABASE_KEY are missing. " +
      "Copy mobile_app/.env.example to mobile_app/.env and restart Expo."
  );
}

// Expo's static web export pre-renders routes in Node, where there is no
// `window` and AsyncStorage cannot run. Only persist the session on a real
// device or browser.
const isServer = typeof window === "undefined";

export const supabase = createClient(
  supabaseUrl,
  supabaseKey,
  {
    auth: {
      storage: isServer ? undefined : AsyncStorage,
      autoRefreshToken: !isServer,
      persistSession: !isServer,
      detectSessionInUrl: false,
    },
  }
);
