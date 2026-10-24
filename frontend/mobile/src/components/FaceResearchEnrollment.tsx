import { MaterialCommunityIcons } from '@expo/vector-icons'
import { CameraView, useCameraPermissions } from 'expo-camera'
import { useEffect, useRef, useState } from 'react'
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from 'react-native'
import { api, type FaceResearchState } from '../api/client'
import { GlassCard, SectionTitle } from './Ui'
import { useAppState } from '../state/AppState'
import { theme } from '../theme'

export function FaceResearchEnrollment() {
  const { token } = useAppState()
  const [permission, requestPermission] = useCameraPermissions()
  const camera = useRef<CameraView>(null)
  const [state, setState] = useState<FaceResearchState | null>(null)
  const [consent, setConsent] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    if (!token) return
    try { setState(await api.faceResearchState(token)); setError(null) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not load research enrollment.') }
  }
  useEffect(() => { void refresh() }, [token])

  const openCamera = async () => {
    if (!consent || !state?.enrollment_enabled) return
    setError(null)
    if (!permission?.granted) {
      const result = await requestPermission()
      if (!result.granted) { setError('Camera permission is required only to take a research capture.'); return }
    }
    setCameraOpen(true)
  }

  const capture = async () => {
    if (!camera.current || !token || !state?.consent_version) return
    setBusy(true); setError(null)
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.78 })
      if (!photo?.uri) throw new Error('The camera did not return an image. Try again.')
      const result = await api.uploadFaceResearchSample(token, photo.uri, state.consent_version)
      setCameraOpen(false); setConsent(false); await refresh()
      Alert.alert('Research capture saved', `This image is encrypted and will expire in ${state.retention_days} days. It does not verify your identity or unlock your account.`)
      if (result.used_for_sign_in) throw new Error('Unexpected authentication state.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save the research capture.') }
    finally { setBusy(false) }
  }

  const removeSamples = () => Alert.alert('Delete research captures?', 'This permanently deletes your face research samples. It does not affect your account or patient access.', [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete captures', style: 'destructive', onPress: () => { void (async () => { if (!token) return; setBusy(true); try { await api.deleteFaceResearchSamples(token); setCameraOpen(false); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Could not delete captures.') } finally { setBusy(false) } })() } },
  ])

  return <View style={styles.section}>
    <SectionTitle eyebrow="OPTIONAL RESEARCH" title="Face verification research" />
    <GlassCard style={styles.card}>
      <View style={styles.heading}><View style={styles.icon}><MaterialCommunityIcons name="face-recognition" size={22} color={theme.colors.cyan} /></View><View style={{ flex: 1, gap: 4 }}><Text style={styles.title}>Help us evaluate face verification</Text><Text style={styles.body}>Voluntary research enrollment for your own account.</Text></View></View>
      <Text style={styles.notice}>This captures a photo for research only. It does not check liveness, compare your identity, train a model automatically, or change sign-in. Your capture is encrypted, kept for at most {state?.retention_days ?? 30} days, and can be deleted here. Password access stays available.</Text>
      {state?.enrollment_enabled ? <>
        {state.samples.length > 0 && <View style={styles.sampleInfo}><MaterialCommunityIcons name="image-lock-outline" size={17} color={theme.colors.mint} /><Text style={styles.sampleText}>{state.samples.length} encrypted capture{state.samples.length === 1 ? '' : 's'} · all unreviewed · none used to sign in</Text></View>}
        {cameraOpen ? <View style={styles.cameraFrame}><CameraView ref={camera} style={StyleSheet.absoluteFill} facing="front" /><View style={styles.cameraOverlay}><Text style={styles.cameraHint}>Center your face in the frame</Text></View><Pressable onPress={() => void capture()} disabled={busy} style={styles.captureButton}>{busy ? <ActivityIndicator color="#fff" /> : <MaterialCommunityIcons name="camera" size={23} color="#fff" />}</Pressable><Pressable onPress={() => setCameraOpen(false)} style={styles.cancelCamera}><Text style={styles.cancelText}>Cancel</Text></Pressable></View> : <>
          <Pressable onPress={() => setConsent(!consent)} accessibilityRole="checkbox" accessibilityState={{ checked: consent }} style={styles.consentRow}><MaterialCommunityIcons name={consent ? 'checkbox-marked' : 'checkbox-blank-outline'} size={21} color={consent ? theme.colors.cyan : theme.colors.dim} /><Text style={styles.body}>I agree to submit my face photo for this limited, voluntary research study under notice {state.consent_version}. I understand I can delete my samples and continue using my password.</Text></Pressable>
          <Pressable onPress={() => void openCamera()} disabled={!consent || busy} style={[styles.button, (!consent || busy) && styles.buttonDisabled]}><MaterialCommunityIcons name="camera-plus-outline" size={17} color="#fff" /><Text style={styles.buttonText}>Take research photo</Text></Pressable>
        </>}
        {state.samples.length > 0 && !cameraOpen && <Pressable onPress={removeSamples} disabled={busy} style={styles.deleteButton}><Text style={styles.deleteText}>Delete my research captures</Text></Pressable>}
      </> : <Text style={styles.body}>Research enrollment is currently unavailable. Your sign-in and account access are unaffected.</Text>}
      {error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
      <Text style={styles.foot}>Only sample metadata is visible here; images cannot be downloaded through the app. Captures are not biometric sign-in credentials.</Text>
    </GlassCard>
  </View>
}

