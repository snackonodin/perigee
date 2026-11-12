import { type DependencyList, useCallback, useEffect, useState } from "react";
import { errorText } from "./client";

interface Loaded<T> {
  data?: T;
  error: string | null;
  loading: boolean;
  apiMock: boolean;
  reload(): void;
}

/** Load once (and on deps change). `fetcher` returns openapi-fetch's {data, error, response}. */
export function useLoad<T>(
  fetcher: () => Promise<{ data?: T; error?: unknown; response?: Response }>,
  deps: DependencyList = [],
): Loaded<T> {
  const [state, setState] = useState<{ data?: T; error: string | null; loading: boolean; apiMock: boolean }>({
    error: null,
    loading: true,
    apiMock: false,
  });
  const [n, setN] = useState(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fetcher, deps);
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    run()
      .then(({ data, error, response }) => {
        if (!live) return;
        setState({ data, loading: false, error: data === undefined ? errorText(error, response?.status) : null,
          apiMock: response?.headers.get("X-TODO-API-Mock") === "true" });
      })
      .catch(() => live && setState({ loading: false, error: errorText(undefined), apiMock: false }));
    return () => {
      live = false;
    };
  }, [run, n]);
  return { ...state, reload: () => setN((x) => x + 1) };
}
