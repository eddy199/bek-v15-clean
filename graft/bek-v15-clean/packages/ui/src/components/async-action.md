# bek-v15-clean/packages/ui/src/components/async-action.tsx

- AsyncActionStatus · type · L23-L23 — type AsyncActionStatus = "idle" | "pending" | "success" | "error";
- UseAsyncActionOptions · type · L25-L30 — type UseAsyncActionOptions<TArgs extends unknown[], TResult> = { action: (...args: TArgs) => TResult | Promise<TResult>; resetAfter?: number; onSuccess?: (result: TResult) => void; onError?: (error: unknown) => void; };
- useAsyncAction · function · L32-L109 — function useAsyncAction<TArgs extends unknown[], TResult>({ action, resetAfter = 1400, onSuccess, onError, }: UseAsyncActionOptions<TArgs, TResult>)
- settle · function · L67-L77 — settle = (next: "success" | "error")
- AsyncButtonContentProps · type · L111-L117 — type AsyncButtonContentProps = { status: AsyncActionStatus; children: ReactNode; pendingLabel: ReactNode; successLabel?: ReactNode; errorLabel?: ReactNode; };
- AsyncButtonContent · function · L119-L192 — function AsyncButtonContent({ status, children, pendingLabel, successLabel = "Done", errorLabel = "Try again", }: AsyncButtonContentProps)
