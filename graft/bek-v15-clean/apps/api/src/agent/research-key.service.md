# bek-v15-clean/apps/api/src/agent/research-key.service.ts

- KeyCheck · type · L6-L9 — type KeyCheck = | { outcome: "valid" } | { outcome: "invalid"; reason: string } | { outcome: "unknown"; reason: string };
- ResearchKeyService · class · L18-L82 — class ResearchKeyService
- verify · method · L21-L72 — async verify(apiKey: string): Promise<KeyCheck>
- cannotTell · method · L74-L81 — private cannotTell(reason: string): KeyCheck
