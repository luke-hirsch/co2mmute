import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";

/**
 * A labelled control with its help text and the server's refusals under it.
 *
 * Out of the create form since S19, when the map upload became the second
 * form in the SPA that renders a Django form's errors field by field.
 */
export function Field({
  id,
  label,
  help,
  errors,
  children,
}: {
  id: string;
  label: string;
  help?: string;
  errors?: string[];
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {help ? (
        <p
          id={`${id}-help`}
          className="max-w-(--measure-body) text-sm text-muted-foreground"
        >
          {help}
        </p>
      ) : null}
      {errors?.length ? (
        // `role="alert"` so a screen reader hears the refusal when it appears,
        // and `id` so the input can point at it — both of which also make it
        // something a test can find without pinning the sentence.
        //
        // An amber rule beside ink text, not amber text: amber on the light
        // ground is hard to read, which the map notes found first (S19). The
        // Django pages' `field-error` is the same thing (S22).
        <ul
          id={`${id}-error`}
          role="alert"
          className="max-w-(--measure-body) space-y-1 border-l-[3px] border-brandaccent pl-4 text-sm text-foreground"
        >
          {errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

