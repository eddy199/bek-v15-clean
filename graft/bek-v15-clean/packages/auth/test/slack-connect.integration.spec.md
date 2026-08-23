# bek-v15-clean/packages/auth/test/slack-connect.integration.spec.ts

- Snapshot · type · L65-L73 — type Snapshot = { organization: { name: string; slug: string; website: string | null; metadata: string | null; } | null; members: { id: string; userId: string; role: string; createdAt: Date }[]; };
- idOf · function · L77-L77 — idOf = (label: string)
- sessionCookie · function · L79-L103 — sessionCookie = async (userId: string): Promise<string>
- seat · function · L105-L135 — seat = async ( label: string, role: WorkspaceRole | null, ): Promise<string>
- startConnect · function · L137-L148 — startConnect = ( path: string, cookie?: string, providerId: string = SLACK_PROVIDER_ID, )
- linkSlack · function · L150-L150 — linkSlack = (cookie?: string)
- completeConnect · function · L152-L161 — completeConnect = ( cookie?: string, providerId: string = SLACK_PROVIDER_ID, )
- messageOf · function · L163-L164 — messageOf = async (response: Response): Promise<string>
- arrived · function · L166-L167 — arrived = async (response: Response): Promise<boolean>
- clear · function · L169-L173 — clear = async ()
