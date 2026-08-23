# bek-v15-clean/apps/app/lib/social-links.ts

- SocialLink · type · L8-L8 — type SocialLink<T> = { key: keyof T; label: string; icon: CarbonIcon };
- CompanyLinks · type · L10-L16 — type CompanyLinks = { linkedinUrl: string | null; twitterUrl: string | null; githubUrl: string | null; pricingUrl: string | null; careersUrl: string | null; };
- ContactLinks · type · L18-L22 — type ContactLinks = { linkedinUrl: string | null; twitterUrl: string | null; githubUrl: string | null; };
- present · function · L38-L43 — function present<T>(record: T, links: SocialLink<T>[])
- companySocialLinks · function · L45-L47 — function companySocialLinks(company: CompanyLinks)
- contactSocialLinks · function · L49-L51 — function contactSocialLinks(contact: ContactLinks)
- hasCompanyLinks · function · L53-L55 — function hasCompanyLinks(company: CompanyLinks): boolean
- hasContactLinks · function · L57-L59 — function hasContactLinks(contact: ContactLinks): boolean
