# bek-v15-clean/packages/db/src/safe-fetch.ts

- isBlockedAddress · function · L8-L35 — function isBlockedAddress(ip: string): boolean
- isBlockedIPv4 · function · L37-L49 — function isBlockedIPv4(a: number, b: number): boolean
- expandIPv6 · function · L51-L86 — function expandIPv6(ip: string): number[] | null
- parse · function · L67-L73 — parse = (part: string)
- resolvesToPublicHost · function · L88-L116 — async function resolvesToPublicHost( hostname: string, timeoutMs: number = DEFAULT_TIMEOUT_MS, ): Promise<boolean>
- safeFetch · function · L118-L172 — async function safeFetch( url: string, { method = "GET", timeoutMs = DEFAULT_TIMEOUT_MS, headers, }: { method?: "GET" | "HEAD"; timeoutMs?: number; headers?: Record<string, string>; } = {}, ): Promise<{ response: Response; url: URL } | null>
