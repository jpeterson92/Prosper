import { useState } from "react";
import { createRoot } from "react-dom/client";
import { runProbe } from "./probe";
import "./style.css";

function Probe() {
  const [status, setStatus] = useState("Ready to check the local connection.");
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    setStatus("Connecting to the local runtime…");
    try {
      const generation = await runProbe();
      setStatus(`F001/F004 transport verified. Active generation: ${generation}. Financial planning remains unavailable.`);
    } catch {
      setStatus("Connection unavailable. Check that the configured synthetic runtime is running, then try again.");
    } finally { setBusy(false); }
  }
  return <main>
    <p className="eyebrow">PROSPER / DEVELOPMENT</p>
    <h1>Synthetic browser probe</h1>
    <p>This diagnostic checks the protected local connection using fictional development data.</p>
    <section aria-label="Connection diagnostic">
      <span className="badge">Synthetic data only</span>
      <h2>Local connection</h2>
      <p role="status">{status}</p>
      <button disabled={busy} onClick={() => void run()}>{busy ? "Checking…" : "Check connection"}</button>
    </section>
    <p className="footnote">Technical diagnostic. Portfolio review and import actions arrive in a later stage.</p>
  </main>;
}

createRoot(document.getElementById("root")!).render(<Probe />);
