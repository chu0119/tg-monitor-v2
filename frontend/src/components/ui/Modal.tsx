import { ReactNode, useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}

export function Modal({ isOpen, onClose, title, children, className }: ModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 模态框内容 */}
      <div
        className={cn(
          "relative z-10 w-full glass rounded-lg shadow-[0_0_50px_rgba(0,240,255,0.2)] animate-in fade-in slide-in-from-bottom sm:slide-in-from-bottom-0 sm:zoom-in duration-200",
          "max-h-[90vh] sm:max-h-[85vh] flex flex-col",
          "rounded-b-none sm:rounded-b-lg mx-0 sm:mx-4",
          className
        )}
      >
        {/* 标题栏 */}
        {title && (
          <div className="flex items-center justify-between p-4 border-b border-cyber-blue/20 shrink-0">
            <h2 className="text-lg font-semibold neon-text">{title}</h2>
            <button
              onClick={onClose}
              className="p-2 rounded hover:bg-cyber-blue/10 transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
            >
              <X size={20} />
            </button>
          </div>
        )}

        {/* 内容 */}
        <div className="p-4 overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  );
}
