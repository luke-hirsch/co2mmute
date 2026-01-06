import { ProtectedRoute } from "../ProtectedRoute";

import MapList from "./MapList";

const MapListRoute = () => {
  return (
    <ProtectedRoute staff={true}>
      <MapList />
    </ProtectedRoute>
  );
};

export default MapListRoute;
