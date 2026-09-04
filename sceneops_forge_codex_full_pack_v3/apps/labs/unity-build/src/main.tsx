import "./base.css";
import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UnityBuildWorkbench } from "../../../../modules/build-release/frontend/src/index";
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider
    client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
  >
    <UnityBuildWorkbench />
  </QueryClientProvider>,
);
