const COLOR_MODE_STORAGE_KEY = "colorMode";

function getStoredColorMode(storageKey = COLOR_MODE_STORAGE_KEY) {
  try {
    const stored = window.localStorage.getItem(storageKey);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch (error) {
    console.warn("Unable to access localStorage for color mode:", error);
  }
  return null;
}

function getSystemColorScheme() {
  try {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
    return prefersDark.matches ? "dark" : "light";
  } catch (error) {
    console.warn("Unable to read system color scheme:", error);
    return "light";
  }
}

// Sync the user-agent color scheme preference into localStorage *and*
// set up reacting to system changes, but only if the user has not
// chosen an explicit mode.
function storeSystemColorScheme(storageKey = COLOR_MODE_STORAGE_KEY) {
  const storedMode = getStoredColorMode(storageKey);
  const systemScheme = getSystemColorScheme();

  // effective scheme: user choice wins, otherwise follow system
  const effectiveScheme =
    storedMode === "light" || storedMode === "dark" ? storedMode : systemScheme;

  // if nothing set yet, explicitly store "system" so we know the intent
  if (storedMode === null) {
    try {
      window.localStorage.setItem(storageKey, "system");
    } catch (error) {
      console.warn("Unable to store initial color mode:", error);
    }
  }

  // listen to system changes, but only apply them when mode === "system"
  try {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");

    const handler = (event) => {
      const currentMode = getStoredColorMode(storageKey);
      if (currentMode !== "system") {
        return; // user override exists, ignore system changes
      }
      const newScheme = event.matches ? "dark" : "light";
      setColorScheme(newScheme);
    };

    if (typeof prefersDark.addEventListener === "function") {
      prefersDark.addEventListener("change", handler);
    } else if ("onchange" in prefersDark) {
      prefersDark.onchange = handler;
    }
  } catch (error) {
    console.warn("Unable to subscribe to system color scheme changes:", error);
  }

  return effectiveScheme;
}

function setColorScheme(colorMode = "light") {
  const root = document.documentElement;
  if (colorMode === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

// toggle color mode
// mode: "light" | "dark" | "system"
function setUserColorMode(mode, storageKey = COLOR_MODE_STORAGE_KEY) {
  if (!["light", "dark", "system"].includes(mode)) {
    console.warn("Invalid color mode:", mode);
    return;
  }

  try {
    window.localStorage.setItem(storageKey, mode);
  } catch (error) {
    console.warn("Unable to store user color mode:", error);
  }

  const effectiveScheme = mode === "system" ? getSystemColorScheme() : mode;

  setColorScheme(effectiveScheme);
}

// init color scheme
