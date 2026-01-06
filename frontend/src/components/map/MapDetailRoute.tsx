import { ProtectedRoute } from "../ProtectedRoute";

import MapDetail from "./MapDetail";

const MapDetailRoute = () => {
  return (
    <ProtectedRoute staff={true}>
      <MapDetail />
    </ProtectedRoute>
  );
};

export default MapDetailRoute;
