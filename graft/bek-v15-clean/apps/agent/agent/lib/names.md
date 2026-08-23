# bek-v15-clean/apps/agent/agent/lib/names.ts

- searchTerms · function · L1-L23 — function searchTerms(local: string): string[]
- add · function · L5-L7 — add = (term: string)
- looksLikeSameCompany · function · L25-L39 — function looksLikeSameCompany( employer: string, companyName: string, domain: string, ): boolean
- nameMatchesLocalPart · function · L41-L65 — function nameMatchesLocalPart( person: { firstName: string | null; lastName: string | null }, local: string, ): boolean
- isDerivedName · function · L67-L75 — function isDerivedName( email: string | null, firstName: string, lastName: string | null, ): boolean
- splitName · function · L77-L87 — function splitName( fullName: string, ): { firstName: string; lastName: string | null } | null
- domainOf · function · L89-L92 — function domainOf(email: string): string | null
- namesMatch · function · L94-L104 — function namesMatch(a: string | null, b: string | null): boolean
- words · function · L106-L111 — function words(value: string | null): string[]
- normalise · function · L113-L115 — function normalise(value: string): string
