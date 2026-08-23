# bek-v15-clean/apps/api/src/logging/context-logger.ts

- consoleLoggerOptions · function · L20-L29 — function consoleLoggerOptions(): ConsoleLoggerOptions
- StructuredMessage · type · L31-L31 — type StructuredMessage = { message: string } & Record<string, unknown>;
- JsonLogRecord · interface · L33-L42 — interface JsonLogRecord
- ContextLogger · class · L45-L102 — class ContextLogger extends ConsoleLogger
- constructor · method · L46-L48 — constructor()
- getJsonLogObject · method · L50-L75 — protected override getJsonLogObject( message: unknown, options: { context: string; logLevel: LogLevel; writeStreamType?: "stdout" | "stderr"; errorStack?: unknown; }, ): JsonLogRecord
- stringifyMessage · method · L77-L91 — protected override stringifyMessage( message: unknown, logLevel: LogLevel, ): string
- formatContext · method · L93-L101 — protected override formatContext(context: string): string
- shortId · function · L104-L106 — function shortId(requestId: string): string
- isStructuredMessage · function · L108-L119 — function isStructuredMessage(value: unknown): value is StructuredMessage
- withoutMessage · function · L121-L125 — function withoutMessage(value: StructuredMessage): Record<string, unknown>
