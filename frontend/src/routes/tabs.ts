// The six tabs of the app shell, in order. `live` tabs will stream from the API.
export interface TabDef {
  path: string;
  label: string;
  icon: string;
  live?: boolean;
  experimental?: boolean;
}

export const TABS: readonly TabDef[] = [
  { path: "/", label: "Today", icon: "◉" },
  { path: "/sleep", label: "Sleep", icon: "☾" },
  { path: "/body", label: "Body", icon: "⌁" },
  { path: "/persona", label: "Persona", icon: "✧" },
  { path: "/checkin", label: "Check-in", icon: "♡" },
  { path: "/briefing", label: "Briefing", icon: "▤" },
  { path: "/consent", label: "Consent", icon: "◇" },
];
