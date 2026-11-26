import React, { useEffect, useRef } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { OverviewPage } from "./pages/OverviewPage";
import { StudyPage } from "./pages/StudyPage";
import { SimulatePage } from "./pages/SimulatePage";
import { UploadPage } from "./pages/UploadPage";
import { HistoryPage } from "./pages/HistoryPage";
import { NotFoundPage } from "./pages/NotFoundPage";

function RouteFocus() {
  const { pathname } = useLocation();
  const section = pathname.split("/")[1];
  const previous = useRef(section);
  useEffect(() => {
    const title = document.querySelector("main h1")?.textContent || "Workspace";
    document.title = `${title} · CloudPilot`;
    if (previous.current !== section) {
      previous.current = section;
      document.getElementById("main-content")?.focus({ preventScroll: true });
      window.scrollTo(0, 0);
    }
  }, [pathname, section]);
  return null;
}

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className="app-container">
          <Header />
          <main className="main-content shell-width" id="main-content" tabIndex={-1}>
            <Routes>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/study" element={<StudyPage />} />
              <Route path="/simulate" element={<SimulatePage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/history/:id?" element={<HistoryPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </main>
          <RouteFocus />
          <Footer />
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
};
