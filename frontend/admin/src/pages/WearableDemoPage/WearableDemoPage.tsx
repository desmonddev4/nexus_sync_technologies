import { useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, MouseEvent } from 'react'
import {
  Activity,
  BatteryCharging,
  Bell,
  Bluetooth,
  CloudUpload,
  Droplets,
  HeartPulse,
  LocateFixed,
  MapPin,
  RotateCcw,
  Siren,
  Watch,
} from 'lucide-react'
import { getPatientDevices, getPatientLocations, getPatientMeasurements, getPatients } from '../../api/operations'
import './WearableDemoPage.css'

/* ------------------------------------------------------------------ */
/* Types & helpers                                                     */
/* ------------------------------------------------------------------ */

type SosState = 'Standby' | 'Queued' | 'Triggered'
type Tone = 'info' | 'warn' | 'success' | 'danger'

interface EventItem {
  id: number
  time: string
  label: string
  detail: string
  tone: Tone
}

const BASE_LAT = 5.6508
const BASE_LNG = -0.1869
const SPREAD = 0.0025

const formatTime = (date: Date) =>
  date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))
const nudge = (value: number, step: number, min: number, max: number) =>
  clamp(value + (Math.random() > 0.5 ? step : -step), min, max)
const toNumber = (value: string | number | null | undefined, fallback: number) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const sosCopy: Record<SosState, { title: string; text: string }> = {
  Standby: {
    title: 'No alert active',
    text: 'The strap is watching. Press SOS to send a simulated alert to the control room.',
  },
  Queued: {
    title: 'Alert queued',
    text: 'The alert is waiting to be picked up by the emergency workflow.',
  },
  Triggered: {
    title: 'SOS is active',
    text: 'The control room can see this alert and the strap’s last known location.',
  },
}

/* ------------------------------------------------------------------ */
/* Band illustration — a woven nylon loop with a slim tracker pod      */
/* ------------------------------------------------------------------ */

