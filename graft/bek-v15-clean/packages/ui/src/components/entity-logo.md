# bek-v15-clean/packages/ui/src/components/entity-logo.tsx

- EntityLogoSize · type · L9-L9 — type EntityLogoSize = "xs" | "sm" | "default" | "lg" | "xl";
- EntityLogoTone · type · L19-L19 — type EntityLogoTone = "opaque" | "dark" | "light";
- EntityLogo · function · L27-L87 — function EntityLogo({ src, darkSrc, tone, name, size = "default", className, }: { src?: string | null; darkSrc?: string | null; tone?: EntityLogoTone | null; name: string; size?: EntityLogoSize; className?: string; })
- Artwork · function · L89-L118 — function Artwork({ src, px, className, onError, }: { src: string; px: number; className: string; onError?: () => void; })
