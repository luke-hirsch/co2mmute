import { createFileRoute, useParams } from "@tanstack/react-router";

import { SeatRedeemScreen } from "@/components/seat/seat-redeem-screen";

/**
 * Where a seat code lands, typed or scanned.
 *
 * Its own route rather than a mode of the join screen: a QR has to point
 * somewhere, and what happens here is not joining — the row already exists and
 * only changes device.
 */
function SeatRedeemRoute() {
  const { code } = useParams({ from: "/seat/$code" });
  return <SeatRedeemScreen code={code.toUpperCase()} />;
}

export const Route = createFileRoute("/seat/$code")({
  component: SeatRedeemRoute,
});
