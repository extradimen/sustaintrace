import React from "react";
import { createRoot } from "react-dom/client";

import "./globals.css";
import Home from "./page";

const root = document.getElementById("root");

if (!root) {
  throw new Error("SustainTrace root element is missing");
}

createRoot(root).render(
  <React.StrictMode>
    <Home />
  </React.StrictMode>,
);
