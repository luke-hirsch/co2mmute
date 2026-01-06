(() => {
  const COLOR_MODE_STORAGE_KEY = "colorMode";
  const colorScheme = storeSystemColorScheme(COLOR_MODE_STORAGE_KEY);
  setColorScheme(colorScheme);

  const initMobileMenus = () => {
    const toggleButtons = document.querySelectorAll(
      '[command="--toggle"][commandfor]'
    );

    toggleButtons.forEach((button) => {
      const targetId = button.getAttribute("commandfor");
      if (!targetId) {
        return;
      }

      const target = document.getElementById(targetId);
      if (!target) {
        return;
      }

      const isHidden = target.hasAttribute("hidden");
      button.setAttribute("aria-controls", targetId);
      button.setAttribute("aria-expanded", isHidden ? "false" : "true");

      button.addEventListener("click", (event) => {
        event.preventDefault();
        const currentlyHidden = target.hasAttribute("hidden");

        if (currentlyHidden) {
          target.removeAttribute("hidden");
          button.setAttribute("aria-expanded", "true");
        } else {
          target.setAttribute("hidden", "");
          button.setAttribute("aria-expanded", "false");
        }
      });
    });
  };

  const initDropdowns = () => {
    const dropdowns = document.querySelectorAll("el-dropdown");
    if (!dropdowns.length) {
      return;
    }

    const closeDropdown = (dropdown) => {
      const button = dropdown.querySelector("button");
      const menu = dropdown.querySelector("el-menu");
      if (!button || !menu) {
        return;
      }

      menu.setAttribute("hidden", "");
      menu.dataset.state = "closed";
      button.setAttribute("aria-expanded", "false");
      dropdown.dataset.state = "closed";
    };

    const openDropdown = (dropdown) => {
      const button = dropdown.querySelector("button");
      const menu = dropdown.querySelector("el-menu");
      if (!button || !menu) {
        return;
      }

      menu.removeAttribute("hidden");
      menu.dataset.state = "open";
      button.setAttribute("aria-expanded", "true");
      dropdown.dataset.state = "open";
    };

    const closeAll = (exception) => {
      dropdowns.forEach((dropdown) => {
        if (exception && dropdown === exception) {
          return;
        }
        closeDropdown(dropdown);
      });
    };

    dropdowns.forEach((dropdown) => {
      const button = dropdown.querySelector("button");
      const menu = dropdown.querySelector("el-menu");
      if (!button || !menu) {
        return;
      }

      closeDropdown(dropdown);
      button.setAttribute("aria-haspopup", "menu");

      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();

        const isExpanded = button.getAttribute("aria-expanded") === "true";
        if (isExpanded) {
          closeDropdown(dropdown);
        } else {
          closeAll(dropdown);
          openDropdown(dropdown);
        }
      });

      menu.addEventListener("click", (event) => {
        const target = event.target;
        if (
          target instanceof HTMLElement &&
          (target.matches("a") || target.matches("button"))
        ) {
          closeDropdown(dropdown);
        }
      });
    });

    document.addEventListener("click", (event) => {
      dropdowns.forEach((dropdown) => {
        if (!dropdown.contains(event.target)) {
          closeDropdown(dropdown);
        }
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeAll();
      }
    });
  };

  window.addEventListener("DOMContentLoaded", () => {
    initMobileMenus();
    initDropdowns();
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
            Lesen Sie mehr in unserer <a href="{% url 'cookies' %}" class="text-primary-600 dark:text-primary-400 hover:underline">Cookie-Richtlinie</a>.
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
              "Sie müssen den notwendigen Cookies zustimmen, um diese Funktionen zu nutzen."
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
