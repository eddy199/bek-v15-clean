# bek-v15-clean/apps/app/components/crm/company-picker.tsx

- CompanyPicker · function · L20-L90 — function CompanyPicker({ id, value, onValueChange, placeholder = "Choose a company", none, selected, disabled, variant, className, }: { id?: string; value: string; onValueChange: (value: string) => void; placeholder?: string; none?: { value: string; label: string }; selected?: ComboboxOption; disabled?: boolean; variant?: "default" | "ghost"; className?: string; })
- CompanyMenuSearch · function · L92-L158 — function CompanyMenuSearch({ none, onSelect, inputRef, }: { none?: string; onSelect: (companyId: string | null) => void; inputRef?: Ref<HTMLInputElement>; })
- InlineCompanyField · function · L160-L199 — function InlineCompanyField({ label = "Company", value, onSave, saving = false, none, company, }: { label?: string; value: string; onSave: (next: string) => void; saving?: boolean; none?: { value: string; label: string }; company?: { id: string; name: string } | null; })
