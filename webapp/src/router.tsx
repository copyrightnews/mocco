import React from "react";
import { createBrowserRouter, RouterProvider, Outlet } from "react-router-dom";
import { AgentPage } from "./pages/AgentPage";
import { ProfilePage } from "./pages/ProfilePage";

export function AppRouter({ shell }: { shell: React.FC }) {
  const router = createBrowserRouter([
    {
      element: <shell />,
      children: [
        { path: "/", element: <AgentPage /> },
        { path: "/profile", element: <ProfilePage /> },
      ],
    },
  ]);
  return <RouterProvider router={router} />;
}
