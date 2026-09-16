# bek-v15-clean/apps/agent/agent/lib/blank-facts.ts

- BlankFactFill · type · L26-L33 — type BlankFactFill = { contactId: string; contact: string; field: FactField; value: string; score: number; dropped: number; };
- BlankFactSweep · type · L35-L42 — type BlankFactSweep = { scanned: number; filled: number; settled: number; waiting: number; unscanned: number; fills: BlankFactFill[]; };
- sweepBlankFacts · function · L44-L127 — async function sweepBlankFacts( options: { dry?: boolean } = {}, ): Promise<BlankFactSweep>
- Proposal · type · L129-L145 — type Proposal = { id: string; contactId: string; field: string; value: string; score: number; contact: { id: string; email: string | null; firstName: string; lastName: string | null; title: string | null; linkedinUrl: string | null; twitterUrl: string | null; githubUrl: string | null; }; };
- appliedValues · function · L147-L166 — async function appliedValues( contactIds: string[], ): Promise<Map<string, string>>
- groupByField · function · L168-L179 — function groupByField(proposals: Proposal[]): [Proposal, ...Proposal[]][]
- redundant · function · L181-L193 — function redundant(group: Proposal[], value: string | null): Proposal[]
- fill · function · L195-L235 — async function fill( factId: string, contactId: string, field: FactField, value: string, column: string | null, ): Promise<void>
- key · function · L237-L239 — function key(contactId: string, field: string): string
