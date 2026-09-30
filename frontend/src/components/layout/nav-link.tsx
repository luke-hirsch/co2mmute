import type { MouseEvent } from "react";
import { useNavigate } from "@tanstack/react-router";

import { routerPath } from "@/lib/nav-href";
import type { NavItem } from "@/lib/queries/navigation";

/**
 * One item from `api/navigation/`, as the server described it.
 *
 * Always a real `<a href>`, so a middle click, a long press and a screen
 * reader all see a link. A plain left click on an href inside the SPA is taken
 * over and handed to the router — the screen is already loaded, and leaving
 * the document to come straight back into it is a full reload for nothing.
 * `onFollow` runs on every click, which is how a menu closes itself.
 */
export function NavLink({
  item,
  className,
  onFollow,
}: {
  item: NavItem;
  className?: string;
  onFollow?: () => void;
}) {
  const navigate = useNavigate();

  if (!item.href) return <span className={className}>{item.label}</span>;

  const inApp = routerPath(item.href);

  function follow(event: MouseEvent<HTMLAnchorElement>) {
    onFollow?.();
    if (inApp === null || event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    void navigate({ href: inApp });
  }

  return (
    <a href={item.href} className={className} onClick={follow}>
      {item.label}
    </a>
  );
}
