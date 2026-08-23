# bek-v15-clean/apps/api/src/logging/request-logger.middleware.ts

- RequestLoggerMiddleware · class · L11-L78 — class RequestLoggerMiddleware implements NestMiddleware
- use · method · L14-L34 — use(request: Request, response: Response, next: NextFunction): void
- logCompleted · method · L36-L77 — private logCompleted( request: Request, response: Response, context: RequestContext, startedAt: bigint, ): void
- incomingRequestId · function · L80-L88 — function incomingRequestId(request: Request): string | undefined
- logAuthRoute · function · L92-L98 — function logAuthRoute( request: Request, response: Response, next: NextFunction, ): void
- sessionUserId · function · L100-L106 — function sessionUserId(request: Request): string | undefined
