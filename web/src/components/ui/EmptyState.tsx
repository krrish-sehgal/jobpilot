import type { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 rounded-xl border border-dashed border-line px-6 py-12 text-center">
      {icon ? <div className="text-brand">{icon}</div> : null}
      <h2 className="font-display text-xl">{title}</h2>
      {children ? <p className="text-sm text-muted">{children}</p> : null}
      {action}
    </div>
  );
}
