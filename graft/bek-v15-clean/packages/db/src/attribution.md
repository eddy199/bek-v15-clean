# bek-v15-clean/packages/db/src/attribution.ts

- Medium · type · L13-L13 — type Medium = (typeof MEDIUMS)[number];
- RawTouch · interface · L15-L24 — interface RawTouch
- Touch · interface · L26-L35 — interface Touch
- classifyTouch · function · L96-L157 — function classifyTouch(raw: RawTouch, at: Date = new Date()): Touch
- isSameTouch · function · L159-L165 — function isSameTouch(a: Touch, b: Touch): boolean
- describeTouch · function · L167-L179 — function describeTouch(touch: { source: string | null; medium: string | null; campaign: string | null; }): string
- mediumFrom · function · L181-L190 — function mediumFrom(value: string | null | undefined): Medium
- match · function · L192-L200 — function match(host: string, table: Record<string, string>): string | null
- matches · function · L202-L216 — function matches(labels: string[], needle: string): boolean
- isSuffix · function · L218-L223 — function isSuffix(tail: string[]): boolean
- hostOf · function · L225-L233 — function hostOf(referrer: string | null): string | null
- clean · function · L235-L240 — function clean(value: string | null | undefined): string | null
- valid · function · L242-L244 — function valid(date: Date): boolean
