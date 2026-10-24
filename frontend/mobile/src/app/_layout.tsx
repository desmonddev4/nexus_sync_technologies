import { Stack } from 'expo-router'
import { StatusBar } from 'expo-status-bar'
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { SignInScreen } from '../components/SignInScreen'
import { RoleProvider, useAppState } from '../state/AppState'
import { theme } from '../theme'
function AppGate(){const{token,loading,error,refresh,signOut}=useAppState();if(!token)return <SignInScreen/>;if(loading)return <View style={styles.center}><ActivityIndicator color={theme.colors.cyan}/></View>;if(error)return <View style={styles.center}><Text style={styles.error}>{error}</Text><Pressable onPress={()=>void refresh()} style={styles.button}><Text style={styles.buttonText}>Try again</Text></Pressable><Pressable onPress={()=>void signOut()}><Text style={styles.link}>Sign out</Text></Pressable></View>;return <Stack screenOptions={{headerShown:false,animation:'fade'}}/>}
const styles=StyleSheet.create({center:{flex:1,backgroundColor:theme.colors.ink,alignItems:'center',justifyContent:'center',padding:28,gap:15},error:{color:'#FF8C9C',fontSize:14,lineHeight:22,textAlign:'center'},button:{paddingHorizontal:24,paddingVertical:13,borderRadius:13,backgroundColor:theme.colors.blue},buttonText:{color:'#fff',fontWeight:'800'},link:{color:theme.colors.cyan,fontWeight:'700'}})
export default function RootLayout(){return <SafeAreaProvider><RoleProvider><StatusBar style="light"/><AppGate/></RoleProvider></SafeAreaProvider>}
