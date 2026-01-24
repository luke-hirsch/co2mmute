import { useEffect, useRef } from "react";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "default";
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmDialog = ({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) => {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onCancel();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onCancel]);

  // Focus trap
  useEffect(() => {
    if (isOpen && dialogRef.current) {
      dialogRef.current.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const confirmButtonClass = {
    danger:
      "bg-red-600 hover:bg-red-700 focus-visible:outline-red-600 dark:bg-red-600 dark:hover:bg-red-700",
    warning:
      "bg-amber-600 hover:bg-amber-700 focus-visible:outline-amber-600 dark:bg-amber-600 dark:hover:bg-amber-700",
    default:
      "bg-primary-600 hover:bg-primary-700 focus-visible:outline-primary-600 dark:bg-primary-600 dark:hover:bg-primary-700",
  }[variant];

  return (
    <div className="fixed inset-0 z-100 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative z-10 w-full max-w-md rounded-lg border border-subtle bg-surface p-6 shadow-xl dark:border-darksubtle dark:bg-darksurface"
      >
        <h2 className="mb-2 text-lg font-semibold text-main dark:text-darktext">
          {title}
        </h2>
        <p className="mb-6 text-sm text-muted dark:text-darkmutedtext">
          {message}
        </p>

        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="rounded px-4 py-2 text-sm font-semibold text-main transition-colors hover:bg-elevated dark:text-darktext dark:hover:bg-darkelevated"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`rounded px-4 py-2 text-sm font-semibold text-white transition-colors focus-visible:outline focus-visible:outline-offset-2 ${confirmButtonClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
