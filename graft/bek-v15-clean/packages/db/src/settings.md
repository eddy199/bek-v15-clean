# bek-v15-clean/packages/db/src/settings.ts

- AgentModelSetting · interface · L15-L19 — interface AgentModelSetting
- readAgentModel · function · L21-L37 — async function readAgentModel(db: Db): Promise<AgentModelSetting>
- writeAgentModel · function · L39-L53 — async function writeAgentModel( db: Db, model: { id: string; contextWindowTokens: number } | null, ): Promise<void>
- readContextDevKey · function · L59-L66 — async function readContextDevKey(db: Db): Promise<string | null>
- writeContextDevKey · function · L68-L76 — async function writeContextDevKey(db: Db, key: string): Promise<void>
- readReportingCurrency · function · L78-L87 — async function readReportingCurrency(db: Db): Promise<string>
- writeReportingCurrency · function · L89-L102 — async function writeReportingCurrency( db: Db, code: string, ): Promise<string>
- readRatesRefreshedAt · function · L104-L111 — async function readRatesRefreshedAt(db: Db): Promise<Date | null>
- writeRatesRefreshedAt · function · L113-L122 — async function writeRatesRefreshedAt( db: Db, ratesRefreshedAt: Date, ): Promise<void>
- maskKey · function · L124-L127 — function maskKey(key: string): string
