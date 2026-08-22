import { ReactNode } from "react";

/**
 * What a panel shows when it has nothing to show.
 *
 * A bare "nothing here" wastes the exact moment someone is asking what to
 * do next, which is the moment they are most likely to give up. Every use
 * of this names what is missing and offers the action that produces it.
 */
export function EmptyState({
  icon,
  title,
  children,
  actions,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="empty">
      {icon && <span className="empty-icon" aria-hidden="true">{icon}</span>}
      <h3>{title}</h3>
      {/* A div, not a <p>: some callers pass an ordered list of what to do
          next, and a list inside a paragraph is invalid HTML. */}
      {children && <div className="empty-text">{children}</div>}
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

/* Icons live here rather than in each caller so the empty states stay
   visually consistent with one another. */

export const IconSearch = (
  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
    <circle cx="8.6" cy="8.6" r="5.4" />
    <path d="M12.6 12.6L17 17" strokeLinecap="round" />
  </svg>
);

export const IconArchive = (
  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
    <rect x="2.8" y="3.4" width="14.4" height="4" rx="1" />
    <path d="M4.3 7.4v8a1 1 0 001 1h9.4a1 1 0 001-1v-8" />
    <path d="M8 10.6h4" strokeLinecap="round" />
  </svg>
);

export const IconPhone = (
  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
    <rect x="5.5" y="2.2" width="9" height="15.6" rx="1.8" />
    <path d="M8.8 15.2h2.4" strokeLinecap="round" />
  </svg>
);

export const IconClock = (
  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
    <circle cx="10" cy="10" r="7.2" />
    <path d="M10 5.8V10l2.8 1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
