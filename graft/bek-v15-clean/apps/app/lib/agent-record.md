# bek-v15-clean/apps/app/lib/agent-record.ts

- AgentRecordKind · type · L3-L3 — type AgentRecordKind = "contact" | "company" | "deal";
- AgentRecord · type · L5-L5 — type AgentRecord = { kind: AgentRecordKind; id: string };
- RecordCopy · type · L7-L14 — type RecordCopy = { header: string; field: "contactId" | "companyId" | "dealId"; title: string; blurb: string; placeholder: string; suggestions: string[]; };
- recordCopy · function · L58-L60 — function recordCopy(kind: AgentRecordKind): RecordCopy
- recordHeader · function · L62-L64 — function recordHeader(record: AgentRecord): Record<string, string>
- recordFilter · function · L66-L72 — function recordFilter(record: AgentRecord): { contactId?: string; companyId?: string; dealId?: string; }
