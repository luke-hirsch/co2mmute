import { useGameDetails, usePlayerGameDetails } from "../../hooks/gameHooks";
import Loading from "../Loading";
// import { redirect } from "@tanstack/react-router";

interface GameDetailProps {
  id: string;
  role: "host" | "player";
  playerId?: string;
}
export default function GameDetail({ id, role, playerId }: GameDetailProps) {
  let gameData;
  if (role === "player" && playerId) {
    gameData = usePlayerGameDetails(id, playerId);
  } else if (role === "host") {
    gameData = useGameDetails(id);
  } else throw new Error("Invalid role");

  if (gameData.isLoading) return <Loading />;
  if (gameData.isError) return (window.location.href = "/");
  console.log(gameData.data);

  return (
    <div className="flex flex-col items-center text-center text-main dark:text-darktext">
      <h2 className="mt-7 text-xl font-light text-muted transition-colors duration-300 md:text-2xl dark:text-darkmutedtext">
        {gameData.data?.game_name}
      </h2>
      <p>getting data for {role}</p>
      <img src={gameData.data.game_qr_code} alt="link to game" />
      <div>{gameData.data.chat_enabled ? "chat geht wohl" : "kein chat"}</div>
    </div>
  );
}
