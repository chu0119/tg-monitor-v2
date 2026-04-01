import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "destructive" | "outline";
}

export const Badge = forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = "default", ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors",
          {
            "bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/50": variant === "default",
            "bg-cyber-green/20 text-cyber-green border border-cyber-green/50": variant === "success",
            "bg-yellow-500/20 text-yellow-500 border border-yellow-500/50": variant === "warning",
            "bg-cyber-pink/20 text-cyber-pink border border-cyber-pink/50": variant === "destructive",
            "border border-muted-foreground text-muted-foreground": variant === "outline",
          },
          className
        )}
        {...props}
      />
    );
  }
);

Badge.displayName = "Badge";
