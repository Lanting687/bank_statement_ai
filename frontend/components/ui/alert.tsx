import * as React from "react";
import { AlertTriangle, Info, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Variant = "default" | "destructive" | "warning" | "success";

const variantClasses: Record<Variant, string> = {
  default: "bg-secondary text-secondary-foreground border-border",
  destructive: "bg-destructive/10 text-destructive border-destructive/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  success: "bg-success/10 text-success border-success/30",
};

const variantIcon: Record<Variant, React.ElementType> = {
  default: Info,
  destructive: AlertTriangle,
  warning: AlertTriangle,
  success: CheckCircle2,
};

export function Alert({
  className,
  variant = "default",
  children,
}: {
  className?: string;
  variant?: Variant;
  children: React.ReactNode;
}) {
  const Icon = variantIcon[variant];
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2.5 rounded-md border px-3.5 py-3 text-sm",
        variantClasses[variant],
        className,
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
