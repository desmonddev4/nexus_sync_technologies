import * as SecureStore from 'expo-secure-store'
import * as LocalAuthentication from 'expo-local-authentication'
import { Platform } from 'react-native'
const API_ORIGIN = process.env.EXPO_PUBLIC_API_URL || 'https://nexus-sync-backend.onrender.com'
const API_BASE = `${API_ORIGIN.replace(/\/$/, '')}/api/v1`
const TOKEN_KEY = 'nexus_sync_auth_token'
const BIOMETRIC_TOKEN_KEY = 'nexus_sync_biometric_token'
const BIOMETRIC_ENABLED_KEY = 'nexus_sync_biometric_enabled'
const BIOMETRIC_OPTIONS = { requireAuthentication: true, authenticationPrompt: 'Verify your identity to open Nexus Sync' }
// SecureStore is a native API. For browser-based development, keep the session
// token only for the lifetime of the tab; never persist biometric credentials on web.
async function readSecret(key: string, options?: SecureStore.SecureStoreOptions) {
 if (Platform.OS === 'web') return typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(key)
 return SecureStore.getItemAsync(key, options)
}
async function writeSecret(key: string, value: string, options?: SecureStore.SecureStoreOptions) {
 if (Platform.OS === 'web') { if (typeof sessionStorage !== 'undefined') sessionStorage.setItem(key, value); return }
 await SecureStore.setItemAsync(key, value, options)
}
async function removeSecret(key: string, options?: SecureStore.SecureStoreOptions) {
 if (Platform.OS === 'web') { if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem(key); return }
 await SecureStore.deleteItemAsync(key, options)
}
export type CurrentUser = { username: string; role: string | null; can_access_operations: boolean }
export type EmergencyContact = { id: string; name: string; relationship: string; phone_number: string; verification_status: string; priority_order: number }
export type ConsentRecord = { id: string; scope: string; status: string; policy_version: string; recorded_at: string }
export type Patient = { id: string; full_name: string; date_of_birth: string | null; phone_number: string; status: string; relevant_medical_notes: string; emergency_contacts: EmergencyContact[]; consent_records: ConsentRecord[]; access_scopes?: string[] }
export type Measurement = { id: string; measurement_type: string; value: string | number; unit: string; source: string; quality: string; measured_at: string }
export type Device = { id: string; device_identifier: string; device_type: string; status: string; battery_percent: number | null; last_seen_at: string | null; is_stale: boolean }
export type Incident = { id: string; incident_type: string; priority: string; trigger_source: string; status: string; created_at: string; location: { latitude: string; longitude: string; is_stale: boolean } | null }
export type AccessGrant = { id: string; username: string; scopes: string[]; granted_at: string }
export type IncidentNotification = { id: string; incident_id: string; contact_name: string | null; channel: string; status: string; retry_count: number; last_attempt_at: string | null; submitted_at: string | null; delivered_at: string | null; acknowledged_at: string | null; failure_code: string; created_at: string }
export type SosLocation = { latitude: number; longitude: number; accuracy_meters: number | null; recorded_at: string }
export type FaceResearchSample = { id: string; image_type: string; consent_version: string; review_status: string; created_at: string; expires_at: string }
export type FaceResearchState = { enrollment_enabled: boolean; consent_version: string; motion_test_enabled: boolean; motion_consent_version: string; retention_days: number; samples: FaceResearchSample[] }
export type FaceMotionChallenge = { challenge: string; steps: ('center' | 'left' | 'right')[]; motion_test_enabled: boolean; consent_version: string }
export class ApiError extends Error { constructor(message: string, readonly status: number) { super(message) } }
async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
 const multipart = typeof FormData !== 'undefined' && init.body instanceof FormData
 const response=await fetch(`${API_BASE}/${path.replace(/^\//,'')}`,{...init,headers:{Accept:'application/json',...(init.body&&!multipart?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Token ${token}`}:{ }),...init.headers}})
 if(!response.ok){let message=`Request failed (${response.status})`;try{const body=await response.json();message=Object.values(body).flat().map(String).join(' ')||message}catch{/* non-JSON response */}throw new ApiError(message,response.status)}
 if(response.status===204)return undefined as T
 return response.json() as Promise<T>
}
export const api={
 async signIn(username:string,password:string){const result=await request<{token:string}>('auth/token/',{method:'POST',body:JSON.stringify({username,password})});await writeSecret(TOKEN_KEY,result.token);await removeSecret(BIOMETRIC_TOKEN_KEY);await writeSecret(BIOMETRIC_ENABLED_KEY,'false');return result.token},
 async token(){const enabled=await readSecret(BIOMETRIC_ENABLED_KEY);if(enabled==='true'){try{return await readSecret(BIOMETRIC_TOKEN_KEY,BIOMETRIC_OPTIONS)}catch{return null}}return readSecret(TOKEN_KEY)},
 async biometricEnabled(){return Platform.OS !== 'web' && (await readSecret(BIOMETRIC_ENABLED_KEY))==='true'},
 async enableBiometrics(token:string){if(Platform.OS==='web')throw new Error('Biometric sign-in is available in the iOS and Android app, not in the web preview.');const available=await LocalAuthentication.hasHardwareAsync();const enrolled=await LocalAuthentication.isEnrolledAsync();if(!available||!enrolled)throw new Error('Enroll Face ID or a strong biometric in your device settings first.');const result=await LocalAuthentication.authenticateAsync({promptMessage:'Enable biometric sign-in for Nexus Sync',cancelLabel:'Cancel',disableDeviceFallback:true,biometricsSecurityLevel:'strong'});if(!result.success)throw new Error('Biometric verification was cancelled or did not succeed.');await writeSecret(BIOMETRIC_TOKEN_KEY,token,BIOMETRIC_OPTIONS);await removeSecret(TOKEN_KEY);await writeSecret(BIOMETRIC_ENABLED_KEY,'true')},
 async disableBiometrics(token:string){await writeSecret(TOKEN_KEY,token);await removeSecret(BIOMETRIC_TOKEN_KEY);await writeSecret(BIOMETRIC_ENABLED_KEY,'false')},
 async signOut(token?:string){let revoked=false;try{if(token){await request<void>('auth/token/revoke/',{method:'POST'},token);revoked=true}}catch{/* Remove local credentials even when offline; server token may remain active. */}finally{await removeSecret(TOKEN_KEY);await removeSecret(BIOMETRIC_TOKEN_KEY);await writeSecret(BIOMETRIC_ENABLED_KEY,'false')}return revoked},
 me(token:string){return request<CurrentUser>('auth/me/',{},token)}, patients(token:string){return request<Patient[]>('patients/',{},token)},
 measurements(token:string,patientId:string){return request<Measurement[]>(`patients/${patientId}/measurements/?limit=20`,{},token)}, devices(token:string,patientId:string){return request<Device[]>(`patients/${patientId}/devices/`,{},token)}, incidents(token:string){return request<Incident[]>('incidents/',{},token)},
 createSos(token:string,patientId:string,eventId:string,location?:SosLocation){return request<Incident>('incidents/sos/',{method:'POST',body:JSON.stringify({patient:patientId,event_id:eventId,trigger_source:'manual',...(location?{location}:{})})},token)},
 caretakers(token:string,patientId:string){return request<AccessGrant[]>(`patients/${patientId}/caretakers/`,{},token)}, grantCaretaker(token:string,patientId:string,username:string,scopes:string[]){return request<AccessGrant>(`patients/${patientId}/caretakers/`,{method:'POST',body:JSON.stringify({username,scopes})},token)}, revokeCaretaker(token:string,patientId:string,grantId:string){return request<void>(`patients/${patientId}/caretakers/${grantId}/`,{method:'DELETE'},token)},
 notifications(token:string,incidentId:string){return request<Omit<IncidentNotification,'incident_id'>[]>(`incidents/${incidentId}/notifications/`,{},token)}, acknowledgeNotification(token:string,incidentId:string,notificationId:string){return request<Omit<IncidentNotification,'incident_id'>>(`incidents/${incidentId}/notifications/${notificationId}/acknowledge/`,{method:'POST'},token)},
 faceResearchState(token:string){return request<FaceResearchState>('auth/biometrics/research-samples/',{},token)},
 faceMotionChallenge(token:string){return request<FaceMotionChallenge>('auth/face-liveness-challenge/',{},token)},
 async evaluateFaceMotion(token:string,challenge:string,frames:string[],consentVersion:string){const body=new FormData();body.append('challenge',challenge);body.append('consent','true');body.append('consent_version',consentVersion);frames.forEach((uri,index)=>body.append('frames',{uri,name:`face-motion-${index+1}.jpg`,type:'image/jpeg'} as unknown as Blob));return request<{motion_passed:boolean;identity_matched:boolean;used_for_sign_in:boolean;server_retained_images:boolean}>('auth/biometrics/motion-check/',{method:'POST',body},token)},
 async uploadFaceResearchSample(token:string,imageUri:string,consentVersion:string){const body=new FormData();body.append('image',{uri:imageUri,name:'face-capture.jpg',type:'image/jpeg'} as unknown as Blob);body.append('consent','true');body.append('consent_version',consentVersion);return request<{id:string;status:string;expires_at:string;used_for_sign_in:boolean}>('auth/biometrics/research-samples/',{method:'POST',body},token)},
 deleteFaceResearchSamples(token:string){return request<void>('auth/biometrics/research-samples/',{method:'DELETE'},token)},
}
