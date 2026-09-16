# bek-v15-clean/packages/ui/src/components/attachment.tsx

- Attachment · function · L42-L62 — function Attachment({ className, state = "done", size = "default", orientation = "horizontal", ...props }: React.ComponentProps<"div"> & VariantProps<typeof attachmentVariants> & { state?: "idle" | "uploading" | "processing" | "error" | "done" })
- AttachmentMedia · function · L80-L93 — function AttachmentMedia({ className, variant = "icon", ...props }: React.ComponentProps<"div"> & VariantProps<typeof attachmentMediaVariants>)
- AttachmentContent · function · L95-L109 — function AttachmentContent({ className, ...props }: React.ComponentProps<"div">)
- AttachmentTitle · function · L111-L125 — function AttachmentTitle({ className, ...props }: React.ComponentProps<"span">)
- AttachmentDescription · function · L127-L142 — function AttachmentDescription({ className, ...props }: React.ComponentProps<"span">)
- AttachmentActions · function · L144-L158 — function AttachmentActions({ className, ...props }: React.ComponentProps<"div">)
- AttachmentAction · function · L160-L178 — function AttachmentAction({ className, variant, size = "icon-xs", ...props }: React.ComponentProps<typeof Button>)
- AttachmentTrigger · function · L180-L198 — function AttachmentTrigger({ className, asChild = false, type, ...props }: React.ComponentProps<"button"> & { asChild?: boolean })
- AttachmentGroup · function · L200-L211 — function AttachmentGroup({ className, ...props }: React.ComponentProps<"div">)
