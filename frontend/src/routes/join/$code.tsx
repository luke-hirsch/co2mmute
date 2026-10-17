import { createFileRoute, useParams } from "@tanstack/react-router";

import { CodeScreen } from "@/components/join/code-screen";

function CodeRoute() {
  const { code } = useParams({ from: "/join/$code" });
  return <CodeScreen code={code.trim().toUpperCase()} />;
}

export const Route = createFileRoute("/join/$code")({
  component: CodeRoute,
});
