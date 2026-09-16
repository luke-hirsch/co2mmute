import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names, last conflicting Tailwind utility wins. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
