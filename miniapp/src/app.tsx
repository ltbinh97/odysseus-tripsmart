import React from "react";
import { createRoot } from "react-dom/client";
import { AppRoot } from "./components/Layout";
import "./css/app.css";

const container = document.getElementById("app");
if (!container) throw new Error("#app root element not found");

createRoot(container).render(
  <React.StrictMode>
    <AppRoot />
  </React.StrictMode>,
);
