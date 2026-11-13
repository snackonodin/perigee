import type { CSSProperties, ReactNode } from "react";
import SpotlightCard from "../vendor/react-bits/SpotlightCard";
import "../vendor/react-bits/SpotlightCard.css";
import { useMotionOK } from "./motion";

/** Cursor spotlight + edge glow around a tile (desktop pointer only; plain wrapper otherwise). */
export function Spotlight({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ok = useMotionOK() && typeof window !== "undefined" && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  if (!ok) return <div className={`spotlight-wrap ${className}`}>{children}</div>;
  return <SpotlightCard className={`spotlight-wrap ${className}`} theme="light" spotlightColor="#5B4BDB" intensity={0.5} borderGlow={0.5}
    spotlightSize={260} proximity={40}
    style={{ "--spotlight-card-surface": "transparent", "--spotlight-card-border": "transparent", "--spotlight-card-shadow": "none" } as CSSProperties}>{children}</SpotlightCard>;
}
