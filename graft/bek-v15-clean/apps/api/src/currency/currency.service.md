# bek-v15-clean/apps/api/src/currency/currency.service.ts

- CurrencyRate · interface · L21-L29 — interface CurrencyRate
- CurrencyInUse · interface · L31-L36 — interface CurrencyInUse
- CurrencySettings · interface · L38-L46 — interface CurrencySettings
- CurrencyService · class · L49-L255 — class CurrencyService
- constructor · method · L52-L56 — constructor( @InjectDatabase() private readonly db: Db, private readonly conversion: ConversionService, private readonly rates: RatesService, )
- settings · method · L58-L133 — async settings(actingUserId: string): Promise<CurrencySettings>
- requireManager · method · L135-L141 — private async requireManager(userId: string): Promise<void>
- setReportingCurrency · method · L143-L170 — async setReportingCurrency( actingUserId: string, code: string, ): Promise<CurrencySettings>
- setManualRate · method · L172-L218 — async setManualRate( actingUserId: string, code: string, rate: number, ): Promise<CurrencySettings>
- removeManualRate · method · L220-L240 — async removeManualRate( actingUserId: string, code: string, ): Promise<CurrencySettings>
- refresh · method · L242-L254 — async refresh(actingUserId: string): Promise<CurrencySettings>
