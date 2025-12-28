import { ProtectedRoute } from "../ProtectedRoute";
import Lobby from "./Lobby";

const LobbyRoute = () => {
  return (
    <ProtectedRoute requiredKind={["host", "player"]}>
      <Lobby />
    </ProtectedRoute>
  );
};
export default LobbyRoute;
