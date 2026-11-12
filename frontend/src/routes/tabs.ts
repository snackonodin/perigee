// The six tabs of the app shell, in order. `live` tabs will stream from the API.
export interface TabDef {
  path: string;
  label: string;
  live?: boolean;
  experimental?: boolean;
}

export const TABS: readonly TabDef[] = [
  { path: "/", label: "Overview" },
  { path: "/breathing", label: "Breathing", live: true },
  { path: "/heart", label: "Heart", live: true, experimental: true },
  { path: "/sleep", label: "Sleep" },
  { path: "/psyche", label: "Psyche" },
  { path: "/settings", label: "Settings" },
];
