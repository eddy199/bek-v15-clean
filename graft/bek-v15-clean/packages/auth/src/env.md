# bek-v15-clean/packages/auth/src/env.ts

- optional · function · L7-L10 — optional = (key: string): string | undefined
- pair · function · L12-L27 — pair = ( idKey: string, secretKey: string, ): { clientId: string; clientSecret: string } | undefined
- googleCredentials · function · L29-L31 — googleCredentials = (): | { clientId: string; clientSecret: string } | undefined
- microsoftCredentials · function · L33-L43 — microsoftCredentials = (): | { clientId: string; clientSecret: string; tenantId: string } | undefined
- slackCredentials · function · L45-L47 — slackCredentials = (): | { clientId: string; clientSecret: string } | undefined
- isGoogleConfigured · function · L70-L72 — function isGoogleConfigured(): boolean
- isMicrosoftConfigured · function · L74-L76 — function isMicrosoftConfigured(): boolean
- isSlackConfigured · function · L78-L80 — function isSlackConfigured(): boolean
