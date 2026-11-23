import type { ReactNode } from "react";

export function Loading({ text = "Loading" }: { text?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry, children }: { message: string; onRetry?: () => void; children?: ReactNode }) {
  return (
    <div className="state error" role="alert">
      <strong>That did not work.</strong>
      <span>{message}</span>
      {onRetry && <button className="btn secondary" onClick={onRetry}>Try again</button>}
      {children}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state empty">
      <strong>{title}</strong>
      {children}
    </div>
  );
}
