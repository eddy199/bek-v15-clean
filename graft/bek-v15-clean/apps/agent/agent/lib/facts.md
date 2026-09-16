# bek-v15-clean/apps/agent/agent/lib/facts.ts

- FactField · type · L19-L19 — type FactField = keyof typeof FIELDS;
- FactSubject · type · L23-L27 — type FactSubject = { email: string | null; firstName: string; lastName: string | null; } & Record<string, unknown>;
- factColumn · function · L29-L31 — function factColumn(field: FactField): string | null
- fillsBlank · function · L33-L42 — function fillsBlank(input: { field: FactField; contact: FactSubject; hasAgentFact: boolean; }): boolean
- RecordFactInput · type · L44-L51 — type RecordFactInput = { contactId: string; field: FactField; value: string; evidence: Evidence[]; method: string; sourceUrl?: string; };
- RecordFactResult · type · L53-L60 — type RecordFactResult = { stored: boolean; applied: boolean; band: FactBand | null; score: number; rationale: string; reason?: string; };
- recordFact · function · L62-L234 — async function recordFact( input: RecordFactInput, ): Promise<RecordFactResult>
- lastEmployerChange · function · L236-L260 — async function lastEmployerChange(contactId: string)
- BriefSections · type · L262-L269 — type BriefSections = { currentRole?: string; tenure?: string; previousRoles?: string[]; seniority?: string; function?: string; location?: string; };
- writeBrief · function · L271-L304 — async function writeBrief(input: { contactId: string; narrative: string; sections: BriefSections; evidence: Evidence[]; sourceUrl?: string; }): Promise<{ written: boolean; score: number; reason?: string }>
- humanOwns · function · L306-L328 — function humanOwns({ field, column, contact, hasAgentFact, }: { field: FactField; column: string | null; contact: { email: string | null; firstName: string; lastName: string | null; } & Record<string, unknown>; hasAgentFact: boolean; }): boolean
- isEmpty · function · L330-L346 — function isEmpty({ field, column, contact, hasAgentFact, }: { field: FactField; column: string | null; contact: Record<string, unknown>; hasAgentFact: boolean; }): boolean
- sameValue · function · L353-L355 — function sameValue(a: string, b: string): boolean
- canonicalValue · function · L357-L367 — function canonicalValue(value: string): string
- asWebUrl · function · L369-L376 — function asWebUrl(value: string): URL | null