const styles = StyleSheet.create({ section: { gap: 11 }, card: { gap: 13 }, heading: { flexDirection: 'row', alignItems: 'center', gap: 11 }, icon: { width: 43, height: 43, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(63,216,255,0.12)' }, title: { color: theme.colors.white, fontSize: 13, fontWeight: '700' }, body: { color: theme.colors.muted, fontSize: 10, lineHeight: 16, flex: 1 }, notice: { color: theme.colors.amber, fontSize: 10, lineHeight: 16, padding: 11, borderRadius: 13, backgroundColor: 'rgba(255,202,120,0.08)', borderWidth: 1, borderColor: 'rgba(255,202,120,0.2)' }, consentRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 9 }, button: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 13, borderRadius: 13, backgroundColor: theme.colors.blue }, buttonDisabled: { opacity: 0.45 }, buttonText: { color: '#fff', fontWeight: '800', fontSize: 11 }, cameraFrame: { height: 340, borderRadius: 18, overflow: 'hidden', backgroundColor: '#070B19' }, cameraOverlay: { ...StyleSheet.absoluteFill, alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }, cameraHint: { color: '#fff', backgroundColor: 'rgba(0,0,0,0.55)', paddingHorizontal: 12, paddingVertical: 7, borderRadius: 99, fontSize: 10 }, captureButton: { position: 'absolute', bottom: 15, alignSelf: 'center', width: 58, height: 58, borderRadius: 29, backgroundColor: theme.colors.blue, alignItems: 'center', justifyContent: 'center', borderWidth: 3, borderColor: '#fff' }, cancelCamera: { position: 'absolute', right: 13, top: 13, backgroundColor: 'rgba(0,0,0,0.6)', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99 }, cancelText: { color: '#fff', fontSize: 10, fontWeight: '700' }, sampleInfo: { flexDirection: 'row', gap: 8, alignItems: 'center', padding: 10, borderRadius: 12, backgroundColor: 'rgba(83,225,182,0.08)' }, sampleText: { color: theme.colors.mint, fontSize: 9, flex: 1 }, deleteButton: { alignSelf: 'center', padding: 8 }, deleteText: { color: theme.colors.coral, fontSize: 10, fontWeight: '700' }, foot: { color: theme.colors.dim, fontSize: 9, lineHeight: 14 }, error: { color: '#FF8C9C', fontSize: 10, lineHeight: 15 } })
