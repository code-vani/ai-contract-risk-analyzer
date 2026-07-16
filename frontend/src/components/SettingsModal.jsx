import React, { useEffect, useRef, useState } from "react";
import { Settings, X, Server, CheckCircle2, AlertTriangle, RotateCcw } from "lucide-react";

const DEFAULT_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

/**
 * Runtime settings — lets the user point the app at a different backend without
 * rebuilding. The value is persisted to localStorage under "backendUrl", which
 * App's BACKEND_URL resolver reads on load; changing it takes effect on reload.
 */
const SettingsModal = ({ onClose, currentModel }) => {
  const panelRef = useRef(null);
  const [url, setUrl] = useState(() => {
    try { return localStorage.getItem("backendUrl") || DEFAULT_URL; }
    catch { return DEFAULT_URL; }
  });
  const [test, setTest] = useState({ state: "idle" }); // idle | testing | ok | fail
  const [saved, setSaved] = useState(false);

  // Focus first field, trap Tab, close on Escape.
  useEffect(() => {
    const panel = panelRef.current;
    const focusables = () =>
      Array.from(panel?.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])') || [])
        .filter((el) => !el.disabled && el.offsetParent !== null);
    focusables()[0]?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    panel?.addEventListener("keydown", onKey);
    return () => panel?.removeEventListener("keydown", onKey);
  }, [onClose]);

  const trimmed = url.trim().replace(/\/+$/, "");

  const testConnection = async () => {
    setTest({ state: "testing" });
    try {
      const res = await fetch(`${trimmed}/health`, { signal: AbortSignal.timeout(6000) });
      const data = await res.json();
      if (res.ok) setTest({ state: "ok", model: data.model, live: !data.mock });
      else setTest({ state: "fail", msg: `HTTP ${res.status}` });
    } catch (e) {
      setTest({ state: "fail", msg: e.name === "TimeoutError" ? "Timed out" : "Unreachable" });
    }
  };

  const save = () => {
    try { localStorage.setItem("backendUrl", trimmed); } catch { /* storage blocked */ }
    setSaved(true);
  };

  const resetDefault = () => {
    try { localStorage.removeItem("backendUrl"); } catch { /* storage blocked */ }
    setUrl(DEFAULT_URL);
    setSaved(true);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div ref={panelRef} className="modal-panel p-6" role="dialog" aria-modal="true" aria-labelledby="settings-title" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="logo-ring p-2"><Settings className="w-5 h-5 text-indigo-400" aria-hidden="true" /></div>
            <div>
              <h2 id="settings-title" className="text-base font-bold text-white font-['Outfit']">Settings</h2>
              <p className="text-[11px] text-slate-500">Runtime configuration — stored in your browser.</p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close dialog" className="p-1.5 hover:bg-slate-800/60 rounded-lg text-slate-500 hover:text-white transition-all"><X className="w-4 h-4" aria-hidden="true" /></button>
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="backend-url" className="text-[9px] text-slate-500 uppercase font-bold tracking-wider flex items-center gap-1.5">
              <Server className="w-3 h-3" aria-hidden="true" /> Backend API URL
            </label>
            <input
              id="backend-url"
              type="url"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setSaved(false); setTest({ state: "idle" }); }}
              placeholder="http://localhost:8000"
              className="w-full text-[12px] bg-slate-900/50 text-slate-200 rounded-lg border border-slate-800/80 px-3 py-2 font-mono focus:border-indigo-500/50 outline-none"
            />
            <p className="text-[10px] text-slate-500 leading-relaxed">
              Where the app fetches analyses from. Changing this takes effect after a reload.
            </p>
          </div>

          {test.state === "ok" && (
            <div className="flex items-start gap-2 text-[11px] text-emerald-300 bg-emerald-500/8 border border-emerald-500/20 p-2.5 rounded-lg">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" />
              <span>Connected · {test.live ? "Live engine" : "Demo/mock"}{test.model ? ` · ${test.model}` : ""}</span>
            </div>
          )}
          {test.state === "fail" && (
            <div className="flex items-start gap-2 text-[11px] text-rose-300 bg-rose-500/8 border border-rose-500/20 p-2.5 rounded-lg">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" />
              <span>Could not reach backend ({test.msg}).</span>
            </div>
          )}

          <div className="flex items-center gap-2 pt-1">
            <button onClick={testConnection} disabled={test.state === "testing"} className="btn-glass px-3 py-2 text-[11px] flex items-center gap-1.5">
              {test.state === "testing"
                ? <><div className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Testing…</>
                : <><Server className="w-3.5 h-3.5" aria-hidden="true" /> Test Connection</>}
            </button>
            <button onClick={resetDefault} title="Reset to the built-in default URL" className="btn-glass px-3 py-2 text-[11px] flex items-center gap-1.5 text-slate-400">
              <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" /> Default
            </button>
            <button onClick={save} className="btn-primary-cta px-4 py-2 text-[12px] ml-auto flex items-center gap-1.5">
              {saved ? <><CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" /> Saved</> : "Save"}
            </button>
          </div>

          {saved && (
            <p className="text-[10px] text-amber-300/90 text-center">Reload the app for the new backend URL to take effect.</p>
          )}

          <div className="pt-3 mt-1 border-t border-slate-800/50 flex items-center justify-between text-[10px] text-slate-500">
            <span>Current engine</span>
            <span className="font-mono text-indigo-300">{currentModel || "unknown"}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;
