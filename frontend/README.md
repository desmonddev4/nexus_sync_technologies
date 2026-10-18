# React Native frontend

Frontend implementation starts after the backend API contracts and workflows are established. Use React Native with TypeScript; do not create web HTML pages or a shared global CSS file.

Organize each screen and reusable component in its own directory. Keep its styles adjacent in a dedicated `.styles.ts` file using React Native `StyleSheet`, for example:

```text
src/
  screens/
    Incidents/
      IncidentQueueScreen.tsx
      IncidentQueueScreen.styles.ts
      index.ts
  components/
    IncidentRow/
      IncidentRow.tsx
      IncidentRow.styles.ts
      index.ts
```

Keep navigation, API clients, shared types, and reusable UI in their own modules. Avoid putting page logic and all application styling into one file.