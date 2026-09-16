# bek-v15-clean/packages/db/test/currency.spec.ts

- Row · type · L15-L20 — type Row = { rate: Prisma.Decimal; asOf: Date; source: RateSource; provider: string | null; };
- fakeDb · function · L22-L40 — function fakeDb(rows: Row[]): { db: Db; calls: number }
- calls · method · L36-L38 — get calls()
- row · function · L42-L53 — function row( rate: string, source: RateSource, provider: string | null = null, ): Row
- rate · function · L165-L170 — rate = (value: string): ResolvedRate
