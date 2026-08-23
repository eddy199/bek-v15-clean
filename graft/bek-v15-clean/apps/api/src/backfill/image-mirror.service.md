# bek-v15-clean/apps/api/src/backfill/image-mirror.service.ts

- ImageMirrorResult · type · L9-L12 — type ImageMirrorResult = { scanned: number; copied: number; };
- ImageMirrorService · class · L15-L139 — class ImageMirrorService
- constructor · method · L18-L18 — constructor(@InjectDatabase() private readonly db: Db)
- sweep · method · L20-L42 — async sweep(): Promise<ImageMirrorResult>
- sweepCompanies · method · L44-L85 — private async sweepCompanies(): Promise<ImageMirrorResult>
- sweepContacts · method · L87-L112 — private async sweepContacts(): Promise<ImageMirrorResult>
- sweepUsers · method · L114-L138 — private async sweepUsers(): Promise<ImageMirrorResult>
- external · function · L141-L151 — function external<T extends string>( field: T, ): Record<T, { not: null }> & { NOT: Record<T, { contains: string }> }
- unchanged · function · L153-L157 — function unchanged(row: Record<string, unknown>): Prisma.CompanyWhereInput
