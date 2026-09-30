(() => {
  const COLOR_MODE_STORAGE_KEY = "colorMode";
  const colorScheme = storeSystemColorScheme(COLOR_MODE_STORAGE_KEY);
  setColorScheme(colorScheme);

  // The header's flyouts are native popovers (`popovertarget` in base.html),
  // so light dismiss, Escape and one-open-at-a-time come from the browser.
  // They replaced @tailwindplus/elements, which was loaded from a CDN on every
  // page and handed each visitor's IP to it. What the platform does not do
  // everywhere yet is put a popover under its button — CSS anchor positioning
  // is Safari 26+ — so that is the one thing done here. It is placed on
  // `toggle`, after it opens, which the fade-in (from opacity 0) hides.
  const initHeaderPopovers = () => {
    const GAP = 12;
    const EDGE = 16;

    document.querySelectorAll("[popover][data-anchor-below]").forEach((panel) => {
      const button = document.querySelector(`[popovertarget="${panel.id}"]`);
      if (!button) {
        return;
      }

      const place = () => {
        const anchor = button.getBoundingClientRect();
        const width = panel.offsetWidth;
        const viewport = document.documentElement.clientWidth;
        const centred = anchor.left + anchor.width / 2 - width / 2;
        const left = Math.max(EDGE, Math.min(centred, viewport - width - EDGE));

        panel.style.top = `${anchor.bottom + GAP + window.scrollY}px`;
        panel.style.left = `${left + window.scrollX}px`;
      };

      panel.addEventListener("toggle", (event) => {
        if (event.newState === "open") {
          place();
        }
      });
      window.addEventListener("resize", () => {
        if (panel.matches(":popover-open")) {
          place();
        }
      });
    });
  };

  // The mobile menu is a native <dialog>: showModal() gives focus trapping,
  // Escape and the top layer. The buttons name it by data attribute rather
  // than the newer `command`/`commandfor`, which older iPads do not have.
  const initDialogs = () => {
    document.querySelectorAll("[data-dialog-open]").forEach((button) => {
      const dialog = document.getElementById(button.dataset.dialogOpen);
      if (!(dialog instanceof HTMLDialogElement)) {
        return;
      }

      button.addEventListener("click", () => {
        dialog.showModal();
        // The page behind a side panel must not scroll under a finger.
        document.documentElement.style.overflow = "hidden";
      });

      dialog.addEventListener("click", (event) => {
        const target = event.target;
        if (
          target instanceof Element &&
          (target.hasAttribute("data-dialog-backdrop") ||
            target.closest("[data-dialog-close]"))
        ) {
          dialog.close();
        }
      });

      // Escape closes it without passing through the click handler.
      dialog.addEventListener("close", () => {
        document.documentElement.style.overflow = "";
      });
    });
  };

  window.addEventListener("DOMContentLoaded", () => {
    initHeaderPopovers();
    initDialogs();
    initCookieBanner();
  });
})();

// Cookie Banner Implementation
const COOKIE_CONSENT_KEY = "co2mmute_cookie_consent";

const initCookieBanner = () => {
  // Check if user has already made a choice
  const hasConsent = localStorage.getItem(COOKIE_CONSENT_KEY);

  if (!hasConsent) {
    showCookieBanner();
  } else {
    updateLinksAvailability();
  }
};

const showCookieBanner = () => {
  const banner = document.createElement("div");
  banner.id = "cookie-banner";
  banner.className =
    "fixed bottom-0 left-0 right-0 bg-surface dark:bg-darksurface border-t border-subtle dark:border-darksubtle shadow-lg p-4 sm:p-6 z-40";

  banner.innerHTML = `
    <div class="max-w-7xl mx-auto">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex-1">
          <h3 class="font-semibold text-main dark:text-darktext mb-2">Cookie-Einstellungen</h3>
          <p class="text-sm text-muted dark:text-darkmutedtext">
            Wir verwenden notwendige Cookies für Session-Management, Spielfunktionalität und Theme-Einstellungen. 
            Mehr dazu findest du in unserer <a href="/legal/cookies/" class="text-primary-600 dark:text-primary-400 hover:underline">Cookie-Richtlinie</a>.
          </p>
        </div>
        <div class="flex gap-3 sm:shrink-0">
          <button 
            id="cookie-accept" 
            class="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-lg whitespace-nowrap"
          >
            Akzeptieren
          </button>
          <button 
            id="cookie-decline" 
            class="px-4 py-2 border border-subtle dark:border-darksubtle text-main dark:text-darktext font-medium rounded-lg hover:bg-elevated dark:hover:bg-darkelevated whitespace-nowrap"
          >
            Ablehnen
          </button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(banner);

  document.getElementById("cookie-accept").addEventListener("click", () => {
    acceptCookies();
  });

  document.getElementById("cookie-decline").addEventListener("click", () => {
    declineCookies();
  });
};

const acceptCookies = () => {
  localStorage.setItem(COOKIE_CONSENT_KEY, "accepted");
  removeCookieBanner();
  updateLinksAvailability();
};

const declineCookies = () => {
  localStorage.setItem(COOKIE_CONSENT_KEY, "declined");
  removeCookieBanner();
  updateLinksAvailability();
};

const removeCookieBanner = () => {
  const banner = document.getElementById("cookie-banner");
  if (banner) {
    banner.remove();
  }
};

const updateLinksAvailability = () => {
  const consent = localStorage.getItem(COOKIE_CONSENT_KEY);

  if (consent === "declined") {
    // Disable functionality links
    const functionalityLinks = [
      'a[href*="create"]',
      'a[href*="join"]',
      'a[href*="profile"]',
    ];

    functionalityLinks.forEach((selector) => {
      document.querySelectorAll(selector).forEach((link) => {
        // Only disable if it's not a legal link
        if (!link.href.includes("legal") && !link.href.includes("admin")) {
          link.addEventListener("click", (e) => {
            e.preventDefault();
            alert(
              "Du musst den notwendigen Cookies zustimmen, um diese Funktionen zu nutzen."
            );
          });
          link.style.pointerEvents = "none";
          link.style.opacity = "0.5";
        }
      });
    });
  }
};

// Expose cookie consent status globally for other scripts
window.isCookieConsented = () => {
  const consent = localStorage.getItem(COOKIE_CONSENT_KEY);
  return consent === "accepted";
};
