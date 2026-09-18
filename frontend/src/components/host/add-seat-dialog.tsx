import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { de, type HostRefusal } from "@/lib/de";
import { useAddSeat } from "@/lib/queries/seats";

/**
 * The host adds a seat played at this machine (1.6, H-02 / L-10).
 *
 * A name and nothing else — that is the whole of what this project collects
 * from a player, and it stays that way for a seat the teacher types in as much
 * as for one somebody joins with.
 *
 * Nothing is refetched afterwards: `add_seat` broadcasts the roster, so the new
 * seat arrives over the socket like every other change. The dialog only has to
 * close.
 *
 * Allowed during a running game too, and deliberately so — a seat added mid
 * round is waited for in that round (`game/seats.py`), which is exactly what a
 * teacher needs when somebody walks in late or the bell has just rung (P-06).
 */
export function AddSeatDialog({ gameId }: { gameId: string }) {
  const add = useAddSeat(gameId);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  function close(next: boolean) {
    setOpen(next);
    if (!next) {
      setName("");
      setError(null);
      add.reset();
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError(de.join.nameRequired);
      return;
    }
    setError(null);
    try {
      await add.mutateAsync(trimmed);
      close(false);
    } catch (failure) {
      setError(addFailure(failure));
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogTrigger asChild>
        <Button variant="outline">{de.host.add}</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{de.host.addTitle}</DialogTitle>
          <DialogDescription>{de.host.addBody}</DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} noValidate className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="seat-name">{de.host.addName}</Label>
            <Input
              id="seat-name"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                if (error) setError(null);
              }}
              placeholder={de.join.namePlaceholder}
              autoFocus
              autoComplete="off"
              maxLength={40}
              aria-invalid={error ? true : undefined}
            />
          </div>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => close(false)}>
              {de.actions.cancel}
            </Button>
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? de.host.adding : de.host.addSubmit}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function addFailure(error: unknown): string {
  if (error instanceof ApiError && error.status === 409 && error.reason) {
    const known = de.host.failed[error.reason as HostRefusal];
    if (known) return known;
  }
  if (error instanceof ApiError && error.status === 400) {
    return de.join.nameRequired;
  }
  return de.host.failedUnknown;
}
