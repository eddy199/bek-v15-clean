# bek-v15-clean/apps/api/src/currency/rates.service.ts

- RateRefresh · interface · L26-L32 — interface RateRefresh
- OpenExchangeResponse · interface · L34-L40 — interface OpenExchangeResponse
- parseAsOf · function · L42-L46 — function parseAsOf(value: unknown): Date | null
- wait · function · L48-L50 — function wait(ms: number): Promise<void>
- RatesService · class · L53-L232 — class RatesService
- constructor · method · L56-L56 — constructor(@InjectDatabase() private readonly db: Db)
- refreshedAt · method · L58-L60 — async refreshedAt(): Promise<Date | null>
- refresh · method · L62-L94 — async refresh(): Promise<RateRefresh>
- store · method · L96-L147 — private async store( base: string, rates: Map<string, Prisma.Decimal>, asOf: Date, ): Promise<number>
- fetch · method · L149-L160 — private async fetch( base: string, ): Promise<{ rates: Map<string, Prisma.Decimal>; asOf: Date } | null>
- attempt · method · L162-L231 — private async attempt( base: string, attempt: number, ): Promise<{ rates: Map<string, Prisma.Decimal>; asOf: Date } | null>
