import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { de } from "@/lib/de";
import type { Persona, PersonaDraft } from "@/lib/game/personas";

/**
 * Which Pendlertypen a game deals, under the switch in the create form.
 *
 * The standard ones as a list of boxes, every one ticked until the host
 * unticks it, then the host's own with a way to take each out again, then a
 * row to write another. What is sent is `pickedPersonas`; the server says
 * what is wrong with it, under the list.
 *
 * The host's own are copies in this game only — the next create form offers
 * the standard ones again and nothing else.
 */
export function PersonaPicker({
  standard,
  loading,
  failed,
  unticked,
  onToggle,
  own,
  onAdd,
  onRemove,
  errors,
}: {
  standard: readonly Persona[];
  loading: boolean;
  failed: boolean;
  unticked: ReadonlySet<number>;
  onToggle: (id: number) => void;
  own: readonly PersonaDraft[];
  onAdd: (persona: PersonaDraft) => void;
  onRemove: (index: number) => void;
  errors?: string[];
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const trimmed = name.trim();

  function add() {
    if (!trimmed) return;
    onAdd({ name: trimmed, description: description.trim() });
    setName("");
    setDescription("");
  }

  /** Enter adds the row. Without this it would submit the whole form. */
  function onEnter(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    add();
  }

  return (
    <fieldset
      className="space-y-6 sm:col-span-2"
      aria-describedby={errors?.length ? "personas-error" : undefined}
    >
      <legend className="text-sm font-medium">{de.create.personasLegend}</legend>

      {loading ? (
        <p className="text-sm text-muted-foreground">{de.create.personasLoading}</p>
      ) : null}
      {failed ? (
        <p className="max-w-(--measure-body) border-l-2 border-brandaccent pl-3 text-sm">
          {de.create.personasFailed}
        </p>
      ) : null}

      {standard.length > 0 || own.length > 0 ? (
        <ul className="divide-y divide-border border-y border-border">
          {standard.map((persona) => (
            <li key={persona.id}>
              <label className="flex cursor-pointer items-start gap-3 py-3">
                <input
                  type="checkbox"
                  checked={!unticked.has(persona.id)}
                  onChange={() => onToggle(persona.id)}
                  className="mt-1 size-4 shrink-0 accent-primary"
                />
                <PersonaText persona={persona} />
              </label>
            </li>
          ))}
          {own.map((persona, index) => (
            <li
              // The host's own have no id until the game does; the list only
              // ever grows at the end and loses a row by its position.
              key={`${index}-${persona.name}`}
              className="flex items-start gap-3 py-3"
            >
              {/* Where the box is above, so the names line up. */}
              <span aria-hidden className="mt-1 size-4 shrink-0" />
              <PersonaText persona={persona} />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onRemove(index)}
                aria-label={de.create.personasRemoveLabel(persona.name)}
                className="ml-auto -mt-1"
              >
                {de.create.personasRemove}
              </Button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] sm:items-end">
        <div className="space-y-2">
          <Label htmlFor="persona_name">{de.create.personasOwnName}</Label>
          <Input
            id="persona_name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={onEnter}
            placeholder={de.create.personasOwnNamePlaceholder}
            autoComplete="off"
            maxLength={40}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="persona_description">
            {de.create.personasOwnDescription}
          </Label>
          <Input
            id="persona_description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            onKeyDown={onEnter}
            placeholder={de.create.personasOwnDescriptionPlaceholder}
            autoComplete="off"
            maxLength={200}
          />
        </div>
        <Button type="button" variant="outline" onClick={add} disabled={!trimmed}>
          {de.create.personasAdd}
        </Button>
      </div>

      {errors?.length ? (
        // Like `Field`'s: an amber rule beside ink text, read out when it
        // appears.
        <ul
          id="personas-error"
          role="alert"
          className="max-w-(--measure-body) space-y-1 border-l-[3px] border-brandaccent pl-4 text-sm text-foreground"
        >
          {errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      ) : null}
    </fieldset>
  );
}

function PersonaText({ persona }: { persona: PersonaDraft }) {
  return (
    <span className="min-w-0">
      <span className="font-medium">{persona.name}</span>
      {persona.description ? (
        <span className="block text-sm text-muted-foreground">
          {persona.description}
        </span>
      ) : null}
    </span>
  );
}
