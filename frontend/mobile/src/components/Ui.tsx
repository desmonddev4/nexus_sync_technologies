import { type ReactNode } from 'react'
import { Image, ScrollView, StyleSheet, Text, View, type ViewStyle } from 'react-native'
import { BlurView } from 'expo-blur'
import { LinearGradient } from 'expo-linear-gradient'
import { SafeAreaView } from 'react-native-safe-area-context'
import { theme } from '../theme'

export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  const content = scroll
    ? <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>{children}</ScrollView>
    : <View style={styles.content}>{children}</View>
  return (
    <View style={styles.root}>
      <LinearGradient colors={['#131C43', theme.colors.ink, '#080D21']} style={StyleSheet.absoluteFill} />
      <View style={styles.glowA} />
      <View style={styles.glowB} />
      <SafeAreaView style={styles.safe} edges={['top', 'left', 'right']}>{content}</SafeAreaView>
    </View>
  )
}

export function GlassCard({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return (
    <View style={[styles.card, style]}>
      <BlurView intensity={24} tint="dark" style={StyleSheet.absoluteFill} />
      <View style={styles.cardWash} />
      {children}
    </View>
  )
}

export function BrandHeader({ subtitle }: { subtitle?: string }) {
  return (
    <View style={styles.header}>
      <View style={styles.brand}>
        <Image source={require('../../assets/nst-logo.png')} style={styles.logo} />
        <View><Text style={styles.brandName}>NEXUS SYNC</Text><Text style={styles.brandSub}>{subtitle ?? 'CARE, CONNECTED'}</Text></View>
      </View>
      <View style={styles.liveDot} />
    </View>
  )
}

export function SectionTitle({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: string }) {
  return (
    <View style={styles.sectionHead}>
      <View>{eyebrow && <Text style={styles.eyebrow}>{eyebrow}</Text>}<Text style={styles.sectionTitle}>{title}</Text></View>
      {action && <Text style={styles.sectionAction}>{action}</Text>}
    </View>
  )
}

export function Tag({ children, tone = 'cyan' }: { children: ReactNode; tone?: 'cyan' | 'green' | 'amber' | 'red' }) {
  const tint = tone === 'green' ? theme.colors.mint : tone === 'amber' ? theme.colors.amber : tone === 'red' ? theme.colors.coral : theme.colors.cyan
  return <View style={[styles.tag, { borderColor: `${tint}55`, backgroundColor: `${tint}18` }]}><View style={[styles.tagDot, { backgroundColor: tint }]} /><Text style={[styles.tagText, { color: tint }]}>{children}</Text></View>
}

export function IconTile({ children, color = theme.colors.cyan }: { children: ReactNode; color?: string }) {
  return <LinearGradient colors={[`${color}38`, `${color}12`]} style={styles.iconTile}><View style={[styles.iconTileInner, { borderColor: `${color}38` }]}>{children}</View></LinearGradient>
}

export function Divider() { return <View style={styles.divider} /> }

export const typography = StyleSheet.create({
  heading: { color: theme.colors.white, fontSize: 28, lineHeight: 34, fontWeight: '700', letterSpacing: -0.8 },
  title: { color: theme.colors.white, fontSize: 17, fontWeight: '700', letterSpacing: -0.25 },
  body: { color: theme.colors.muted, fontSize: 13, lineHeight: 19 },
  small: { color: theme.colors.dim, fontSize: 11, lineHeight: 16 },
})

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.ink },
  safe: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 122, gap: 20 },
  glowA: { position: 'absolute', top: -100, right: -115, width: 265, height: 265, borderRadius: 140, backgroundColor: 'rgba(36,87,245,0.14)' },
  glowB: { position: 'absolute', top: 285, left: -145, width: 240, height: 240, borderRadius: 130, backgroundColor: 'rgba(138,68,240,0.10)' },
  card: { overflow: 'hidden', borderRadius: theme.radius.card, borderWidth: 1, borderColor: theme.colors.line, backgroundColor: theme.colors.inkCard, padding: 18 },
  cardWash: { ...StyleSheet.absoluteFill, backgroundColor: 'rgba(255,255,255,0.018)' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logo: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#fff' },
  brandName: { color: theme.colors.white, fontSize: 12, fontWeight: '800', letterSpacing: 1.55 },
  brandSub: { color: theme.colors.dim, fontSize: 8, fontWeight: '700', letterSpacing: 1.2, marginTop: 3 },
  liveDot: { width: 8, height: 8, borderRadius: 5, backgroundColor: theme.colors.mint, shadowColor: theme.colors.mint, shadowOpacity: 0.9, shadowRadius: 8 },
  sectionHead: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 10 },
  eyebrow: { color: theme.colors.cyan, fontSize: 9, fontWeight: '800', letterSpacing: 1.6, marginBottom: 6 },
  sectionTitle: { color: theme.colors.white, fontSize: 20, fontWeight: '700', letterSpacing: -0.4 },
  sectionAction: { color: theme.colors.cyan, fontSize: 11, fontWeight: '700', paddingBottom: 2 },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', borderWidth: 1, borderRadius: 99, paddingHorizontal: 10, paddingVertical: 6 },
  tagDot: { width: 5, height: 5, borderRadius: 3 },
  tagText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.7, textTransform: 'uppercase' },
  iconTile: { width: 42, height: 42, borderRadius: 15, padding: 1 },
  iconTileInner: { flex: 1, alignItems: 'center', justifyContent: 'center', borderRadius: 14, borderWidth: 1, backgroundColor: 'rgba(11,16,41,0.35)' },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: theme.colors.line },
})
