# bek-v15-clean/apps/app/components/app-icon-rail.tsx

- RailItem · type · L33-L39 — type RailItem = { title: string; href: string; icon: CarbonIconType; match: "exact" | "prefix"; related?: string[]; };
- isActive · function · L61-L67 — function isActive(item: RailItem, pathname: string): boolean
- RailLink · function · L69-L107 — function RailLink({ item, active, onPrefetch, }: { item: RailItem; active: boolean; onPrefetch: () => void; })
- MobileRailLink · function · L109-L146 — function MobileRailLink({ item, active, onNavigate, onPrefetch, }: { item: RailItem; active: boolean; onNavigate: () => void; onPrefetch: () => void; })
- MobileRailIconLink · function · L148-L183 — function MobileRailIconLink({ item, active, onNavigate, onPrefetch, }: { item: RailItem; active: boolean; onNavigate: () => void; onPrefetch: () => void; })
- AppIconRailFallback · function · L185-L206 — function AppIconRailFallback()
- AppIconRail · function · L208-L306 — function AppIconRail()
