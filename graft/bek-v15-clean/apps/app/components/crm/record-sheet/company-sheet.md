# bek-v15-clean/apps/app/components/crm/record-sheet/company-sheet.tsx

- Company · type · L74-L74 — type Company = RouterOutputs["companies"]["byId"];
- CompanyDeal · type · L75-L75 — type CompanyDeal = Company["deals"][number];
- pendingFields · function · L79-L85 — function pendingFields(company: Company): string[]
- companyConsequence · function · L87-L102 — function companyConsequence(company: Company): string
- nextClose · function · L125-L131 — function nextClose(deals: CompanyDeal[]): string | null
- CompanySheet · function · L133-L297 — function CompanySheet({ companyId }: { companyId: string })
- CompanyOverview · function · L299-L424 — function CompanyOverview({ company }: { company: Company })
- save · function · L312-L313 — save = (data: Record<string, string | null>)
- saveFields · function · L315-L316 — saveFields = (fields: Record<string, FieldValueJson>)
- CompanyContacts · function · L426-L554 — function CompanyContacts({ company, adding, onAdd, onDone, }: { company: Company; adding: boolean; onAdd: () => void; onDone: () => void; })
- CompanyDeals · function · L556-L642 — function CompanyDeals({ company, adding, onAdd, onDone, }: { company: Company; adding: boolean; onAdd: () => void; onDone: () => void; })
