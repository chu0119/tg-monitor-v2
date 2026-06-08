import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        ref={ref}
        className={cn(
          "input-tech flex h-10 w-full rounded-md px-3 py-2 text-sm",
          className
        )}
        {...props}
      />
    );
  }
);

Input.displayName = "Input";
