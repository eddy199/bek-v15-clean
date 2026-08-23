# bek-v15-clean/apps/agent/agent/lib/lookup.ts

- RecordKind · type · L5-L5 — type RecordKind = "contact" | "company" | "deal";
- ContactHit · type · L7-L15 — type ContactHit = { kind: "contact"; id: string; name: string; title: string | null; email: string | null; company: { id: string; name: string } | null; lastActivityAt: string | null; };
- CompanyHit · type · L17-L25 — type CompanyHit = { kind: "company"; id: string; name: string; domain: string | null; industry: string | null; contacts: number; deals: number; };
- DealHit · type · L27-L35 — type DealHit = { kind: "deal"; id: string; name: string; stage: string; amount: number | null; currency: string; company: { id: string; name: string }; };
- SearchHit · type · L37-L37 — type SearchHit = ContactHit | CompanyHit | DealHit;
- SearchResult · type · L39-L45 — type SearchResult = { query: string; contacts: ContactHit[]; companies: CompanyHit[]; deals: DealHit[]; total: number; };
- DealListStatus · type · L47-L47 — type DealListStatus = "open" | "won" | "lost" | "all";
- DealListOptions · type · L49-L57 — type DealListOptions = { status?: DealListStatus; inactiveForDays?: number; companyId?: string; ownerId?: string; limit?: number; cursor?: string; now?: Date; };
- listDeals · function · L59-L156 — async function listDeals(options: DealListOptions = {})
- searchCrm · function · L158-L188 — async function searchCrm( query: string, options: { kinds?: RecordKind[]; limit?: number } = {}, ): Promise<SearchResult>
- wants · function · L170-L170 — wants = (kind: RecordKind)
- searchContacts · function · L190-L244 — async function searchContacts( term: string, words: string[], email: string | null, limit: number, ): Promise<ContactHit[]>
- searchCompanies · function · L246-L291 — async function searchCompanies( term: string, words: string[], domain: string | null, limit: number, ): Promise<CompanyHit[]>
- searchDeals · function · L293-L336 — async function searchDeals( term: string, words: string[], limit: number, ): Promise<DealHit[]>
- score · function · L338-L360 — function score(term: string, fields: string[]): number
- bareDomain · function · L362-L368 — function bareDomain(term: string): string | null
