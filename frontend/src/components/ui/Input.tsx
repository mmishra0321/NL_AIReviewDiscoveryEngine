import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-md border border-border bg-bg-subtle px-3 py-2 text-sm text-fg placeholder:text-fg-subtle",
        "focus-ring focus-visible:border-brand/60 transition",
        className,
      )}
      {...rest}
    />
  ),
);
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...rest }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "w-full rounded-md border border-border bg-bg-subtle px-3 py-2 text-sm text-fg placeholder:text-fg-subtle",
        "focus-ring focus-visible:border-brand/60 transition resize-y min-h-[72px]",
        className,
      )}
      {...rest}
    />
  ),
);
Textarea.displayName = "Textarea";