function BandIllustration() {
  return (
    <svg className="wd-band__svg" viewBox="0 0 500 560" role="img" aria-label="Black woven wristband with a slim tracker pod">
      <defs>
        <pattern id="wdWeaveFront" width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="#111116" />
          <rect width="2.3" height="6" fill="#2c2c35" />
        </pattern>
        <pattern id="wdWeaveBack" width="7" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(90)">
          <rect width="7" height="8" fill="#101015" />
          <path d="M0 4 Q1.75 1 3.5 4 T7 4" fill="none" stroke="#3a3a44" strokeWidth="1.8" />
        </pattern>
        <pattern id="wdWeavePatch" width="5" height="5" patternUnits="userSpaceOnUse">
          <rect width="5" height="5" fill="#16161b" />
          <rect width="5" height="1.8" fill="#2a2a32" />
        </pattern>
        <linearGradient id="wdShadeBack" gradientUnits="userSpaceOnUse" x1="216" y1="0" x2="500" y2="0">
          <stop offset="0" stopColor="#000" stopOpacity="0.15" />
          <stop offset="0.45" stopColor="#000" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity="0.5" />
        </linearGradient>
        <linearGradient id="wdShadeFront" gradientUnits="userSpaceOnUse" x1="14" y1="0" x2="216" y2="0">
          <stop offset="0" stopColor="#000" stopOpacity="0.35" />
          <stop offset="0.35" stopColor="#fff" stopOpacity="0.03" />
          <stop offset="1" stopColor="#000" stopOpacity="0.3" />
        </linearGradient>
        <linearGradient id="wdPodBody" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#5a5a68" />
          <stop offset="0.35" stopColor="#34343e" />
          <stop offset="1" stopColor="#15151b" />
        </linearGradient>
        <linearGradient id="wdBuckleBody" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3a3a44" />
          <stop offset="1" stopColor="#0d0d11" />
        </linearGradient>
        <clipPath id="wdFrontClip">
          <path d="M34 98 L206 26 Q216 22 216 34 L216 512 Q216 524 205 519 L26 432 Q14 426 14 413 L14 112 Q14 102 24 101 Z" />
        </clipPath>
        <filter id="wdLedGlow" x="-200%" y="-50%" width="500%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="wdSoft" x="-20%" y="-200%" width="140%" height="500%">
          <feGaussianBlur stdDeviation="8" />
        </filter>
      </defs>

      <ellipse cx="260" cy="548" rx="190" ry="9" fill="#000" opacity="0.45" filter="url(#wdSoft)" />

      {/* Loop: back of the strap with the opening cut out */}
      <path
        fillRule="evenodd"
        fill="url(#wdWeaveBack)"
        d="M216 34 C290 8 380 14 432 46 C480 80 500 200 492 310 C486 420 400 520 300 548 C270 556 240 540 216 512 Z M226 284 a64 214 0 1 0 128 0 a64 214 0 1 0 -128 0 Z"
      />
      <path
        fillRule="evenodd"
        fill="url(#wdShadeBack)"
        d="M216 34 C290 8 380 14 432 46 C480 80 500 200 492 310 C486 420 400 520 300 548 C270 556 240 540 216 512 Z M226 284 a64 214 0 1 0 128 0 a64 214 0 1 0 -128 0 Z"
      />
      <path
        fill="none"
        stroke="#06060a"
        strokeWidth="3"
        d="M216 34 C290 8 380 14 432 46 C480 80 500 200 492 310 C486 420 400 520 300 548 C270 556 240 540 216 512"
      />
      <path fill="none" stroke="#2b2b34" strokeWidth="2" d="M226 284 a64 214 0 1 0 128 0 a64 214 0 1 0 -128 0 Z" />
      <path fill="none" stroke="#fff" strokeOpacity="0.07" strokeWidth="1.5" d="M222 40 C292 16 378 22 428 52" />

      {/* Buckle */}
      <g transform="translate(404 54) rotate(28)">
        <rect x="-78" y="-11" width="52" height="22" rx="4" fill="#1a1a21" stroke="#050507" strokeWidth="2" />
        <rect x="-36" y="-15" width="72" height="30" rx="11" fill="url(#wdBuckleBody)" stroke="#050507" strokeWidth="2" />
        <rect x="-23" y="-6" width="46" height="12" rx="5" fill="#050507" />
        <path d="M-28 -11 H26" stroke="#fff" strokeOpacity="0.18" strokeWidth="1.5" strokeLinecap="round" />
      </g>

      {/* Front strap panel */}
      <g clipPath="url(#wdFrontClip)">
        <rect width="230" height="560" fill="url(#wdWeaveFront)" />
        <polygon points="0 372 230 462 230 560 0 560" fill="url(#wdWeavePatch)" />
        <rect width="230" height="560" fill="url(#wdShadeFront)" />
      </g>
      <path
        fill="none"
        stroke="#050507"
        strokeWidth="3"
        d="M34 98 L206 26 Q216 22 216 34 L216 512 Q216 524 205 519 L26 432 Q14 426 14 413 L14 112 Q14 102 24 101 Z"
      />
      <path fill="none" stroke="#fff" strokeOpacity="0.1" strokeWidth="1.5" d="M40 99 L203 31" />

      {/* Tracker pod */}
      <g transform="translate(200 250) rotate(5.5)">
        <rect x="-24" y="-172" width="50" height="344" rx="22" fill="#050507" opacity="0.5" transform="translate(5 4)" />
        <rect x="-26" y="-172" width="52" height="344" rx="22" fill="url(#wdPodBody)" stroke="#07070a" strokeWidth="2" />
        <rect x="-21" y="-166" width="3" height="332" rx="1.5" fill="#fff" opacity="0.16" />
        {/* Status light bar: colour follows the SOS state */}
        <rect className="wd-band__led" x="-3.5" y="-138" width="7" height="64" rx="3.5" filter="url(#wdLedGlow)" />
        {/* Optical sensor window */}
        <rect x="-13" y="96" width="26" height="46" rx="10" fill="#0a0a0e" stroke="#2a2a33" strokeWidth="1.5" />
        <circle className="wd-band__optic" cx="0" cy="110" r="4" />
        <circle className="wd-band__optic" cx="0" cy="128" r="4" />
      </g>
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

const HISTORY_LENGTH = 30

export function WearableDemoPage() {
  const [battery, setBattery] = useState(86)
  const [charging, setCharging] = useState(false)
  const [heartRate, setHeartRate] = useState(72)
  const [hrHistory, setHrHistory] = useState<number[]>(() =>
    Array.from({ length: HISTORY_LENGTH }, (_, i) => 70 + Math.round(Math.sin(i / 3) * 3)),
  )
  const [spo2, setSpo2] = useState(98)
  const [signal, setSignal] = useState(92)
  const [lastSync, setLastSync] = useState(() => new Date())
  const [sosState, setSosState] = useState<SosState>('Standby')
  const [gps, setGps] = useState({ lat: BASE_LAT, lng: BASE_LNG })
  const [patientName, setPatientName] = useState('Demo patient')
  const [deviceIdentifier, setDeviceIdentifier] = useState('NS-SIM-001')
  const [dataSource, setDataSource] = useState<'simulated' | 'backend'>('simulated')
  const [previousGps, setPreviousGps] = useState<{ lat: number; lng: number } | null>(null)
  const [pending, setPending] = useState<string[]>([])
  const [events, setEvents] = useState<EventItem[]>([
    { id: 3, time: '11:06:41', label: 'Measurement', detail: 'Heart rate sample accepted', tone: 'success' },
    { id: 2, time: '11:06:12', label: 'Location', detail: 'GPS lock acquired near UPSA', tone: 'info' },
    { id: 1, time: '11:05:45', label: 'Heartbeat', detail: 'Device status reported to backend', tone: 'success' },
  ])

  const nextId = useRef(4)
  const heartRateRef = useRef(72)
  const timers = useRef<number[]>([])
  const bandRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let active = true

    const hydrateFromBackend = async () => {
      try {
        const patientRows = await getPatients().catch(() => [])
        const patients = Array.isArray(patientRows) ? patientRows : []
        const patient = patients.find((entry) => entry.status === 'active') ?? patients[0]
        if (!patient) return

        const [devices, measurements, locations] = await Promise.all([
          getPatientDevices(patient.id).catch(() => []),
          getPatientMeasurements(patient.id, 20).catch(() => []),
          getPatientLocations(patient.id, 20).catch(() => []),
        ])

        if (!active) return

        const wearableList = Array.isArray(devices) ? devices : []
        const measurementList = Array.isArray(measurements) ? measurements : []
        const locationList = Array.isArray(locations) ? locations : []
        const device = wearableList.find((entry) => entry.device_type === 'wearable') ?? wearableList[0]

        if (patient.full_name) setPatientName(patient.full_name)
        if (device?.device_identifier) setDeviceIdentifier(device.device_identifier)
        setDataSource('backend')

        const latestHeart = measurementList
          .filter((item) => item.measurement_type === 'heart_rate_bpm' || item.measurement_type === 'heart_rate')
          .sort((left, right) => Date.parse(right.measured_at) - Date.parse(left.measured_at))[0]

        const latestSpo2 = measurementList
          .filter((item) => item.measurement_type === 'spo2' || item.measurement_type === 'blood_oxygen')
          .sort((left, right) => Date.parse(right.measured_at) - Date.parse(left.measured_at))[0]

        const latestLocation = locationList
          .slice()
          .sort((left, right) => Date.parse(right.recorded_at) - Date.parse(left.recorded_at))[0]

        if (latestHeart) {
          const heartValue = Math.round(toNumber(latestHeart.value, heartRateRef.current))
          heartRateRef.current = heartValue
          setHeartRate(heartValue)
          setHrHistory((history) => {
            const next = [...history.slice(1), heartValue]
            return next.length >= HISTORY_LENGTH ? next : [...Array(HISTORY_LENGTH - next.length).fill(heartValue), ...next]
          })
        }

        if (latestSpo2) {
          setSpo2(Math.round(toNumber(latestSpo2.value, spo2)))
        }

        if (device?.battery_percent !== null && device?.battery_percent !== undefined) {
          setBattery(Math.round(device.battery_percent))
        }

        if (device?.last_seen_at) {
          setLastSync(new Date(device.last_seen_at))
        }

        if (latestLocation) {
          const nextGps = {
            lat: toNumber(latestLocation.latitude, BASE_LAT),
            lng: toNumber(latestLocation.longitude, BASE_LNG),
          }
          setGps(nextGps)
          setPreviousGps((current) => current ?? nextGps)
        }

        if (device?.status === 'charging') setCharging(true)
        else if (device?.status) setCharging(false)

        const receptionSignal = typeof device?.last_seen_age_seconds === 'number' && device.last_seen_age_seconds <= 30
          ? 92
          : 74
        setSignal(receptionSignal)
      } catch {
        if (active) {
          setDataSource('simulated')
        }
      }
    }

    void hydrateFromBackend()

    const timer = window.setInterval(() => {
      if (!active) return
      const nextHeartRate = nudge(heartRateRef.current, 2, 64, 96)
      heartRateRef.current = nextHeartRate
      setHeartRate(nextHeartRate)
      setHrHistory((history) => [...history.slice(1), nextHeartRate])
      setBattery((current) => (charging ? clamp(current + 2, 0, 100) : clamp(current - (Math.random() > 0.6 ? 1 : 0), 40, 100)))
      setSpo2((current) => nudge(current, 1, 94, 100))
      setSignal((current) => nudge(current, 1, 68, 99))
      setLastSync(new Date())
    }, 4000)

    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [charging])

  useEffect(() => {
    const pendingTimers = timers.current
    return () => pendingTimers.forEach((id) => window.clearTimeout(id))
  }, [])

  /* Derived ------------------------------------------------------------ */
  const hrZone = heartRate < 70 ? 'Resting' : heartRate < 90 ? 'Normal' : 'Elevated'
  const signalLabel = signal >= 80 ? 'Strong' : signal >= 50 ? 'Fair' : 'Weak'
  const batteryLabel = charging ? 'Charging' : battery > 75 ? 'Healthy' : battery > 30 ? 'Fine for now' : 'Low power'
  const daysLeft = Math.max(1, Math.round((battery / 100) * 14))

  const sparkline = useMemo(() => {
    const min = 60
    const max = 100
    const width = 300
    const height = 64
    const step = width / (hrHistory.length - 1)
    const points = hrHistory.map((value, index) => {
      const y = height - ((clamp(value, min, max) - min) / (max - min)) * (height - 8) - 4
      return [index * step, y] as const
    })
    const line = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')
    const area = `${line} L${width} ${height} L0 ${height} Z`
    const last = points[points.length - 1]
    return { line, area, lastY: (last[1] / height) * 100, low: Math.min(...hrHistory), high: Math.max(...hrHistory) }
  }, [hrHistory])

  const mapPosition = (point: { lat: number; lng: number }): CSSProperties => ({
    left: `${clamp(50 + ((point.lng - BASE_LNG) / SPREAD) * 38, 8, 92)}%`,
    top: `${clamp(50 - ((point.lat - BASE_LAT) / SPREAD) * 38, 10, 90)}%`,
  })

  /* Actions ------------------------------------------------------------ */
  const addEvent = (label: string, detail: string, tone: Tone) => {
    const id = nextId.current++
    setEvents((current) => [{ id, time: formatTime(new Date()), label, detail, tone }, ...current].slice(0, 6))
  }

  const run = (key: string, work: () => void, delay = 700) => {
    if (pending.includes(key)) return
    setPending((current) => [...current, key])
    const id = window.setTimeout(() => {
      work()
      setPending((current) => current.filter((item) => item !== key))
    }, delay)
    timers.current.push(id)
  }

  const sendHeartbeat = () =>
    run('heartbeat', () => {
      setLastSync(new Date())
      addEvent('Heartbeat', 'Telemetry packet uploaded to backend', 'success')
    })

  const refreshGps = () =>
    run('gps', () => {
      setPreviousGps(gps)
      const next = {
        lat: BASE_LAT + (Math.random() - 0.5) * SPREAD * 1.6,
        lng: BASE_LNG + (Math.random() - 0.5) * SPREAD * 1.6,
      }
      setGps(next)
      addEvent('Location', `GPS refreshed at ${next.lat.toFixed(4)}, ${next.lng.toFixed(4)}`, 'info')
    })

  const toggleCharging = () =>
    run(
      'charging',
      () => {
        const next = !charging
        setCharging(next)
        addEvent('Charging', next ? 'Charger connected in the demo profile' : 'Charger removed in the demo profile', 'info')
      },
      400,
    )

  const syncGateway = () =>
    run('gateway', () => addEvent('Bluetooth', 'Nearby diagnostics synced to dashboard', 'info'), 900)

  const triggerSos = () => {
    if (sosState !== 'Standby') return
    setSosState('Queued')
    addEvent('SOS', 'Manual alert queued for emergency response workflow', 'danger')
    timers.current.push(window.setTimeout(() => setSosState('Triggered'), 900))
  }

  const resetSos = () => {
    setSosState('Standby')
    addEvent('SOS', 'Alert cleared, strap back on standby', 'success')
  }

  /* Band follows the cursor a little ----------------------------------- */
  const onStageMove = (event: MouseEvent<HTMLDivElement>) => {
    const band = bandRef.current
    if (!band) return
    const rect = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - rect.left) / rect.width - 0.5
    const y = (event.clientY - rect.top) / rect.height - 0.5
    band.style.setProperty('--tilt-x', `${(-y * 7).toFixed(2)}deg`)
    band.style.setProperty('--tilt-y', `${(x * 12).toFixed(2)}deg`)
  }

  const onStageLeave = () => {
    const band = bandRef.current
    if (!band) return
    band.style.setProperty('--tilt-x', '0deg')
    band.style.setProperty('--tilt-y', '0deg')
  }

  const sosStep = sosState === 'Standby' ? 0 : sosState === 'Queued' ? 1 : 2
  const batterySegments = Math.round(battery / 10)
  const signalBars = Math.ceil(signal / 20)
  const spo2Percent = clamp((spo2 - 90) * 10, 0, 100)

  return (
    <div className="wd-page">
      {/* Header ---------------------------------------------------------- */}
      <header className="wd-header">
        <div className="wd-header__title">
          <h1>Wearable demo</h1>
          <p>{dataSource === 'backend' ? `${patientName} is reporting live telemetry from the backend.` : 'A simulated Nexus strap sending telemetry to the control room.'}</p>
        </div>
        <div className="wd-header__meta">
          <span className="wd-tag wd-tag--online">
            <i aria-hidden="true" /> Device online
          </span>
          <span className="wd-tag">Last sync {formatTime(lastSync)}</span>
          <span className="wd-tag wd-tag--outline">{dataSource === 'backend' ? 'Live backend' : 'Simulated data'}</span>
        </div>
      </header>

      {/* Stage ----------------------------------------------------------- */}
      <section className="wd-stage" aria-label="Wearable device" onMouseMove={onStageMove} onMouseLeave={onStageLeave}>
        <div className="wd-stage__visual">
          <div className="wd-device-name">
            <Watch size={15} aria-hidden="true" /> {deviceIdentifier}
          </div>

          <div className="wd-band" ref={bandRef} data-mode={sosState} style={{ '--beat': `${60 / heartRate}s` } as CSSProperties}>
            <div className="wd-band__float">
              <BandIllustration />

              <button type="button" className="wd-hot wd-hot--light" aria-label="Status light">
                <span className="wd-hot__dot" />
                <span className="wd-hot__tip">
                  <strong>Status light</strong>
                  <small>{sosState === 'Standby' ? 'Green, all clear' : sosState === 'Queued' ? 'Amber, alert queued' : 'Red, SOS active'}</small>
                </span>
              </button>

              <button type="button" className="wd-hot wd-hot--sensor" aria-label="Optical sensor">
                <span className="wd-hot__dot" />
                <span className="wd-hot__tip">
                  <strong>Optical sensor</strong>
                  <small>{heartRate} bpm · SpO₂ {spo2}%</small>
                </span>
              </button>

              <button type="button" className="wd-hot wd-hot--strap" aria-label="Strap antenna">
                <span className="wd-hot__dot" />
                <span className="wd-hot__tip">
                  <strong>GPS and radio</strong>
                  <small>Signal {signal}% · {gps.lat.toFixed(4)}, {gps.lng.toFixed(4)}</small>
                </span>
              </button>

              <button type="button" className="wd-hot wd-hot--buckle" aria-label="Battery">
                <span className="wd-hot__dot" />
                <span className="wd-hot__tip wd-hot__tip--left">
                  <strong>Battery {battery}%</strong>
                  <small>{charging ? 'Charging' : `About ${daysLeft} days left`}</small>
                </span>
              </button>
            </div>
          </div>
          <p className="wd-stage__hint">Hover the dots to read each sensor.</p>
        </div>

        <div className="wd-stage__sos" data-mode={sosState}>
          <div className="wd-sos__head">
            <span className="wd-sos__label">SOS alert</span>
            <span className="wd-sos__state" data-mode={sosState}>
              <i aria-hidden="true" /> {sosState}
            </span>
          </div>
          <h2>{sosCopy[sosState].title}</h2>
          <p>{sosCopy[sosState].text}</p>

          <ol className="wd-steps" aria-label="Alert progress">
            {(['Standby', 'Queued', 'Triggered'] as SosState[]).map((step, index) => (
              <li key={step} className={index <= sosStep ? 'is-done' : ''} data-current={index === sosStep}>
                <span aria-hidden="true" />
                {step}
              </li>
            ))}
          </ol>

          {sosState === 'Standby' ? (
            <button type="button" className="wd-sos__button" onClick={triggerSos}>
              <Siren size={20} aria-hidden="true" />
              Trigger SOS
            </button>
          ) : (
            <button type="button" className="wd-sos__button wd-sos__button--reset" onClick={resetSos} disabled={sosState === 'Queued'}>
              <RotateCcw size={18} aria-hidden="true" />
              Clear alert
            </button>
          )}
        </div>
      </section>

      {/* Telemetry ------------------------------------------------------- */}
      <section className="wd-metrics" aria-label="Live telemetry">
        <article className="wd-card wd-card--hr">
          <header>
            <span className="wd-card__icon" style={{ animationDuration: `${60 / heartRate}s` }}>
              <HeartPulse size={18} aria-hidden="true" />
            </span>
            <h2>Heart rate</h2>
            <span className="wd-card__badge">{hrZone}</span>
          </header>
          <div className="wd-card__value">
            <strong>{heartRate}</strong>
            <span>bpm</span>
          </div>
          <div className="wd-spark" aria-hidden="true">
            <svg viewBox="0 0 300 64" preserveAspectRatio="none">
              <path className="wd-spark__area" d={sparkline.area} />
              <path className="wd-spark__line" d={sparkline.line} />
            </svg>
            <span className="wd-spark__dot" style={{ top: `${sparkline.lastY}%` }} />
          </div>
          <footer>
            Range {sparkline.low}–{sparkline.high} bpm over the last two minutes
          </footer>
        </article>

        <article className="wd-card wd-card--spo2">
          <header>
            <span className="wd-card__icon">
              <Droplets size={18} aria-hidden="true" />
            </span>
            <h2>Blood oxygen</h2>
          </header>
          <div className="wd-gauge">
            <svg viewBox="0 0 120 70" aria-hidden="true">
              <path className="wd-gauge__track" d="M10 62 A50 50 0 0 1 110 62" pathLength={100} />
              <path
                className="wd-gauge__fill"
                d="M10 62 A50 50 0 0 1 110 62"
                pathLength={100}
                strokeDasharray={`${spo2Percent} 100`}
              />
            </svg>
            <div className="wd-card__value wd-gauge__value">
              <strong>{spo2}</strong>
              <span>%</span>
            </div>
          </div>
          <footer>{spo2 >= 95 ? 'Normal range' : 'Below normal, recheck the fit'}</footer>
        </article>

        <article className="wd-card wd-card--battery">
          <header>
            <span className={`wd-card__icon${charging ? ' is-charging' : ''}`}>
              <BatteryCharging size={18} aria-hidden="true" />
            </span>
            <h2>Battery</h2>
          </header>
          <div className="wd-card__value">
            <strong>{battery}</strong>
            <span>%</span>
          </div>
          <div className={`wd-cells${charging ? ' is-charging' : ''}`} aria-hidden="true">
            {Array.from({ length: 10 }, (_, index) => (
              <i key={index} className={index < batterySegments ? 'is-on' : ''} />
            ))}
          </div>
          <footer>{charging ? 'Charging now' : `${batteryLabel}, about ${daysLeft} days left`}</footer>
        </article>

        <article className="wd-card wd-card--signal">
          <header>
            <span className="wd-card__icon">
              <Activity size={18} aria-hidden="true" />
            </span>
            <h2>Signal</h2>
          </header>
          <div className="wd-card__value">
            <strong>{signal}</strong>
            <span>%</span>
          </div>
          <div className="wd-bars" aria-hidden="true">
            {[1, 2, 3, 4, 5].map((bar) => (
              <i key={bar} className={bar <= signalBars ? 'is-on' : ''} style={{ height: `${bar * 18}%` }} />
            ))}
          </div>
          <footer>{signalLabel} link to the gateway</footer>
        </article>
      </section>

      {/* Bottom row ------------------------------------------------------ */}
      <section className="wd-lower">
        <article className="wd-panel wd-panel--map">
          <header className="wd-panel__head">
            <h2>Location</h2>
            <span className="wd-coords">
              <MapPin size={14} aria-hidden="true" />
              {gps.lat.toFixed(4)}, {gps.lng.toFixed(4)}
            </span>
          </header>
          <div className="wd-map" aria-label="Last known location">
            <svg viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
              <rect width="400" height="240" fill="#e9eef8" />
              <path d="M0 176 C70 150 130 196 210 170 S340 140 400 160 V240 H0Z" fill="#cfe2f6" />
              <rect x="248" y="22" width="112" height="70" rx="10" fill="#d3ecdc" />
              <g fill="#f7f9fe">
                <rect x="14" y="14" width="86" height="54" rx="6" />
                <rect x="120" y="14" width="104" height="54" rx="6" />
                <rect x="14" y="88" width="86" height="60" rx="6" />
                <rect x="120" y="88" width="104" height="60" rx="6" />
                <rect x="248" y="112" width="112" height="40" rx="6" />
              </g>
              <g stroke="#fff" strokeWidth="9" strokeLinecap="round" fill="none">
                <path d="M0 78 H400" />
                <path d="M110 0 V240" />
                <path d="M236 0 V240" />
                <path d="M0 158 L400 128" />
              </g>
              <g stroke="#cdd5e8" strokeWidth="1.2" strokeDasharray="5 6" fill="none">
                <path d="M0 78 H400" />
                <path d="M110 0 V240" />
                <path d="M236 0 V240" />
              </g>
            </svg>
            {previousGps && <span className="wd-map__trail" style={mapPosition(previousGps)} />}
            <span className="wd-map__pin" style={mapPosition(gps)}>
              <i aria-hidden="true" />
              <MapPin size={22} aria-hidden="true" />
            </span>
          </div>
        </article>

        <article className="wd-panel wd-panel--actions">
          <header className="wd-panel__head">
            <h2>Device actions</h2>
          </header>
          <div className="wd-actions">
            <ActionButton icon={CloudUpload} title="Send heartbeat" hint="Upload a status packet" busy={pending.includes('heartbeat')} onClick={sendHeartbeat} />
            <ActionButton icon={LocateFixed} title="Refresh GPS" hint="Get a new location fix" busy={pending.includes('gps')} onClick={refreshGps} />
            <ActionButton
              icon={BatteryCharging}
              title={charging ? 'Unplug charger' : 'Plug in charger'}
              hint={charging ? 'Back to battery power' : 'Start charging the strap'}
              busy={pending.includes('charging')}
              onClick={toggleCharging}
            />
            <ActionButton icon={Bluetooth} title="Sync gateway" hint="Share diagnostics nearby" busy={pending.includes('gateway')} onClick={syncGateway} />
          </div>
        </article>

        <article className="wd-panel wd-panel--events">
          <header className="wd-panel__head">
            <h2>Event stream</h2>
            <span className="wd-live">
              <i aria-hidden="true" /> Live
            </span>
          </header>
          <ol className="wd-timeline">
            {events.map((item) => (
              <li key={item.id} className={`wd-timeline__item wd-timeline__item--${item.tone}`}>
                <span className="wd-timeline__marker" aria-hidden="true" />
                <div>
                  <strong>{item.label}</strong>
                  <small>{item.detail}</small>
                </div>
                <time>{item.time}</time>
              </li>
            ))}
          </ol>
        </article>
      </section>

      {/* Status strip ---------------------------------------------------- */}
      <footer className="wd-strip">
        <span>
          <Bell size={15} aria-hidden="true" />
          {sosState === 'Standby' ? 'Notifications are quiet' : 'A priority alert is in progress'}
        </span>
        <span>
          <BatteryCharging size={15} aria-hidden="true" />
          Battery health: {battery > 80 ? 'nominal' : 'watch closely'}
        </span>
      </footer>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Action button                                                       */
/* ------------------------------------------------------------------ */

interface ActionButtonProps {
  icon: typeof Activity
  title: string
  hint: string
  busy: boolean
  onClick: () => void
}

function ActionButton({ icon: Icon, title, hint, busy, onClick }: ActionButtonProps) {
  return (
    <button type="button" className={`wd-action${busy ? ' is-busy' : ''}`} onClick={onClick} aria-busy={busy}>
      <span className="wd-action__icon">
        <Icon size={18} aria-hidden="true" />
      </span>
      <span className="wd-action__text">
        <strong>{title}</strong>
        <small>{busy ? 'Working…' : hint}</small>
      </span>
    </button>
  )
}