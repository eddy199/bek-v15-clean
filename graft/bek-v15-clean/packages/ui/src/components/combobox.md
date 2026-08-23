# bek-v15-clean/packages/ui/src/components/combobox.tsx

- ComboboxOption · type · L23-L28 — type ComboboxOption = { value: string; label: string; hint?: string; keywords?: string[]; };
- Combobox · function · L30-L131 — function Combobox({ options, selectedOption, value, onValueChange, placeholder = "Select an option", searchPlaceholder = "Search…", empty = "Nothing matches.", search, onSearchChange, stale, size = "default", variant, className, ...props }: Omit<React.ComponentProps<"button">, "onChange" | "value"> & VariantProps<typeof selectTriggerVariants> & { options: ComboboxOption[]; selectedOption?: ComboboxOption; value: string; onValueChange: (value: string) => void; placeholder?: string; searchPlaceholder?: string; empty?: React.ReactNode; search?: string; onSearchChange?: (search: string) => void; stale?: boolean; size?: "sm" | "default"; })
- close · function · L65-L68 — close = ()
