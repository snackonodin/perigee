import { useEffect, useState, type ReactElement, type ReactNode } from "react";
import { createBrowserRouter, createMemoryRouter, Outlet, RouterProvider, useNavigate } from "react-router";
import { api } from "./api/client";
import { AuthProvider, RequireAuth } from "./auth/AuthProvider";
import { AppShell } from "./components/AppShell";
import { Login } from "./pages/Login";
import { Setup } from "./pages/Setup";
import { Overview } from "./pages/Overview";
import { Persona } from "./pages/Persona";
import { Body } from "./pages/Body";
import { Psyche } from "./pages/Psyche";
import { Settings } from "./pages/Settings";
import { Sleep } from "./pages/Sleep";
import { Placeholder } from "./routes/Placeholder";
import { TABS } from "./routes/tabs";
import { SafetyProvider } from "./safety/SafetyProvider";
import { CompanionGallery } from "./pages/CompanionGallery";

const PAGES: Record<string, ReactElement> = {
  "/": <Overview />,
  "/sleep": <Sleep />,
  "/persona": <Persona />,
  "/body": <Body />,
  "/checkin": <Psyche />,
};

function Root() {
  return (
    <AuthProvider>
      <SafetyProvider>
        <Outlet />
      </SafetyProvider>
    </AuthProvider>
  );
}

function SetupGate({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let active = true;
    void (async () => {
      let done = false;
      try { done = window.localStorage.getItem("setup.done") === "true"; } catch { /* baseline response remains available */ }
      if (!done) {
        try {
          const { data } = await api.GET("/api/v1/today");
          if (data?.baselines?.length) {
            try { window.localStorage.setItem("setup.done", "true"); } catch { /* baseline is the durable signal */ }
            done = true;
          }
        } catch { /* unavailable baseline means keep first-run setup reachable */ }
      }
      if (!active) return;
      if (done) setReady(true);
      else navigate("/setup", { replace: true });
    })();
    return () => { active = false; };
  }, [navigate]);
  if (!ready) return <p className="muted shell" role="status">Loading your account…</p>;
  return <>{children}</>;
}

const routes = [
  {
    element: <Root />,
    children: [
      ...(import.meta.env.DEV ? [{ path: "/dev/companion", element: <CompanionGallery /> }] : []),
      { path: "/login", element: <Login /> },
      { path: "/register", element: <Login signup /> },
      { path: "/setup", element: <RequireAuth><Setup /></RequireAuth> },
      {
        path: "/",
        element: (
          <RequireAuth>
            <SetupGate><AppShell /></SetupGate>
          </RequireAuth>
        ),
        children: [
          ...TABS.map((t) => {
            const element = PAGES[t.path] ?? <Placeholder tab={t} />;
            return t.path === "/" ? { index: true, element } : { path: t.path.slice(1), element };
          }),
          { path: "settings", element: <Settings /> },
        ],
      },
    ],
  },
];

export function App({ initialPath }: { initialPath?: string }) {
  const router = initialPath
    ? createMemoryRouter(routes, { initialEntries: [initialPath] })
    : createBrowserRouter(routes);
  return <RouterProvider router={router} />;
}
