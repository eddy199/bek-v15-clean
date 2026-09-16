# bek-v15-clean/packages/db/src/crm-events.ts

- CrmEventRecordKind · type · L1-L1 — type CrmEventRecordKind = "company" | "contact" | "deal";
- CrmEventDefinition · type · L3-L7 — type CrmEventDefinition = { label: string; description: string; recordKind: CrmEventRecordKind; };
- CrmEventType · type · L42-L42 — type CrmEventType = keyof typeof CRM_EVENT_CATALOG;
- isCrmEventType · function · L49-L51 — function isCrmEventType(value: unknown): value is CrmEventType
