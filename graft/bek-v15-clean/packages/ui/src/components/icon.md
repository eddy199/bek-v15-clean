# bek-v15-clean/packages/ui/src/components/icon.tsx

- IconMotion · type · L24-L24 — type IconMotion = (typeof ICON_MOTIONS)[number];
- CarbonIconProps · type · L26-L28 — type CarbonIconProps = React.SVGProps<SVGSVGElement> & { size?: number | string; };
- CarbonIcon · type · L30-L33 — type CarbonIcon = React.ComponentType<CarbonIconProps> & { displayName?: string; render?: { displayName?: string; name?: string }; };
- iconName · function · L71-L73 — function iconName(icon: CarbonIcon): string | undefined
- iconMotionFor · function · L75-L78 — function iconMotionFor(icon: CarbonIcon): IconMotion
- IconProps · type · L80-L83 — type IconProps = CarbonIconProps & { icon: CarbonIcon; motion?: IconMotion; };
- Icon · function · L85-L96 — function Icon({ icon: Glyph, motion, className, ...props }: IconProps)
