import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ApiError } from "./api/client";
import { AuthProvider } from "./auth/AuthContext";
import { ToastHost, pushToast } from "./components/Toast";
import { ThemeProvider } from "./theme/ThemeContext";
import "./index.css";

let queryClient: QueryClient | undefined;

function handleError(error: unknown): void {
  if (error instanceof ApiError) {
    if (error.status === 401) return;
    pushToast("error", error.message);
    if (error.status === 409) {
      void queryClient?.invalidateQueries();
    }
    return;
  }
  if (error instanceof Error) pushToast("error", error.message);
}

queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
  queryCache: new QueryCache({ onError: handleError }),
  mutationCache: new MutationCache({ onError: handleError }),
});

const client = queryClient;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <App />
            <ToastHost />
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
