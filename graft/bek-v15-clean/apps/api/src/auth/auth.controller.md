# bek-v15-clean/apps/api/src/auth/auth.controller.ts

- CrmSession · type · L10-L10 — type CrmSession = UserSession<typeof auth>;
- AuthController · class · L13-L34 — class AuthController
- constructor · method · L14-L14 — constructor(private readonly authService: AuthService)
- getMe · method · L17-L19 — async getMe(@Session() session: CrmSession)
- getSession · method · L23-L33 — getSession(@Session() session?: CrmSession)
