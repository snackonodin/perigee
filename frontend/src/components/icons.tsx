// One inline-SVG icon set (B5): 24 px box, 1.75 px stroke, round caps. Decorative: always aria-hidden.
const PATHS: Record<string, string> = {
  today: "M4 10.5 12 4l8 6.5M6 9v10.5h12V9M10 19.5V14h4v5.5",
  sleep: "M19.5 14.5A7.5 7.5 0 0 1 9.5 4.5a7.5 7.5 0 1 0 10 10ZM16 4h3l-3 3.5h3",
  body: "M12 7.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM6 10l6-1 6 1M12 9v6m0 0-3 5.5M12 15l3 5.5",
  persona: "M12 12a3.75 3.75 0 1 0 0-7.5 3.75 3.75 0 0 0 0 7.5ZM5 20a7 7 0 0 1 14 0",
  checkin: "M9 4.5h6v2.5H9zM9 5.5H6.5v15h11v-15H15M9 13l2 2 4-4",
  briefing: "M5 4.5h10l4 4v11H5zM15 4.5v4h4M8.5 12.5h7M8.5 16h5",
  consent: "M12 3.5 19 6v5.5c0 4.25-3 7.5-7 9-4-1.5-7-4.75-7-9V6zM9 12l2 2 4-4",
  monitor: "M3 12h4l2-5.5 4 11 2-5.5h6",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2.1-1.2L14.2 3h-4.4l-.3 2.6a7 7 0 0 0-2.1 1.2l-2.3-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2.1 1.2l.3 2.6h4.4l.3-2.6a7 7 0 0 0 2.1-1.2l2.3.9 2-3.4-2-1.5c.07-.4.1-.8.1-1.2Z",
  breath: "M3 9.5c2.5-3 5-3 7.5 0s5 3 7.5 0M3 14.5c2.5-3 5-3 7.5 0s5 3 7.5 0M20 8l1 1.5M20 13l1 1.5",
  clock: "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM12 8v4l2.5 1.5",
  logout: "M14 4.5h4.5v15H14M10 8l-4 4 4 4M6 12h9",
};

export const ROUTE_ICON: Record<string, string> = {
  "/": "today", "/sleep": "sleep", "/body": "body", "/persona": "persona", "/checkin": "checkin",
  "/briefing": "briefing", "/consent": "consent", "/monitor": "monitor", "/settings": "settings",
};

export function Icon({ name, size = 24 }: { name: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.75"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={PATHS[name] ?? PATHS.today} />
    </svg>
  );
}
