import { createBrowserRouter, createMemoryRouter, RouterProvider } from "react-router";
import { AppShell } from "./components/AppShell";
import { Placeholder } from "./routes/Placeholder";
import { TABS } from "./routes/tabs";

const routes = [
  {
    path: "/",
    element: <AppShell />,
    children: TABS.map((t) =>
      t.path === "/"
        ? { index: true, element: <Placeholder tab={t} /> }
        : { path: t.path.slice(1), element: <Placeholder tab={t} /> },
    ),
  },
];

export function App({ initialPath }: { initialPath?: string }) {
  const router = initialPath
    ? createMemoryRouter(routes, { initialEntries: [initialPath] })
    : createBrowserRouter(routes);
  return <RouterProvider router={router} />;
}
