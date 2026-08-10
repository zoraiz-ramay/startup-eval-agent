import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
// iX first: it defines the --theme-* variables that tokens.css maps onto, so it has to be
// parsed before our own sheet reads them.
import "@siemens/ix/dist/siemens-ix/siemens-ix.css";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
