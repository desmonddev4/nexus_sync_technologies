import { MaterialCommunityIcons } from '@expo/vector-icons'
import { CameraView, useCameraPermissions } from 'expo-camera'
import { useEffect, useRef, useState } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native'
import { api, type FaceMotionChallenge, type FaceResearchState } from '../api/client'
import { useAppState } from '../state/AppState'
import { theme } from '../theme'
import { GlassCard, SectionTitle } from './Ui'

export function FaceMotionResearchCheck() {
  const { token } = useAppState()
  const camera = useRef<CameraView>(null)
  const [permission, requestPermission] = useCameraPermissions()
  const [state, setState] = useState<FaceResearchState | null>(null)
  const [challenge, setChallenge] = useState<FaceMotionChallenge | null>(null)
  const [frames, setFrames] = useState<string[]>([])
  const [consent, setConsent] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    if (token) void api.faceResearchState(token).then((value) => { if (active) setState(value) }).catch((e) => { if (active) setError(e instanceof Error ? e.message : 'Could not load the motion-check status.') })
    return () => { active = false }
  }, [token])

  const start = async () => {
    if (!token || !consent || !state?.motion_test_enabled || busy) return
    setBusy(true); setError(null); setResult(null)
    try {
      if (!permission?.granted) {
        const permissionResult = await requestPermission()
        if (!permissionResult.granted) throw new Error('Camera permission is needed only to run this optional motion test.')
      }
      const next = await api.faceMotionChallenge(token)
      if (!next.motion_test_enabled || !next.consent_version) throw new Error('The development motion test is unavailable.')
      setChallenge(next); setFrames([]); setCameraOpen(true)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not start the motion test.') }
    finally { setBusy(false) }
  }

  const capture = async () => {
    if (!camera.current || !token || !challenge || busy) return
    setBusy(true); setError(null)
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.5 })
      if (!photo?.uri) throw new Error('The camera did not return a frame. Try again.')
      const nextFrames = [...frames, photo.uri]
      setFrames(nextFrames)
      if (nextFrames.length === challenge.steps.length) {
        setCameraOpen(false)
        const response = await api.evaluateFaceMotion(token, challenge.challenge, nextFrames, challenge.consent_version)
        setResult(response.motion_passed
          ? 'Motion check passed. No identity match was run; sign-in and patient access were unchanged.'
          : 'Motion check did not pass. Sign-in and patient access are unchanged.')
        setChallenge(null); setFrames([])
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not complete the motion check.') }
    finally { setBusy(false) }
  }

  if (!state?.motion_test_enabled) return null
  const step = challenge?.steps[frames.length]

  return <View style={styles.section}>
    <SectionTitle eyebrow="OPTIONAL DEVELOPMENT TEST" title="Face motion check" />
    <GlassCard style={styles.card}>
      <Text style={styles.body}>This tests only the camera motion check. It does not identify you, compare your face to an enrollment, unlock the app, or change your account access. The server processes the three frames in memory and does not retain them.</Text>
      <Pressable onPress={() => setConsent((value) => !value)} accessibilityRole="checkbox" accessibilityState={{ checked: consent }} style={styles.consent}>
        <MaterialCommunityIcons name={consent ? 'checkbox-marked' : 'checkbox-blank-outline'} size={21} color={consent ? theme.colors.cyan : theme.colors.dim} />
        <Text style={styles.body}>I agree to send three temporary camera frames for this motion test under notice {state.motion_consent_version}.</Text>
      </Pressable>
      {cameraOpen && challenge && step ? <View style={styles.camera}>
        <CameraView ref={camera} style={StyleSheet.absoluteFill} facing="front" />
        <View style={styles.overlay} pointerEvents="none">
          <Text style={styles.prompt}>{step === 'center' ? 'Face the camera' : `Turn your head ${step}`}</Text>
          <Text style={styles.counter}>Step {frames.length + 1} of {challenge.steps.length}</Text>
        </View>
        <Pressable onPress={() => void capture()} disabled={busy} style={styles.capture} accessibilityRole="button" accessibilityLabel={`Capture ${step} frame`}>
          {busy ? <ActivityIndicator color="#fff" /> : <MaterialCommunityIcons name="camera" size={23} color="#fff" />}
        </Pressable>
        <Pressable onPress={() => { setCameraOpen(false); setChallenge(null); setFrames([]) }} style={styles.cancel}><Text style={styles.cancelText}>Cancel</Text></Pressable>
      </View> : <Pressable onPress={() => void start()} disabled={!consent || busy} style={[styles.button, (!consent || busy) && styles.disabled]}>
        {busy ? <ActivityIndicator color="#fff" /> : <MaterialCommunityIcons name="face-recognition" size={17} color="#fff" />}
        <Text style={styles.buttonText}>Start motion check</Text>
      </Pressable>}
      {result && <Text accessibilityRole="status" style={styles.result}>{result}</Text>}
      {error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
    </GlassCard>
  </View>
}

const styles = StyleSheet.create({
  section: { gap: 11 }, card: { gap: 13 }, body: { color: theme.colors.muted, fontSize: 10, lineHeight: 16, flex: 1 },
  consent: { flexDirection: 'row', alignItems: 'flex-start', gap: 9 },
  button: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 13, borderRadius: 13, backgroundColor: theme.colors.blue },
  disabled: { opacity: 0.45 }, buttonText: { color: '#fff', fontWeight: '800', fontSize: 11 },
  camera: { height: 340, borderRadius: 18, overflow: 'hidden', backgroundColor: '#070B19' },
  overlay: { ...StyleSheet.absoluteFill, alignItems: 'center', justifyContent: 'center', gap: 8 },
  prompt: { color: '#fff', backgroundColor: 'rgba(0,0,0,0.6)', paddingHorizontal: 13, paddingVertical: 8, borderRadius: 99, fontSize: 12, fontWeight: '700' },
  counter: { color: '#fff', backgroundColor: 'rgba(0,0,0,0.5)', paddingHorizontal: 9, paddingVertical: 5, borderRadius: 99, fontSize: 9 },
  capture: { position: 'absolute', bottom: 15, alignSelf: 'center', width: 58, height: 58, borderRadius: 29, backgroundColor: theme.colors.blue, alignItems: 'center', justifyContent: 'center', borderWidth: 3, borderColor: '#fff' },
  cancel: { position: 'absolute', right: 13, top: 13, backgroundColor: 'rgba(0,0,0,0.6)', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99 }, cancelText: { color: '#fff', fontSize: 10, fontWeight: '700' },
  result: { color: theme.colors.mint, fontSize: 10, lineHeight: 16 }, error: { color: '#FF8C9C', fontSize: 10, lineHeight: 15 },
})
