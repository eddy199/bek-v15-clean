# bek-v15-clean/apps/app/components/responsive-sheet.tsx

- useResponsive · function · L24-L24 — useResponsive = ()
- RootProps · type · L26-L32 — type RootProps = { open?: boolean; defaultOpen?: boolean; onOpenChange?: (open: boolean) => void; modal?: boolean; children?: React.ReactNode; };
- Sheet · function · L34-L45 — function Sheet({ children, ...props }: RootProps)
- SheetContent · function · L47-L84 — function SheetContent({ children, side, size, showCloseButton, className, ...props }: React.ComponentProps<"div"> & { side?: "top" | "right" | "bottom" | "left"; size?: SheetSize; showCloseButton?: boolean; onOpenAutoFocus?: (event: Event) => void; })
- SheetHeader · function · L86-L92 — function SheetHeader(props: React.ComponentProps<"div">)
- SheetTitle · function · L94-L104 — function SheetTitle(props: { className?: string; size?: "default" | "lg"; children?: React.ReactNode; })
- SheetDescription · function · L106-L115 — function SheetDescription(props: { className?: string; children?: React.ReactNode; })
