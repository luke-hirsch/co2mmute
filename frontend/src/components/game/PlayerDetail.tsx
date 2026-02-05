import { useState } from "react";
import { type WSPlayer } from "../../types/wsTypes";
import { API_BASE_URL } from "../../config";
import { apiFetch } from "../../utils/api";
import ConfirmDialog from "../ConfirmDialog";

interface PlayerDetailProps {
  player: WSPlayer;
  gameId: string;
  onClose: () => void;
  onPlayerUpdated?: () => void;
  onPlayerKicked?: () => void;
}

const PlayerDetail = ({
  player,
  gameId,
  onClose,
  onPlayerUpdated,
  onPlayerKicked,
}: PlayerDetailProps) => {
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState(player.name);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showKickConfirm, setShowKickConfirm] = useState(false);
  const [isKicking, setIsKicking] = useState(false);

  const handleSaveName = async () => {
    if (!editedName.trim() || editedName === player.name) {
      setIsEditingName(false);
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const data = await apiFetch(
        `${API_BASE_URL}/api/game/${gameId}/player/${player.playerId}/`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: editedName.trim() }),
        },
      );

      if (data && typeof data === "object" && "error" in data) {
        setError(data.error || "Failed to update name");
        return;
      }

      setIsEditingName(false);
      onPlayerUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update name");
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleMute = async () => {
    setError(null);

    try {
      const data = await apiFetch(
        `${API_BASE_URL}/api/game/${gameId}/player/${player.playerId}/mute/`,
        {
          method: "POST",
        },
      );

      if (data && typeof data === "object" && "error" in data) {
        setError(data.error || "Failed to toggle mute");
        return;
      }

      onPlayerUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to toggle mute");
    }
  };

  const handleKickPlayer = async () => {
    setIsKicking(true);
    setError(null);

    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/game/${gameId}/player/${player.playerId}/?kicked=true`,
        {
          method: "DELETE",
        },
      );

      if (response && typeof response === "object" && "error" in response) {
        setError(response.error || "Failed to remove player");
        setShowKickConfirm(false);
        return;
      }

      setShowKickConfirm(false);
      onPlayerKicked?.();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove player");
      setShowKickConfirm(false);
    } finally {
      setIsKicking(false);
    }
  };

  return (
    <>
      <div className="rounded-lg border border-subtle bg-elevated p-6 dark:border-darksubtle dark:bg-darkelevated">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-main dark:text-darktext">
            Player Details
          </h2>
          <button
            onClick={onClose}
            className="text-muted hover:text-main dark:text-darkmutedtext dark:hover:text-darktext"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded bg-red-100 p-3 text-sm text-red-700 dark:bg-red-900 dark:text-red-200">
            {error}
          </div>
        )}

        {/* Player Name */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-semibold text-muted dark:text-darkmutedtext">
              Name
            </label>
            {!isEditingName && (
              <button
                onClick={() => {
                  setIsEditingName(true);
                  setEditedName(player.name);
                }}
                className="text-xs font-semibold text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
              >
                Edit
              </button>
            )}
          </div>

          {isEditingName ? (
            <div className="space-y-2">
              <input
                type="text"
                value={editedName}
                onChange={(e) => setEditedName(e.target.value)}
                className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="Player name"
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  onClick={() => setIsEditingName(false)}
                  className="flex-1 rounded px-3 py-1 text-xs font-semibold text-main hover:bg-surface dark:text-darktext dark:hover:bg-darksurface"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveName}
                  disabled={isSaving}
                  className="flex-1 rounded bg-primary-600 px-3 py-1 text-xs font-semibold text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {isSaving ? "Saving..." : "Save"}
                </button>
              </div>
            </div>
          ) : (
            <p className="text-lg font-medium text-main dark:text-darktext">
              {player.name}
            </p>
          )}
        </div>

        {/* Player ID */}
        <div className="mb-6">
          <label className="text-sm font-semibold text-muted dark:text-darkmutedtext mb-2 block">
            Player ID
          </label>
          <code className="text-sm font-mono text-primary-600">
            {player.playerId}
          </code>
        </div>

        {/* Joined At */}
        <div className="mb-6">
          <label className="text-sm font-semibold text-muted dark:text-darkmutedtext mb-2 block">
            Joined
          </label>
          <p className="text-sm text-main dark:text-darktext">
            {new Date(player.joinedAt).toLocaleString()}
          </p>
        </div>

        {/* Online Status */}
        <div className="mb-6">
          <label className="text-sm font-semibold text-muted dark:text-darkmutedtext mb-2 block">
            Status
          </label>
          <div className="flex items-center gap-2">
            <div
              className={`h-2 w-2 rounded-full ${player.online ? "bg-green-500" : "bg-gray-400"}`}
            />
            <span className="text-sm text-main dark:text-darktext">
              {player.online ? "Online" : "Offline"}
            </span>
          </div>
        </div>

        {/* Mute Toggle */}
        <div className="mb-6">
          <label className="text-sm font-semibold text-muted dark:text-darkmutedtext mb-2 block">
            Chat Access
          </label>
          <button
            onClick={handleToggleMute}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              !player.isMuted ? "bg-green-600" : "bg-gray-300 dark:bg-gray-600"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                !player.isMuted ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
          <p className="mt-1 text-xs text-muted dark:text-darkmutedtext">
            {player.isMuted
              ? "Player is muted and cannot send chat messages"
              : "Player can send chat messages"}
          </p>
        </div>

        {/* Kick Button */}
        <div className="pt-4 border-t border-subtle dark:border-darksubtle">
          <button
            onClick={() => setShowKickConfirm(true)}
            className="w-full rounded bg-red-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-700"
          >
            Remove from Game
          </button>
          <p className="mt-2 text-xs text-muted dark:text-darkmutedtext text-center">
            This player will not be able to rejoin
          </p>
        </div>
      </div>

      {/* Kick Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showKickConfirm}
        title="Remove Player"
        message={`Are you sure you want to remove ${player.name} from the game? They will not be able to rejoin.`}
        confirmLabel={isKicking ? "Removing..." : "Remove Player"}
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={handleKickPlayer}
        onCancel={() => setShowKickConfirm(false)}
      />
    </>
  );
};

export default PlayerDetail;
