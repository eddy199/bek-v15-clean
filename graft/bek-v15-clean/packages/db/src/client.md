# bek-v15-clean/packages/db/src/client.ts

- liveDatabase · function · L9-L19 — function liveDatabase(): string
- testDatabase · function · L21-L50 — function testDatabase(): string
- databaseName · function · L52-L58 — function databaseName(url: string): string
- PrismaLogRecord · interface · L60-L65 — interface PrismaLogRecord
- PrismaLogSink · type · L67-L67 — type PrismaLogSink = (record: PrismaLogRecord) => void;
- consoleSink · function · L69-L80 — consoleSink: PrismaLogSink = ({ level, message, target, durationMs })
- setPrismaLogSink · function · L84-L86 — function setPrismaLogSink(next: PrismaLogSink | null): void
- createPrismaClient · function · L101-L121 — createPrismaClient = ()
- Db · type · L133-L133 — type Db = typeof db;
