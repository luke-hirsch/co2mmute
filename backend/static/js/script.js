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
  });
})();
