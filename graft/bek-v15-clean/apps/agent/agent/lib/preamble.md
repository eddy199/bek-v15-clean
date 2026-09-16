# bek-v15-clean/apps/agent/agent/lib/preamble.ts

- Opened · type · L6-L11 — type Opened = { dispatched: boolean; kind?: string | null; reason?: string | null; budget?: number | null; };
- Preamble · type · L13-L16 — type Preamble = { markdown: string; focus: { contactId?: string | null; companyId?: string | null }; };
- sessionPreamble · function · L18-L31 — async function sessionPreamble( record: { contactId?: string | null; companyId?: string | null; dealId?: string | null; }, opened: Opened, ): Promise<Preamble>
- composeClosing · function · L33-L39 — async function composeClosing( us: WorkspaceIdentity | null, ): Promise<string>
- closing · function · L41-L43 — async function closing(): Promise<string>
- opening · function · L45-L60 — function opening(opened: Opened, questions: string): string
- contactPreamble · function · L62-L145 — async function contactPreamble( contactId: string, opened: Opened, ): Promise<Preamble>
- companyPreamble · function · L147-L223 — async function companyPreamble( companyId: string, opened: Opened, ): Promise<Preamble>
- dealPreamble · function · L225-L302 — async function dealPreamble( dealId: string, opened: Opened, ): Promise<Preamble>
- noRecordPreamble · function · L304-L318 — async function noRecordPreamble(): Promise<Preamble>
- workspacePreamble · function · L320-L366 — async function workspacePreamble( known?: WorkspaceIdentity | null, ): Promise<Preamble>
