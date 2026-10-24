import { Tabs } from 'expo-router'
import { BlurView } from 'expo-blur'
import { LinearGradient } from 'expo-linear-gradient'
import { MaterialCommunityIcons } from '@expo/vector-icons'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { theme } from '../../theme'

const tabMeta: Record<string, { label: string; icon: keyof typeof MaterialCommunityIcons.glyphMap }> = {
  index: { label: 'Home', icon: 'view-dashboard-outline' },
  circle: { label: 'My circle', icon: 'account-multiple-outline' },
  activity: { label: 'Activity', icon: 'pulse' },
  sos: { label: 'SOS', icon: 'alert' },
  profile: { label: 'You', icon: 'account-circle-outline' },
}

type FloatingTabBarProps = {
  state: { index: number; routes: Array<{ key: string; name: string }> }
  navigateToTab: (routeKey: string) => void
}

function FloatingTabBar({ state, navigateToTab }: FloatingTabBarProps) {
  return (
    <View style={styles.barWrap}>
      <BlurView intensity={85} tint="dark" style={styles.bar}>
        {state.routes.map((route, index) => {
          const active = state.index === index
          const meta = tabMeta[route.name]
          const isSOS = route.name === 'sos'
          return (
            <Pressable
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              accessibilityLabel={isSOS ? 'SOS' : meta.label}
              key={route.key}
              onPress={() => {
                if (!active) navigateToTab(route.key)
              }}
              style={styles.tab}
            >
              {isSOS ? (
                <LinearGradient colors={[theme.colors.red, theme.colors.redDeep]} style={styles.sosIcon}>
                  <MaterialCommunityIcons name={meta.icon} size={22} color="#fff" />
                </LinearGradient>
              ) : (
                <MaterialCommunityIcons name={meta.icon} size={21} color={active ? theme.colors.cyan : theme.colors.dim} />
              )}
              <Text style={[styles.label, active && !isSOS && styles.activeLabel, isSOS && styles.sosLabel]}>{meta.label}</Text>
              {active && !isSOS && <View style={styles.activeDot} />}
            </Pressable>
          )
        })}
      </BlurView>
    </View>
  )
}

export default function TabLayout() {
  return (
    <Tabs
      tabBar={(props) => <FloatingTabBar {...props} />}
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: theme.colors.ink } }}
    >
      <Tabs.Screen name="index" options={{ title: 'Home' }} />
      <Tabs.Screen name="circle" options={{ title: 'My circle' }} />
      <Tabs.Screen name="activity" options={{ title: 'Activity' }} />
      <Tabs.Screen name="sos" options={{ title: 'SOS' }} />
      <Tabs.Screen name="profile" options={{ title: 'You' }} />
    </Tabs>
  )
}

const styles = StyleSheet.create({
  barWrap: { position: 'absolute', left: 15, right: 15, bottom: 12, borderRadius: 24, overflow: 'hidden', borderWidth: 1, borderColor: 'rgba(255,255,255,0.14)', shadowColor: '#000', shadowOpacity: 0.32, shadowRadius: 20, shadowOffset: { width: 0, height: 10 }, elevation: 20 },
  bar: { minHeight: 72, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', backgroundColor: 'rgba(14,21,50,0.76)' },
  tab: { flex: 1, height: 70, alignItems: 'center', justifyContent: 'center', gap: 4 },
  label: { color: theme.colors.dim, fontSize: 8, fontWeight: '700', letterSpacing: 0.15 },
  activeLabel: { color: theme.colors.cyan },
  sosLabel: { color: '#FF9AA8' },
  activeDot: { width: 3, height: 3, borderRadius: 2, backgroundColor: theme.colors.cyan, position: 'absolute', bottom: 4 },
  sosIcon: { width: 42, height: 42, borderRadius: 17, alignItems: 'center', justifyContent: 'center', marginTop: -15, borderWidth: 3, borderColor: '#151D43' },
})

