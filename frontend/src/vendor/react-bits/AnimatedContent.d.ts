import type { CSSProperties, ReactNode } from "react";
declare const AnimatedContent: (props: {
  children?: ReactNode; className?: string; style?: CSSProperties; distance?: number; direction?: "vertical" | "horizontal";
  duration?: number; ease?: string; initialOpacity?: number; scale?: number; delay?: number; stagger?: number;
  trigger?: "scroll" | "mount"; once?: boolean; [attr: string]: unknown;
}) => JSX.Element;
export default AnimatedContent;
