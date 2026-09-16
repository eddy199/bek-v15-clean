# bek-v15-clean/packages/db/src/fx.ts

- RateOrigin · type · L6-L6 — type RateOrigin = "IDENTITY" | "MANUAL" | "FETCHED";
- ResolvedRate · interface · L8-L13 — interface ResolvedRate
- Conversion · interface · L15-L21 — interface Conversion
- resolveRate · function · L25-L57 — async function resolveRate( db: Db, base: string, quote: string, now: Date = new Date(), ): Promise<ResolvedRate | null>
- applyRate · function · L59-L75 — function applyRate( amount: Prisma.Decimal, rate: ResolvedRate, base: string, ): Conversion
- convertToBase · function · L77-L90 — async function convertToBase( db: Db, amount: Prisma.Decimal | null, from: string, base: string, now: Date = new Date(), ): Promise<Conversion | null>
