# bek-v15-clean/apps/api/src/database/database.module.ts

- DatabaseModule · class · L16-L38 — class DatabaseModule implements OnModuleInit, OnApplicationShutdown
- constructor · method · L19-L19 — constructor(@InjectDatabase() private readonly db: Db)
- onModuleInit · method · L21-L32 — async onModuleInit(): Promise<void>
- onApplicationShutdown · method · L34-L37 — async onApplicationShutdown(signal?: string): Promise<void>
