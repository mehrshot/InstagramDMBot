// Small per-browser flags. Wrapped because storage can be unavailable (private mode etc.).

export function getFlag(key: string): boolean {
  try {
    return localStorage.getItem(`dm.flag.${key}`) === "1";
  } catch {
    return false;
  }
}

export function setFlag(key: string) {
  try {
    localStorage.setItem(`dm.flag.${key}`, "1");
  } catch {
    // ignore
  }
}

/** Checklist step "test the bot" is done after the first playground reply (per shop). */
export const playgroundKey = (shopId: string) => `playground-tried.${shopId}`;
