import React from "react";

export default function ErrorBox({ message }) {
  return (
    <div role="alert" className="error-box" style={{ color: "red", padding: "1rem", textAlign: "center" }}>
      {message}
    </div>
  );
}
