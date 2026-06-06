import React from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AgentPage } from "./pages/AgentPage";
import { ProfilePage } from "./pages/ProfilePage";

export function AppRouter({ shell: Shell }: { shell: React.FC }) {
  const router = createBrowserRouter([
    {
      element: <Shell />,
      children: [
        { path: "/", element: <AgentPage /> },
        { path: "/profile", element: <ProfilePage /> },
      ],
    },
  ]);
  return <RouterProvider router={router} />;
}
