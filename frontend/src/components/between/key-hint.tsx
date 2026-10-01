/** The key that casts a vote (S24). Meaningless on a phone, so not drawn there. */
export function KeyHint({ children }: { children: number | string }) {
  return (
    <kbd className="ml-2 hidden rounded border border-current/30 px-1.5 font-mono text-xs opacity-70 sm:inline-block">
      {children}
    </kbd>
  );
}
