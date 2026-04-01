import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/providers/ThemeProvider";
import { Button } from "@/components/ui/Button";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleTheme}
      className="relative overflow-hidden group"
      title={theme === "dark" ? "切换到亮色主题" : "切换到暗色主题"}
    >
      <div className="relative w-5 h-5">
        {theme === "dark" ? (
          <Moon
            size={20}
            className="absolute inset-0 transition-all duration-300 rotate-0 scale-100"
          />
        ) : (
          <Sun
            size={20}
            className="absolute inset-0 transition-all duration-300 rotate-90 scale-0"
          />
        )}
        <Moon
          size={20}
          className={`absolute inset-0 transition-all duration-300 ${
            theme === "dark" ? "rotate-0 scale-100" : "-rotate-90 scale-0"
          }`}
        />
        <Sun
          size={20}
          className={`absolute inset-0 transition-all duration-300 ${
            theme === "dark" ? "rotate-90 scale-0" : "rotate-0 scale-100"
          }`}
        />
      </div>
    </Button>
  );
}
