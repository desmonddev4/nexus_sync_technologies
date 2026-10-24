# Mobile face-motion development check

The mobile app's **Face motion check** is an opt-in research test in the profile screen. It sends three camera frames to the local backend for a head-movement check. The backend does not store those frames, compare them with an identity template, issue a token, or change patient access. Password login remains authoritative. The device's Face ID / fingerprint option only unlocks the saved session on that device.

## Local setup

The local backend `.env` should contain:

```dotenv
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<computer-wifi-ip>
BIOMETRIC_MOTION_TEST_ENABLED=true
BIOMETRIC_MOTION_CONSENT_VERSION=face-motion-dev-v1
```

The mobile app's ignored `.env.local` should point to the computer's Wi-Fi address:

```dotenv
EXPO_PUBLIC_API_URL=http://<computer-wifi-ip>:8000
```

Keep the phone and computer on the same trusted Wi-Fi network. Start Django so it listens on the network interface and start Expo in LAN mode:

```powershell
# backend
python manage.py runserver 0.0.0.0:8000

# frontend/mobile
npm run start -- --lan
```

## Test account and flow

The local development database has a synthetic patient account:

- Username: `mobile-motion-test`
- Password: `NexusMotionDev-2026!`

Open the app in Expo Go, sign in, open **Your account**, scroll to **Face motion check**, review and accept the separate notice, then capture the centered frame and follow the randomized turn prompts. A passing result reports only that motion was detected; it does not identify the person or affect sign-in.

This local test is not evaluated presentation-attack detection and must not be used as an authentication factor or for real patient records.
