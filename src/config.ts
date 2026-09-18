import Constants from 'expo-constants';

export const SUPABASE_URL =
  (Constants.expoConfig?.extra as any)?.supabaseUrl ?? 'https://mduemjbplprditrqolcp.supabase.co';

// Publishable key from the Swift app (SupabaseConfig.publishableKey).
// For production, move this to EAS env / expo-constants extra.
export const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_rvlRgP3T8YCdMHlgh6-cbA_vNS7hJOT';

export const APP_SCHEME = 'com.illumereader.ios';
export const AUTH_CALLBACK = `${APP_SCHEME}://auth-callback`;
