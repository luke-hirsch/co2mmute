import { NavLink } from "@/components/layout/nav-link";
import { de } from "@/lib/de";
import { useNavigation } from "@/lib/queries/navigation";

/**
 * The footer `base.html` has always had, which the SPA never did — so no screen
 * under `/app/` linked to the Impressum, the Datenschutz page or the Cookies
 * page. The legal links come first in the list and are fixed on the server; the
 * repository is last. Like the header it stays off the game screens, which own
 * their viewport.
 */
export function AppFooter() {
  const navigation = useNavigation();

  return (
    <footer className="border-t border-border bg-card">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-10 lg:px-8">
        <p className="text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} {de.app.name}
        </p>
        <nav aria-label={de.app.footer.label} className="flex flex-wrap gap-x-6 gap-y-2">
          {navigation.data?.footer.map((item) => (
            <NavLink
              key={item.id}
              item={item}
              className="text-sm text-muted-foreground transition hover:text-foreground"
            />
          ))}
        </nav>
      </div>
    </footer>
  );
}
