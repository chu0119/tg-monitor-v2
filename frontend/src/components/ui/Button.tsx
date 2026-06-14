import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "ghost" | "tech";
  size?: "default" | "sm" | "lg" | "icon";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyber-blue disabled:pointer-events-none disabled:opacity-50",
          {
            "bg-cyber-blue text-background hover:bg-cyber-blue/90": variant === "default",
            "bg-cyber-pink text-white hover:bg-cyber-pink/90": variant === "destructive",
            "border border-cyber-blue/50 bg-transparent hover:bg-cyber-blue/10": variant === "outline",
            "hover:bg-cyber-blue/10 dark:hover:bg-cyber-blue/10 light:hover:bg-cyber-blue/20": variant === "ghost",
            "btn-tech": variant === "tech",
            "h-10 px-4 py-2": size === "default",
            "h-9 rounded-md px-3 text-sm": size === "sm",
            "h-11 rounded-md px-8": size === "lg",
            "h-10 w-10": size === "icon",
          },
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";
