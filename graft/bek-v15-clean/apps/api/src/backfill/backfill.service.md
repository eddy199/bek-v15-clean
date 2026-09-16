# bek-v15-clean/apps/api/src/backfill/backfill.service.ts

- BackfillScope · type · L13-L13 — type BackfillScope = "companies" | "contacts" | "deals";
- BackfillResult · type · L15-L20 — type BackfillResult = { queued: number; alreadyQueued: number; remaining: number; iconsResolving: number; };
- BackfillService · class · L48-L328 — class BackfillService implements OnModuleInit
- constructor · method · L51-L57 — constructor( @InjectDatabase() private readonly db: Db, private readonly agent: AgentTriggerService, private readonly favicon: FaviconService, private readonly images: ImageMirrorService, @Inject(CACHE_MANAGER) private readonly cache: Cache, )
- onModuleInit · method · L59-L63 — onModuleInit(): void
- auto · method · L65-L94 — async auto(): Promise<{ started: boolean }>
- sweepWorkspace · method · L96-L115 — private async sweepWorkspace(): Promise<void>
- run · method · L117-L121 — async run(scope: BackfillScope): Promise<BackfillResult>
- runCompanies · method · L123-L182 — private async runCompanies(dealsOnly: boolean): Promise<BackfillResult>
- runContacts · method · L184-L233 — private async runContacts(): Promise<BackfillResult>
- sweepFavicons · method · L235-L258 — private async sweepFavicons(): Promise<number>
- companiesNeedingBrand · method · L260-L262 — private companiesNeedingBrand(): Prisma.CompanyWhereInput
- companiesNeedingArtwork · method · L264-L282 — private async companiesNeedingArtwork(): Promise<Prisma.CompanyWhereInput>
- contactsNeedingPhoto · method · L299-L323 — private async contactsNeedingPhoto(): Promise<Prisma.ContactWhereInput>
- contactsNeverResearched · method · L325-L327 — private contactsNeverResearched(): Prisma.ContactWhereInput
