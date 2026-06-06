import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AgentPage } from "./pages/AgentPage";
import { ProfilePage } from "./pages/ProfilePage";

const router = createBrowserRouter([
  { path: "/", element: <AgentPage /> },
  { path: "/profile", element: <ProfilePage /> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
