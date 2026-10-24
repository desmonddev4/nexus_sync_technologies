import { useState } from 'react'
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { BrandHeader, GlassCard, Screen } from '../components/Ui'
import { useAppState } from '../state/AppState'
import { theme } from '../theme'

export function SignInScreen() {
  const { signIn, loading, error } = useAppState()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  return <Screen><KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.wrap}>
    <BrandHeader subtitle="SECURE PATIENT ACCESS" />
    <View style={styles.intro}><Text style={styles.title}>Welcome to Nexus Sync</Text><Text style={styles.body}>Sign in with the account provided by your care team to view your live patient record.</Text></View>
    <GlassCard style={styles.card}><Text style={styles.label}>USERNAME</Text><TextInput value={username} onChangeText={setUsername} autoCapitalize="none" autoCorrect={false} style={styles.input} placeholder="Your username" placeholderTextColor={theme.colors.dim} accessibilityLabel="Username" /><Text style={styles.label}>PASSWORD</Text><TextInput value={password} onChangeText={setPassword} secureTextEntry style={styles.input} placeholder="Your password" placeholderTextColor={theme.colors.dim} accessibilityLabel="Password" onSubmitEditing={() => void submit()} />
      {(localError || error) && <Text accessibilityRole="alert" style={styles.error}>{localError || error}</Text>}
      <Pressable disabled={loading} onPress={() => void submit()} style={styles.button}><Text style={styles.buttonText}>{loading ? 'Signing in…' : 'Sign in securely'}</Text></Pressable>
      <Text style={styles.hint}>Biometric sign-in can be enabled after your account is connected.</Text></GlassCard>
  </KeyboardAvoidingView></Screen>
  async function submit() { setLocalError(null); if (!username.trim() || !password) { setLocalError('Enter your username and password.'); return } try { await signIn(username.trim(), password) } catch (e) { setLocalError(e instanceof Error ? e.message : 'Sign-in failed.') } }
}
const styles = StyleSheet.create({ wrap: { flex: 1, justifyContent: 'center', gap: 24 }, intro: { gap: 8 }, title: { color: theme.colors.white, fontSize: 26, fontWeight: '800' }, body: { color: theme.colors.muted, fontSize: 13, lineHeight: 20 }, card: { gap: 11 }, label: { color: theme.colors.cyan, fontSize: 9, fontWeight: '800', letterSpacing: 1.2, marginTop: 5 }, input: { borderWidth: 1, borderColor: theme.colors.line, borderRadius: 13, padding: 14, color: theme.colors.white, backgroundColor: 'rgba(255,255,255,0.04)' }, error: { color: '#FF8C9C', fontSize: 12, lineHeight: 18 }, button: { backgroundColor: theme.colors.blue, borderRadius: 14, padding: 15, alignItems: 'center', marginTop: 4 }, buttonText: { color: '#fff', fontSize: 13, fontWeight: '800' }, hint: { color: theme.colors.dim, fontSize: 10, lineHeight: 16, textAlign: 'center' } })
