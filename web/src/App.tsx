import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ErrorBoundary } from "@/components/error-boundary";
import { AppShell } from "@/components/layout/app-shell";
import DashboardPage from "@/pages/dashboard";
import AccountsPage from "@/pages/accounts";
import AccountDetailPage from "@/pages/account-detail";
import DocumentsPage from "@/pages/documents";
import MessagesPage from "@/pages/messages";
import HistoryPage from "@/pages/history";
import DocumentDetailPage from "@/pages/document-detail";
import LogsPage from "@/pages/logs";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="accounts" element={<AccountsPage />} />
            <Route path="accounts/add" element={<Navigate to="/accounts" replace />} />
            <Route path="accounts/:id" element={<AccountDetailPage />} />
            <Route path="docs" element={<DocumentsPage />} />
            <Route path="docs/:id" element={<DocumentDetailPage />} />
            <Route path="messages" element={<MessagesPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="logs" element={<LogsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
    </ErrorBoundary>
  );
}
