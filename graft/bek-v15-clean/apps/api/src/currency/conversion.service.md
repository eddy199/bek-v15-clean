# bek-v15-clean/apps/api/src/currency/conversion.service.ts

- DealFxFields · interface · L14-L19 — interface DealFxFields
- Unconverted · interface · L21-L24 — interface Unconverted
- RerateResult · interface · L26-L30 — interface RerateResult
- ConversionService · class · L33-L208 — class ConversionService
- constructor · method · L36-L36 — constructor(@InjectDatabase() private readonly db: Db)
- reportingCurrency · method · L38-L40 — async reportingCurrency(): Promise<string>
- rateFor · method · L42-L45 — async rateFor(currency: string): Promise<ResolvedRate | null>
- convert · method · L47-L57 — async convert( amount: PrismaTypes.Decimal | null, currency: string, ): Promise<Conversion | null>
- dealFields · method · L59-L80 — async dealFields( amount: PrismaTypes.Decimal | null, currency: string, ): Promise<DealFxFields>
- countedWhere · method · L82-L84 — countedWhere(base: string): PrismaTypes.DealWhereInput
- pendingWhere · method · L86-L95 — pendingWhere(base: string): PrismaTypes.DealWhereInput
- unconverted · method · L97-L115 — async unconverted( where: PrismaTypes.DealWhereInput = {}, ): Promise<Unconverted>
- rerateAll · method · L117-L119 — async rerateAll(): Promise<RerateResult>
- fillMissing · method · L121-L123 — async fillMissing(): Promise<RerateResult>
- rerate · method · L125-L170 — private async rerate(onlyMissing: boolean): Promise<RerateResult>
- write · method · L172-L195 — private async write( base: string, code: string, rate: ResolvedRate, places: number, onlyMissing: boolean, ): Promise<number>
- clear · method · L197-L207 — private async clear(code: string): Promise<number>
