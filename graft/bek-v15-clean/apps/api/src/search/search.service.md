# bek-v15-clean/apps/api/src/search/search.service.ts

- SearchHit · type · L5-L14 — type SearchHit = { kind: "company" | "contact" | "deal"; id: string; label: string; detail: string | null; iconUrl: string | null; iconDarkUrl: string | null; iconTone: string | null; imageUrl: string | null; };
- SearchService · class · L19-L126 — class SearchService
- constructor · method · L20-L20 — constructor(@InjectDatabase() private readonly db: Db)
- quick · method · L22-L125 — async quick(q: string): Promise<{ hits: SearchHit[] }>
