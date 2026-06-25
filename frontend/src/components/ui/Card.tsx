import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Card = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { interactive?: boolean }>(
  ({ className, interactive, ...rest }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-xl border border-border bg-bg-elevated shadow-card",
        interactive && "transition cursor-pointer hover:border-brand/60 hover:shadow-glow",
        className,
      )}
      {...rest}
    />
  ),
);
Card.displayName = "Card";

export function CardHeader({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pb-3", className)} {...rest} />;
}
export function CardContent({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-2", className)} {...rest} />;
}
export function CardFooter({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-3 border-t border-border", className)} {...rest} />;
}
export function CardTitle({ className, ...rest }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("font-semibold text-base leading-snug text-fg", className)} {...rest} />;
}
