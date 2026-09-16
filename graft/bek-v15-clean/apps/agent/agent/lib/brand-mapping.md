# bek-v15-clean/apps/agent/agent/lib/brand-mapping.ts

- BrandUpdate · type · L4-L4 — type BrandUpdate = Prisma.CompanyUpdateInput;
- CompanySnapshot · type · L6-L29 — type CompanySnapshot = { name: string; nameIsPlaceholder: boolean; description: string | null; logoUrl: string | null; logoDarkUrl: string | null; iconUrl: string | null; iconDarkUrl: string | null; iconTone: string | null; brandColor: string | null; industry: string | null; subIndustry: string | null; city: string | null; stateCode: string | null; country: string | null; countryCode: string | null; phone: string | null; email: string | null; linkedinUrl: string | null; twitterUrl: string | null; githubUrl: string | null; pricingUrl: string | null; careersUrl: string | null; };
- LogoMode · type · L31-L31 — type LogoMode = "light" | "dark" | "has_opaque_background";
- pickEntry · function · L33-L44 — function pickEntry( logos: Brand["logos"], type: "logo" | "icon", mode?: LogoMode, )
- pickLogo · function · L46-L52 — function pickLogo( logos: Brand["logos"], type: "logo" | "icon", mode?: LogoMode, ): string | null
- pickIcon · function · L54-L60 — function pickIcon(logos: Brand["logos"])
- iconTone · function · L62-L80 — function iconTone(logos: Brand["logos"]): string | null
- parseHex · function · L82-L90 — function parseHex( hex: string | null | undefined, ): [number, number, number] | null
- social · function · L92-L94 — function social(socials: Brand["socials"], type: string): string | null
- clean · function · L96-L99 — function clean(value: string | null | undefined): string | null
- fillable · function · L101-L105 — function fillable(key: string, current: CompanySnapshot): boolean
- brandToUpdate · function · L107-L159 — function brandToUpdate( brand: Brand, current: CompanySnapshot, ): BrandUpdate
- fill · function · L113-L120 — fill = <K extends keyof CompanySnapshot & keyof BrandUpdate>( key: K, value: string | null, )
- stillFillable · function · L161-L174 — function stillFillable( update: BrandUpdate, current: CompanySnapshot, ): BrandUpdate
- filledFields · function · L176-L178 — function filledFields(update: BrandUpdate): string[]
