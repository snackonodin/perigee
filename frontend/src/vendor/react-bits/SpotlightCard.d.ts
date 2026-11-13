import type { CSSProperties, ReactNode } from "react";
declare const SpotlightCard: (props: {
  children?: ReactNode; className?: string; style?: CSSProperties; spotlightColor?: string; intensity?: number;
  spotlightSize?: number; softness?: number; shape?: "circle" | "beam"; borderGlow?: number; proximity?: number;
  smoothing?: number; ambient?: boolean; flare?: boolean; grain?: number; theme?: "dark" | "light";
  [attr: string]: unknown;
}) => JSX.Element;
export default SpotlightCard;
