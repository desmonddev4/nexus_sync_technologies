import { MaterialCommunityIcons } from '@expo/vector-icons'
import { StyleSheet, Text, View } from 'react-native'
import { BrandHeader, GlassCard, IconTile, Screen, SectionTitle, Tag, typography } from '../../components/Ui'
import { useAppState } from '../../state/AppState'
import { theme } from '../../theme'
const labels: Record<string, string> = { heart_rate: 'Heart rate', spo2: 'Blood oxygen', body_temperature: 'Body temperature', skin_temperature: 'Skin temperature', systolic_blood_pressure: 'Systolic pressure', diastolic_blood_pressure: 'Diastolic pressure' }
export default function HomeScreen() {
 const { user, patient, measurements, devices, accessScopes, loading, error, refresh } = useAppState()
 return <Screen><BrandHeader subtitle="YOUR LIVE CARE RECORD" /><View style={styles.greeting}><Text style={styles.hello}>Hello, {patient?.full_name || user?.username}</Text><Text style={typography.body}>Your information is loaded securely from your patient record.</Text></View>
 {error && <GlassCard><Text style={styles.error}>{error}</Text></GlassCard>}
 {!patient && !loading && !error && <GlassCard><Text style={styles.title}>No patient record linked</Text><Text style={typography.body}>Ask your care team to link your account to a patient record.</Text></GlassCard>}
 {patient && <><GlassCard style={styles.patient}><Tag tone="green">{patient.status}</Tag><Text style={styles.title}>{patient.full_name}</Text><Text style={typography.body}>{patient.phone_number || 'No phone number on record'}</Text></GlassCard>
 <SectionTitle eyebrow="LATEST READINGS" title="Wellness" action={accessScopes.includes("health")?`${measurements.length} records`:"Not shared"} />
 {measurements.length ? <View style={styles.metrics}>{measurements.slice(0, 4).map((item) => <GlassCard key={item.id} style={styles.metric}><IconTile color={theme.colors.cyan}><MaterialCommunityIcons name="heart-pulse" size={18} color={theme.colors.cyan} /></IconTile><Text style={styles.value}>{item.value} <Text style={styles.unit}>{item.unit}</Text></Text><Text style={styles.label}>{labels[item.measurement_type] || item.measurement_type}</Text><Text style={styles.note}>{new Date(item.measured_at).toLocaleString()} · {item.quality}</Text></GlassCard>)}</View> : <Empty text={accessScopes.includes("health")?"No measurements are recorded for this patient yet.":"Health readings are not included in your sharing permissions."} />}
 <SectionTitle eyebrow="CONNECTED DEVICES" title="Your devices" action={accessScopes.includes("devices")?`${devices.length} devices`:"Not shared"} />
 {devices.length ? devices.map((d) => <GlassCard key={d.id} style={styles.row}><MaterialCommunityIcons name="watch-variant" size={22} color={theme.colors.cyan} /><View style={{flex:1}}><Text style={styles.label}>{d.device_identifier}</Text><Text style={styles.note}>{d.device_type} · {d.status}{d.battery_percent == null ? '' : ` · ${d.battery_percent}% battery`}</Text></View><Tag tone={d.is_stale ? 'amber' : 'green'}>{d.is_stale ? 'Stale' : 'Live'}</Tag></GlassCard>) : <Empty text={accessScopes.includes("devices")?"No devices are connected to this patient record.":"Device details are not included in your sharing permissions."} />}
 <GlassCard style={styles.row}><View style={{flex:1}}><Text style={styles.label}>Refresh patient data</Text><Text style={styles.note}>Fetch the latest data from the server</Text></View><Text onPress={() => void refresh()} style={styles.refresh}>Refresh</Text></GlassCard>
 <Text style={styles.disclaimer}>Measurements are shown as recorded and are not a diagnosis. For urgent medical help, contact local emergency services.</Text></>}
 {loading && <Text style={styles.note}>Loading live data…</Text>}</Screen>
}
function Empty({ text }: { text: string }) { return <GlassCard><Text style={styles.note}>{text}</Text></GlassCard> }
const styles = StyleSheet.create({ greeting:{gap:5},hello:{color:theme.colors.white,fontSize:22,fontWeight:'700'},patient:{gap:8},title:{color:theme.colors.white,fontSize:18,fontWeight:'700'},metrics:{flexDirection:'row',flexWrap:'wrap',gap:10},metric:{width:'48%',flexGrow:1,gap:7,padding:13},value:{color:theme.colors.white,fontSize:25,fontWeight:'800'},unit:{color:theme.colors.muted,fontSize:12},label:{color:theme.colors.white,fontSize:11,fontWeight:'700'},note:{color:theme.colors.dim,fontSize:9,lineHeight:15},row:{flexDirection:'row',alignItems:'center',gap:12,padding:14},refresh:{color:theme.colors.cyan,fontWeight:'700'},disclaimer:{color:theme.colors.dim,fontSize:9,lineHeight:14,textAlign:'center'},error:{color:'#FF8C9C',lineHeight:18}})


