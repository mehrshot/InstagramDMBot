import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import Account from "./pages/Account";
import Dashboard from "./pages/Dashboard";
import Handoffs from "./pages/Handoffs";
import Inbox from "./pages/Inbox";
import Instagram from "./pages/Instagram";
import InstagramCallback from "./pages/InstagramCallback";
import Knowledge from "./pages/Knowledge";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Playground from "./pages/Playground";
import Products from "./pages/Products";
import Register from "./pages/Register";
import Settings from "./pages/Settings";
import Unanswered from "./pages/Unanswered";
import { DataDeletion, Privacy, Terms } from "./pages/public/Legal";

function RequireAuth({ children }: { children: ReactNode }) {
  const { loggedIn } = useAuth();
  const location = useLocation();
  if (!loggedIn) {
    const next = location.pathname + location.search;
    return <Navigate to={`/login${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`} replace />;
  }
  return children;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { loggedIn } = useAuth();
  return loggedIn ? <Navigate to="/" replace /> : children;
}

export default function App() {
  return (
    <Routes>
      {/* public — Meta's app review needs these without login */}
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/data-deletion" element={<DataDeletion />} />

      <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
      <Route path="/register" element={<GuestOnly><Register /></GuestOnly>} />

      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path="handoffs" element={<Handoffs />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="inbox/:id" element={<Inbox />} />
        <Route path="unanswered" element={<Unanswered />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="products" element={<Products />} />
        <Route path="playground" element={<Playground />} />
        <Route path="settings" element={<Settings />} />
        <Route path="instagram" element={<Instagram />} />
        <Route path="instagram/callback" element={<InstagramCallback />} />
        <Route path="account" element={<Account />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
