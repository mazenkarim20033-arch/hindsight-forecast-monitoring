import type { ReactNode } from "react";
import type { Problem } from "../hooks/useAsync";
import { useLang, useServerText } from "../i18n";

export function Loading({ text }: { text?: string }) {
  const { t } = useLang();
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{text ?? t("state.loading")}</span>
    </div>
  );
}

export function ErrorBox({ problem, onRetry, children }: { problem: Problem; onRetry?: () => void; children?: ReactNode }) {
  const { t } = useLang();
  const say = useServerText();
  return (
    <div className="state error" role="alert">
      <strong>{t("state.failed")}</strong>
      <span>{say(problem, "problem")}</span>
      {onRetry && <button className="btn secondary" onClick={onRetry}>{t("state.retry")}</button>}
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
