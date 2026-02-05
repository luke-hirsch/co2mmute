import { useParams } from "@tanstack/react-router";
import {
  Bars2Icon,
  ChatBubbleBottomCenterTextIcon,
  XMarkIcon,
} from "@heroicons/react/24/solid";

import { useState, useEffect } from "react";

import Header from "./../../components/Header";
import Game from "./../../components/game/Game";
import GameDetail from "./../../components/game/GameDetail";
import ChatSidebar from "./../../components/ChatSidebar";

import Loading from "./../../components/Loading";
import { useAuth } from "../../context/AuthContext";
import { useGameSocket } from "../../hooks/useGameSocket";
import { useGameDetails, usePlayerGameDetails, usePlayerDetail } from "../../hooks/gameHooks";
import StatusBar from "../../components/game/StatusBar";
import type { PlayerAgentAssignments } from "../../types/types";

const GameLayout = () => {
  const { gameId } = useParams({ from: "/game/$gameId" });
  const [menu, setMenu] = useState(false);
  const [chat, setChat] = useState(false);
  const { isLoading, isError, isHost, isPlayer, auth } = useAuth();

  // Connect to game websocket and receive game state updates
  const { gameState } = useGameSocket({ gameId });

  // Fetch REST game data for chat_enabled (not in websocket state)
  const hostGameData = useGameDetails(gameId, isHost);
  const playerGameData = usePlayerGameDetails(
    gameId,
    auth?.player?.playerId || "",
    isPlayer && !!auth?.player?.playerId,
  );
  const restGameData = isHost ? hostGameData.data : playerGameData.data;

  // Fetch player details for agent assignments
  const playerDetailData = usePlayerDetail(
    gameId,
    auth?.player?.playerId || "",
    isPlayer && !!auth?.player?.playerId,
  );
  const agentAssignments = playerDetailData.data?.agent_assignments as PlayerAgentAssignments | undefined;

  // Redirect to summary when game ends
  useEffect(() => {
    if (gameState?.endedAt) {
      window.location.href = `/game/${gameId}/summary/`;
    }
  }, [gameState?.endedAt, gameId]);
  return (
    <div className="min-h-svh min-w-full max-w-screen bg-body dark:bg-darkbody dark:text-darktext overflow-hidden">
      <div className="lg:hidden absolute top p-2 w-screen flex justify-between">
        <Bars2Icon
          className={`w-10 h-10 cursor-pointer dark:text-darktext text-main transition-all duration-300 ${menu || chat ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-75"}`}
          onClick={() => setMenu(true)}
        />

        <XMarkIcon
          className={`w-10 h-10 cursor-pointer dark:text-darktext text-main transition-all duration-300 ${menu ? "opacity-100 z-85 " : "z-0 opacity-0 -translate-x-full"}`}
          onClick={() => setMenu(false)}
        />
      </div>
      <div className="lg:hidden absolute top p-2 w-screen flex justify-between">
        <XMarkIcon
          className={`w-10 h-10 cursor-pointer dark:text-darktext text-main transition-all duration-300 ${chat ? "opacity-100 z-85" : "z-0 opacity-0 translate-x-full"}`}
          onClick={() => setChat(false)}
        />
        <ChatBubbleBottomCenterTextIcon
          className={`w-10 h-10 cursor-pointer dark:text-darktext text-main transition-all duration-300 ${chat || menu ? "z-0 opacity-0 translate-x-full" : "opacity-100 z-75"}`}
          onClick={() => setChat(true)}
        />
      </div>

      {/* Centering container */}
      <div className="flex justify-center items-center min-h-full max-h-full w-full overflow-hidden">
        <div className="flex max-h-svh min-h-svh w-screen bg-inherit p-4">
          {/* Sidebar left*/}
          <div className=" max-h-svh overflow-hidden">
            {isHost || isPlayer ? (
              <aside
                className={`absolute lg:relative min-h-full left-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${menu ? "translate-x-0" : "-translate-x-60"} transition-all duration-300 h-full rounded z-50`}
              >
                <StatusBar gameId={gameId} />
              </aside>
            ) : (
              <></>
            )}
          </div>
          <div className="flex flex-1 max-h-svh w-screen overflow-hidden">
            {/* Main content */}
            <div className="relative flex-1 max-h-svh overflow-y-auto">
              <Header title={`Game - ${gameId}`} />
              <main className="flex-1 p-6 dark:text-darktext flex flex-col items-center justify-start max-w-screen min-h-full">
                {isLoading ? (
                  <Loading />
                ) : isError ? (
                  <div className="text-red-600 dark:text-red-400">
                    Error loading game content
                  </div>
                ) : isHost ? (
                  <GameDetail
                    id={gameId}
                    role="host"
                  />
                ) : isPlayer ? (
                  <Game
                    gameId={gameId}
                    gameState={gameState}
                    playerId={auth?.player?.playerId}
                    isHost={false}
                    agentCount={restGameData?.agent_per_player ?? 4}
                    mapId={restGameData?.game_map}
                    agentAssignments={agentAssignments}
                  />
                ) : (
                  <div>Unauthorized</div>
                )}
              </main>
            </div>

            {/* Sidebar right */}
            {isHost || isPlayer ? (
              <aside
                className={`absolute lg:relative right-0 top-0 w-60 dark:bg-inherit bg-body flex lg:translate-x-0 ${chat ? "translate-x-0" : "translate-x-60"} transition-all duration-300 h-full rounded z-50`}
              >
                <ChatSidebar
                  gameId={gameId}
                  chatEnabled={restGameData?.chat_enabled ?? true}
                />
              </aside>
            ) : (
              <></>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GameLayout;
