# bek-v15-clean/apps/api/src/auth/auth.service.ts

- UserProfile · interface · L7-L14 — interface UserProfile
- profileKey · function · L18-L18 — profileKey = (userId: string)
- AuthService · class · L21-L70 — class AuthService
- constructor · method · L24-L27 — constructor( @InjectDatabase() private readonly db: Db, @Inject(CACHE_MANAGER) private readonly cache: Cache, )
- getProfile · method · L29-L64 — async getProfile(userId: string): Promise<UserProfile>
- invalidateProfile · method · L66-L69 — async invalidateProfile(userId: string): Promise<void>
