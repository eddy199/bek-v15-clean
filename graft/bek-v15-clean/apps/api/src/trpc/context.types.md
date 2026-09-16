# bek-v15-clean/apps/api/src/trpc/context.types.ts

- BaseTrpcContext · type · L4-L7 — type BaseTrpcContext = { req?: Request; session: Session | null; };
- AuthedTrpcContext · type · L9-L11 — type AuthedTrpcContext = BaseTrpcContext & { user: SessionUser; };
