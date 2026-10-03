import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { de } from "@/lib/de";
import { afterLines, goesLines } from "@/lib/map/version-deletion";
import { useDeleteVersion } from "@/lib/queries/map-editor";
import { useVersionDeletion } from "@/lib/queries/map-graph";
import type { MapVersion } from "../../../types/mapTypes";

/**
 * "Version löschen" asks first (F14), like the map delete does (S19).
 *
 * It asks the server what goes before it offers the button, because only the
 * server can know: what is in this version and no other, which ballot pairs go
 * with it, which combinations keep its change — and whether it may go at all.
 * The base version, a map with a game running on it and a version a game has
 * already seen are refused, and the refusal is the server's own sentence; the
 * button is then not offered at all.
 *
 * The question is not asked again while the delete is under way: the delete
 * invalidates the version list, and a fresh look at a version that no longer
 * exists would answer 404 into the dialog a moment before it closes.
 */
export function DeleteVersionDialog({
  mapId,
  version,
  open,
  onOpenChange,
  onDeleting,
  onDeleted,
}: {
  mapId: string;
  version: MapVersion;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Just before the delete goes out — the editor stops showing this version. */
  onDeleting: () => void;
  onDeleted: () => void;
}) {
  const deleteMutation = useDeleteVersion(mapId);
  const settled = deleteMutation.isPending || deleteMutation.isSuccess;
  const deletion = useVersionDeletion(mapId, open ? version.id : null, !settled);

  const data = deletion.data;
  const refusal = data?.refusal ?? null;
  const goes = data ? goesLines(data.goes) : [];
  const after = data ? afterLines(data) : [];

  const handleDelete = () => {
    onDeleting();
    deleteMutation.mutate(version.id, {
      onSuccess: () => {
        onOpenChange(false);
        onDeleted();
      },
    });
  };

  const close = (next: boolean) => {
    if (deleteMutation.isPending) return;
    if (!next) deleteMutation.reset();
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{de.editor.version.deleteTitle(version.name)}</DialogTitle>
          <DialogDescription>{de.editor.version.deleteLead}</DialogDescription>
        </DialogHeader>

        {deletion.isLoading ? (
          <p className="text-sm text-muted-foreground">
            {de.editor.version.deleteAsking}
          </p>
        ) : null}

        {deletion.isError && !data ? (
          <Alert variant="destructive">
            <AlertDescription>{de.editor.version.deleteAskFailed}</AlertDescription>
          </Alert>
        ) : null}

        {refusal ? (
          <Alert variant="destructive">
            <AlertDescription>{refusal.detail}</AlertDescription>
          </Alert>
        ) : null}

        {data && !refusal ? (
          <div className="space-y-3 text-sm">
            {goes.length ? (
              <div>
                <p className="font-medium">{de.editor.version.deleteGoes}</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5">
                  {goes.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <p>{de.editor.version.deleteGoesNothing}</p>
            )}
            {after.map((line) => (
              <p key={line} className="text-muted-foreground">
                {line}
              </p>
            ))}
          </div>
        ) : null}

        {deleteMutation.isError ? (
          <Alert variant="destructive">
            <AlertDescription>
              {deleteMutation.error?.message || de.editor.version.deleteFailed}
            </AlertDescription>
          </Alert>
        ) : null}

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => close(false)}
            disabled={deleteMutation.isPending}
          >
            {refusal ? de.actions.close : de.actions.cancel}
          </Button>
          {data && !refusal ? (
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending || deleteMutation.isSuccess}
            >
              {deleteMutation.isPending
                ? de.editor.version.deleting
                : de.editor.version.deleteConfirm}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
