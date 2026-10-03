import { Fragment, useEffect, useRef } from "react";

import { Lockup } from "@/components/layout/lockup";
import { NavLink } from "@/components/layout/nav-link";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { placeBelow, startsLanguageGroup } from "@/lib/nav-href";
import { type NavItem, useNavigation } from "@/lib/queries/navigation";

/**
 * The header, the same one `base.html` draws.
 *
 * It used to be a wordmark and a profile link and nothing else, next to a
 * Django header with the whole navigation — so a host went from a page that
 * offered the map menu and a way to sign out to one that offered neither. Both
 * now render the list from `api/navigation/` with the same markup and widths:
 * `max-w-7xl` and a `px-4 sm:px-6 lg:px-8` gutter *inside* it. `Screen` puts
 * its gutter outside its column, which is what made this header sit 24 px
 * inside the page on every screen that has one.
 *
 * The flyouts and the phone menu are the platform's own `popover` and
 * `<dialog>`, as on the Django side — light dismiss, Escape and focus come from
 * the browser. `showsAppChrome` decides where this renders.
 */
export function AppHeader() {
  const navigation = useNavigation();
  const nav = navigation.data;
  const dialog = useRef<HTMLDialogElement>(null);

  function openMenu() {
    dialog.current?.showModal();
    // The page behind a side panel must not scroll under a finger.
    document.documentElement.style.overflow = "hidden";
  }

  function closeMenu() {
    dialog.current?.close();
  }

  return (
    <header className="border-b border-border bg-card text-foreground">
      <nav
        aria-label={de.app.header.label}
        className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-4 py-5 sm:px-6 lg:px-8"
      >
        <div className="flex lg:flex-1">
          <a href="/" className="-m-1.5 p-1.5 text-foreground">
            <Lockup />
          </a>
        </div>

        <div className="flex lg:hidden">
          <button
            type="button"
            onClick={openMenu}
            aria-haspopup="dialog"
            aria-controls="mobile-menu"
            className="-m-2.5 inline-flex items-center justify-center rounded-md p-2.5"
          >
            <span className="sr-only">{de.app.header.menu}</span>
            <MenuIcon />
          </button>
        </div>

        {/* Nothing is rendered while the list is in flight: an item that
            appears a beat late is fine, one that appears and vanishes is not. */}
        <div className="hidden lg:flex lg:items-center lg:gap-x-10">
          {nav?.header.map((item) =>
            item.children?.length ? (
              <Flyout key={item.id} item={item} />
            ) : (
              <NavLink key={item.id} item={item} className={TOP_LINK} />
            ),
          )}
        </div>

        <div className="hidden lg:flex lg:flex-1 lg:items-center lg:justify-end lg:gap-x-6">
          {nav?.account ? (
            <NavLink item={nav.account} className={TOP_LINK} />
          ) : null}
          {nav ? (
            <a href={nav.session.href ?? "/"} className={TOP_LINK}>
              {nav.session.label} <span aria-hidden="true">&rarr;</span>
            </a>
          ) : null}
        </div>
      </nav>

      <dialog
        ref={dialog}
        id="mobile-menu"
        aria-label={de.app.header.menu}
        className="backdrop:bg-transparent lg:hidden"
        onClose={() => {
          document.documentElement.style.overflow = "";
        }}
      >
        <div
          tabIndex={0}
          className="fixed inset-0 focus:outline-none"
          onClick={(event) => {
            if (event.target === event.currentTarget) closeMenu();
          }}
        >
          <div className="fixed inset-y-0 right-0 z-50 w-full overflow-y-auto bg-card px-4 py-5 text-foreground sm:max-w-sm sm:px-6 sm:ring-1 sm:ring-border">
            <div className="flex items-center justify-between">
              <a href="/" className="-m-1.5 p-1.5 text-foreground">
                <Lockup />
              </a>
              <button
                type="button"
                onClick={closeMenu}
                className="-m-2.5 rounded-md p-2.5"
              >
                <span className="sr-only">{de.app.header.closeMenu}</span>
                <CloseIcon />
              </button>
            </div>
            <div className="mt-6 flow-root">
              <div className="-my-6 divide-y divide-border">
                <div className="space-y-2 py-6">
                  {nav?.header.map((item) =>
                    item.children?.length ? (
                      <details key={item.id} className="group -mx-3">
                        <summary className="flex w-full cursor-pointer list-none items-center justify-between rounded-lg py-2 pr-3.5 pl-3 text-base/7 font-medium transition hover:bg-muted [&::-webkit-details-marker]:hidden">
                          {item.label}
                          <Chevron className="group-open:rotate-180" />
                        </summary>
                        <div className="mt-2 space-y-2">
                          {item.children.map((child, index, children) => (
                            <Fragment key={child.id}>
                              {startsLanguageGroup(children, index) ? (
                                <hr className="ml-6 border-border" />
                              ) : null}
                              <NavLink
                                item={child}
                                onFollow={closeMenu}
                                className="block rounded-lg py-2 pr-3 pl-6 text-sm/7 font-medium transition hover:bg-muted"
                              />
                            </Fragment>
                          ))}
                        </div>
                      </details>
                    ) : (
                      <div key={item.id} className="-mx-3">
                        <NavLink
                          item={item}
                          onFollow={closeMenu}
                          className="block rounded-lg py-2 pr-3.5 pl-3 text-base/7 font-medium transition hover:bg-muted"
                        />
                      </div>
                    ),
                  )}
                </div>
                <div className="py-6">
                  {nav?.account ? (
                    <NavLink
                      item={nav.account}
                      onFollow={closeMenu}
                      className={MENU_ROW}
                    />
                  ) : null}
                  {nav ? (
                    <NavLink item={nav.session} className={MENU_ROW} />
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </div>
      </dialog>
    </header>
  );
}

const TOP_LINK =
  "text-sm/6 font-medium text-foreground transition hover:text-primary";

const MENU_ROW =
  "-mx-3 block rounded-lg px-3 py-2.5 text-base/7 font-medium transition hover:bg-muted";

/**
 * A menu under a button. The panel is a native popover, and is put under its
 * button on `toggle` — after it opens, which the fade-in from opacity 0 hides.
 */
function Flyout({ item }: { item: NavItem }) {
  const id = `nav-${item.id}`;
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const target = panel.current;
    const anchor = button.current;
    if (!target || !anchor) return;

    const place = () => {
      const { top, left } = placeBelow(
        anchor.getBoundingClientRect(),
        target.offsetWidth,
        document.documentElement.clientWidth,
      );
      target.style.top = `${top + window.scrollY}px`;
      target.style.left = `${left + window.scrollX}px`;
    };
    const onToggle = (event: Event) => {
      if ((event as ToggleEvent).newState === "open") place();
    };
    const onResize = () => {
      if (target.matches(":popover-open")) place();
    };

    target.addEventListener("toggle", onToggle);
    window.addEventListener("resize", onResize);
    return () => {
      target.removeEventListener("toggle", onToggle);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <div className="relative">
      <button
        ref={button}
        type="button"
        popoverTarget={id}
        className="flex items-center gap-x-1 text-sm/6 font-medium text-foreground transition hover:text-primary"
      >
        {item.label}
        <Chevron />
      </button>
      <div
        ref={panel}
        id={id}
        popover="auto"
        className="absolute inset-auto m-0 w-56 translate-y-1 rounded-lg border border-border bg-card p-2 text-foreground opacity-0 shadow-sm transition transition-discrete duration-150 ease-out open:translate-y-0 open:opacity-100 starting:open:translate-y-1 starting:open:opacity-0"
      >
        {item.children?.map((child, index, children) => (
          <Fragment key={child.id}>
            {startsLanguageGroup(children, index) ? (
              <hr className="mx-3 my-2 border-border" />
            ) : null}
            <NavLink
              item={child}
              onFollow={() => panel.current?.hidePopover()}
              className="block rounded-md px-3 py-2 text-sm/6 font-medium transition hover:bg-muted"
            />
          </Fragment>
        ))}
      </div>
    </div>
  );
}

/*
 * The same three icons, path for path, that `base.html` draws. They were
 * lucide's here and heroicons' there, and side by side the menu bars were
 * visibly a different weight — the one place the two headers still differed.
 */

function MenuIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
      className="size-6"
    >
      <path
        d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
      className="size-6"
    >
      <path
        d="M6 18 18 6M6 6l12 12"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Chevron({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden="true"
      className={cn(
        "size-5 flex-none text-soft dark:text-darksofttext",
        className,
      )}
    >
      <path
        d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
        fillRule="evenodd"
        clipRule="evenodd"
      />
    </svg>
  );
}
