declare const SplitText: (props: {
  text: string; className?: string; delay?: number; duration?: number; ease?: string; splitType?: "chars" | "words" | "lines" | string;
  from?: Record<string, unknown>; to?: Record<string, unknown>; textAlign?: "left" | "center" | "right"; tag?: string;
  effect?: string; trigger?: "view" | "load" | "hover" | "click"; [attr: string]: unknown;
}) => JSX.Element;
export default SplitText;
