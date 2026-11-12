import type { ReactElement } from "react";
import { createBrowserRouter, createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { AuthProvider, RequireAuth } from "./auth/AuthProvider";
import { AppShell } from "./components/AppShell";
import { Breathing, Heart } from "./pages/Live";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { Psyche } from "./pages/Psyche";
import { Settings } from "./pages/Settings";
import { Sleep } from "./pages/Sleep";
import { Placeholder } from "./routes/Placeholder";
import { TABS } from "./routes/tabs";
import { SafetyProvider } from "./safety/SafetyProvider";

const PAGES: Record<string, ReactElement> = {
  "/": <Overview />,
  "/breathing": <Breathing />,
  "/heart": <Heart />,
  "/sleep": <Sleep />,
  "/psyche": <Psyche />,
  "/settings": <Settings />,
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

const routes = [
  {
    element: <Root />,
    children: [
      { path: "/login", element: <Login /> },
      {
        path: "/",
        element: (
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        ),
        children: TABS.map((t) => {
          const element = PAGES[t.path] ?? <Placeholder tab={t} />;
          return t.path === "/" ? { index: true, element } : { path: t.path.slice(1), element };
        }),
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
