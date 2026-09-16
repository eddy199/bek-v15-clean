# bek-v15-clean/packages/ui/src/components/sheet.tsx

- SheetSize · type · L29-L31 — type SheetSize = NonNullable< VariantProps<typeof sheetContentVariants>["size"] >;
- Sheet · function · L33-L35 — function Sheet({ ...props }: React.ComponentProps<typeof SheetPrimitive.Root>)
- SheetTrigger · function · L37-L41 — function SheetTrigger({ ...props }: React.ComponentProps<typeof SheetPrimitive.Trigger>)
- SheetClose · function · L43-L47 — function SheetClose({ ...props }: React.ComponentProps<typeof SheetPrimitive.Close>)
- SheetPortal · function · L49-L53 — function SheetPortal({ ...props }: React.ComponentProps<typeof SheetPrimitive.Portal>)
- SheetOverlay · function · L55-L69 — function SheetOverlay({ className, ...props }: React.ComponentProps<typeof SheetPrimitive.Overlay>)
- SheetContent · function · L71-L108 — function SheetContent({ className, children, side = "right", size, showCloseButton = true, ...props }: React.ComponentProps<typeof SheetPrimitive.Content> & { side?: "top" | "right" | "bottom" | "left"; size?: SheetSize; showCloseButton?: boolean; })
- SheetHeader · function · L110-L118 — function SheetHeader({ className, ...props }: React.ComponentProps<"div">)
- SheetFooter · function · L120-L128 — function SheetFooter({ className, ...props }: React.ComponentProps<"div">)
- SheetTitle · function · L142-L155 — function SheetTitle({ className, size, ...props }: React.ComponentProps<typeof SheetPrimitive.Title> & VariantProps<typeof sheetTitleVariants>)
- SheetDescription · function · L157-L168 — function SheetDescription({ className, ...props }: React.ComponentProps<typeof SheetPrimitive.Description>)
