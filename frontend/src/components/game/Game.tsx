import {
  Bars2Icon,
  ChatBubbleBottomCenterTextIcon,
  XMarkIcon,
} from "@heroicons/react/24/solid";

import { useState, useEffect } from "react";

import Header from "../Header";
import GamePlay from "./GamePlay";
import ChatSidebar from "../ChatSidebar";
import { useParams } from "@tanstack/react-router";

import Loading from "../Loading";
import { useAuth } from "../../context/AuthContext";
import GameStatSidebar from "./GameStatSidebar";
import { useGameSocket } from "../../hooks/useGameSocket";
import type { WSGameState } from "../../types/wsTypes";

const Game = () => {
  const [menu, setMenu] = useState(false);
  const [chat, setChat] = useState(false);
  const { isLoading, isError, isHost, isPlayer, auth } = useAuth();
  const { gameId } = useParams({ from: "/game/$gameId" });

  // Connect to game websocket
  useGameSocket({ gameId });

  // TODO: gameState will be populated when GameConsumer sends state updates
  const [gameState] = useState<WSGameState | null>(null);

  // Redirect to summary when game ends
  useEffect(() => {
    if (gameState?.ended_at) {
      window.location.href = `/game/${gameId}/summary/`;
    }
  }, [gameState?.ended_at, gameId]);

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
                <GameStatSidebar gameId={gameId} />
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
                    Error loading game
                  </div>
                ) : isPlayer || isHost ? (
                  <GamePlay
                    gameId={gameId}
                    playerId={auth?.player?.playerId}
                    isHost={isHost}
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
                  chatEnabled={gameState?.chat_enabled ?? true}
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

export default Game;
