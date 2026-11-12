import type { ReactNode } from "react";

/** Uniform loading / error / content for anything fetched with useLoad. */
export function LoadState<T>({
  state,
  label,
  children,
}: {
  state: { data?: T; error: string | null; loading: boolean; reload(): void };
  label: string;
  children(data: T): ReactNode;
}) {
  if (state.data !== undefined) return <>{children(state.data)}</>;
  if (state.error) {
    return (
      <div className="load-error" role="alert">
        <p>
          Could not load {label}: {state.error}
        </p>
        <button type="button" className="ghost" onClick={state.reload}>
          Retry
        </button>
      </div>
    );
  }
  return (
    <p className="muted loading" aria-busy="true" role="status">
      Loading {label}…
    </p>
  );
}
