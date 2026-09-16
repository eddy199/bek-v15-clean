# bek-v15-clean/apps/app/components/crm/record-sheet/contact-sheet.tsx

- Contact · type · L66-L66 — type Contact = RouterOutputs["contacts"]["byId"];
- ContactSheet · function · L89-L260 — function ContactSheet({ contactId }: { contactId: string })
- CompanyStat · function · L262-L285 — function CompanyStat({ company, }: { company: NonNullable<Contact["company"]>; })
- ContactOverview · function · L287-L432 — function ContactOverview({ contact }: { contact: Contact })
- agentProps · function · L295-L304 — agentProps = (field: string)
- saveFields · function · L313-L314 — saveFields = (fields: Record<string, FieldValueJson>)
- save · function · L318-L319 — save = (data: Record<string, string | null>)
- Background · function · L434-L483 — function Background({ brief }: { brief: NonNullable<Contact["brief"]> })
- PreviousRoles · function · L485-L502 — function PreviousRoles({ roles }: { roles: string[] })
- WeKnowThem · function · L504-L564 — function WeKnowThem({ relationship, contactName: name, }: { relationship: Contact["relationship"]; contactName: string; })
- Colleagues · function · L566-L590 — function Colleagues({ colleagues, }: { colleagues: Contact["relationship"]["colleagues"]; })
- ContactDeals · function · L592-L635 — function ContactDeals({ contact }: { contact: Contact })
