# bek-v15-clean/apps/api/src/logging/all-exceptions.filter.ts

- AllExceptionsFilter · class · L14-L62 — class AllExceptionsFilter implements ExceptionFilter
- catch · method · L17-L39 — catch(exception: unknown, host: ArgumentsHost): void
- log · method · L41-L61 — private log(exception: unknown, status: number, request: Request): void
- routePattern · function · L64-L67 — function routePattern(request: Request): string | null
- describe · function · L69-L75 — function describe(exception: unknown): string
- body · function · L77-L99 — function body( exception: unknown, status: number, requestId: string | undefined, ): Record<string, unknown>
