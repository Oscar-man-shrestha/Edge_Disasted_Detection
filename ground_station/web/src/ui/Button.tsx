import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "./cn";

type Variant = "default" | "primary" | "ghost" | "danger" | "success";
const VARIANTS: Record<Variant, string> = {
  default: "bg-surface-2 border-line hover:bg-surface-3 text-text",
  primary: "bg-accent border-accent text-white hover:brightness-110",
  ghost: "bg-transparent border-transparent hover:bg-surface-2 text-text-2 hover:text-text",
  danger: "bg-critical/15 border-critical/50 text-critical hover:bg-critical/25",
  success: "bg-good/15 border-good/50 text-good hover:bg-good/25",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md" | "icon";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "default", size = "md", className, type = "button", ...rest }, ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg border font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50 disabled:pointer-events-none",
        size === "sm" && "h-7 px-2.5 text-xs",
        size === "md" && "h-8 px-3 text-sm",
        size === "icon" && "h-8 w-8 text-sm",
        VARIANTS[variant], className,
      )}
      {...rest}
    />
  );
});
