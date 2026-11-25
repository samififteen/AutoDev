import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import History from "./pages/History";
import NotFound from "./pages/NotFound";
import Overview from "./pages/Overview";
import PullRequests from "./pages/PullRequests";
import Repositories from "./pages/Repositories";
import RepositoryDetail from "./pages/RepositoryDetail";
import Settings from "./pages/Settings";
import Tasks from "./pages/Tasks";
import Workspace from "./pages/Workspace";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Overview />} />
        <Route path="repositories" element={<Repositories />} />
        <Route path="repositories/:repositoryId" element={<RepositoryDetail />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="workspace" element={<Workspace />} />
        <Route path="workspace/:executionId" element={<Workspace />} />
        <Route path="pull-requests" element={<PullRequests />} />
        <Route path="history" element={<History />} />
        <Route path="settings" element={<Settings />} />
        <Route path="home" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
