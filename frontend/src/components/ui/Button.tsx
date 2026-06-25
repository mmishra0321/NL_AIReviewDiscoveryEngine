import { forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "outline";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  primary:   "bg-brand text-brand-fg hover:bg-brand-hover active:bg-brand font-semibold shadow-sm",
  secondary: "bg-bg-elevated text-fg border border-border hover:bg-bg-hover hover:border-border-strong",
  ghost:     "bg-transparent text-fg-muted hover:bg-bg-elevated hover:text-fg",
  outline:   "bg-transparent text-fg border border-border hover:bg-bg-elevated hover:border-border-strong",
};

const sizes: Record<Size, string> = {
  sm: "text-xs px-2.5 py-1.5 rounded-md",
  md: "text-sm px-3.5 py-2   rounded-md",
  lg: "text-base px-5 py-2.5 rounded-lg",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "secondary", size = "md", ...rest }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 transition select-none",
        "disabled:opacity-50 disabled:cursor-not-allowed focus-ring",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    />
  ),
);
Button.displayName = "Button";
