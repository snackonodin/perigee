import type { StreamStatus } from "./stream";

const TEXT: Record<StreamStatus["state"], string> = {
  connecting: "Connecting…",
  open: "Live",
  reconnecting: "Reconnecting…",
  ended: "Replay finished",
  error: "Stopped",
  stopped: "Stopped",
};

export function StatusPill({ status, replay }: { status: StreamStatus; replay: boolean }) {
  const text = status.state === "open" && replay ? "Replaying" : TEXT[status.state];
  return (
    <span className={`pill ${status.state}`} role="status">
      {text}
      {status.detail ? ` (${status.detail})` : ""}
    </span>
  );
}
