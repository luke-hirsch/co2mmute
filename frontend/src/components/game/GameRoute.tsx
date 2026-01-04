import { ProtectedRoute } from "../ProtectedRoute";
import Game from "./Game";

const GameRoute = () => {
  return (
    <ProtectedRoute requiredKind={["host", "player"]}>
      <Game />
    </ProtectedRoute>
  );
};
export default GameRoute;
