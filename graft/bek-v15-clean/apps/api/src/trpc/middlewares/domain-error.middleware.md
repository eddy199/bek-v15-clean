# bek-v15-clean/apps/api/src/trpc/middlewares/domain-error.middleware.ts

- TrpcErrorCode · type · L9-L16 — type TrpcErrorCode = | "BAD_REQUEST" | "UNAUTHORIZED" | "FORBIDDEN" | "NOT_FOUND" | "CONFLICT" | "TOO_MANY_REQUESTS" | "INTERNAL_SERVER_ERROR";
- statusToTrpcCode · function · L18-L35 — function statusToTrpcCode(status: number): TrpcErrorCode
- DomainErrorMiddleware · class · L38-L58 — class DomainErrorMiddleware implements TRPCMiddleware
- use · method · L39-L57 — async use(opts: MiddlewareOptions): Promise<MiddlewareResponse>
