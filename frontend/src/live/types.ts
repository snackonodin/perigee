// Events of GET /api/v1/live/vitals (LIVE-1), as text/event-stream. Mirrors
// backend/services/live.py window_payload / heart_payload / hello / bye / end.

export interface HelloLive {
  mode: "live";
  poll_s: number;
  heartbeat_s: number;
  max_s: number;
}
export interface HelloReplay {
  mode: "replay";
  session_id: string;
  speed: number;
  events: number;
}
export interface ReplayMeta {
  replay?: true;
  seq?: number;
}
export interface WindowEvent extends ReplayMeta {
  session_id: string;
  t_start: string;
  t_end: string;
  rr_a: number | null;
  rr_b: number | null;
  pnr_db: number | null;
  quality: number;
  motion: boolean;
  motion_score: number | null;
  presence: boolean;
}
export interface HeartEvent extends ReplayMeta {
  session_id: string;
  t_start: string;
  t_end: string;
  hr_bpm: number | null;
  quality: number;
  experimental: true;
}
export interface Bye {
  reason: "max_s" | "unauthorized" | string;
}

export type LiveEvent =
  | { type: "hello"; data: HelloLive | HelloReplay }
  | { type: "window"; data: WindowEvent }
  | { type: "heart"; data: HeartEvent }
  | { type: "bye"; data: Bye }
  | { type: "end"; data: { events: number } };
