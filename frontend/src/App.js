import "@/App.css";
import { useEffect, useRef } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Navbar } from "@/components/Navbar";
import { CustomCursor } from "@/components/CustomCursor";
import { PageTransition } from "@/components/PageTransition";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import CreateBook from "@/pages/CreateBook";
import BookGeneration from "@/pages/BookGeneration";
import BookReader from "@/pages/BookReader";
import Store from "@/pages/Store";
import PaymentSuccess from "@/pages/PaymentSuccess";
import PaymentCancel from "@/pages/PaymentCancel";

/** The neon aura follows the pointer on desktop and drifts on its own on
 * touch devices — same effect the parlour concept mockup used, driving the
 * same --mx/--my custom properties the .aura-glow/.wall-glint CSS reads. */
function useAura() {
  const target = useRef({ x: 72, y: 28 });
  const current = useRef({ x: 72, y: 28 });

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) return;

    let raf;
    const tick = () => {
      current.current.x += (target.current.x - current.current.x) * 0.06;
      current.current.y += (target.current.y - current.current.y) * 0.06;
      document.documentElement.style.setProperty("--mx", `${current.current.x.toFixed(2)}%`);
      document.documentElement.style.setProperty("--my", `${current.current.y.toFixed(2)}%`);
      raf = requestAnimationFrame(tick);
    };
    tick();

    const onMove = (e) => {
      target.current.x = (e.clientX / window.innerWidth) * 100;
      target.current.y = (e.clientY / window.innerHeight) * 100;
    };

    const isTouch = window.matchMedia("(hover: none)").matches;
    let driftTimer;
    if (isTouch) {
      let t = 0;
      driftTimer = setInterval(() => {
        t += 0.06;
        target.current.x = 50 + Math.cos(t * 0.7) * 28;
        target.current.y = 34 + Math.sin(t) * 22;
      }, 60);
    } else {
      window.addEventListener("pointermove", onMove, { passive: true });
    }

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      if (driftTimer) clearInterval(driftTimer);
    };
  }, []);
}

function App() {
  useAura();
  return (
    <div className="App min-h-screen">
      <div className="wall-lattice" />
      <div className="wall-glint" />
      <div className="aura-glow" />
      <div className="fog-blob-a" style={{ top: "-10vh", left: "-10vw" }} />
      <div className="fog-blob-b" style={{ bottom: "-15vh", right: "-10vw" }} />
      <div className="noise-grain" />
      <BrowserRouter>
        <AuthProvider>
          <CustomCursor />
          <Navbar />
          <PageTransition>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/payment/success" element={<PaymentSuccess />} />
              <Route path="/payment/cancel" element={<PaymentCancel />} />
              <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/store" element={<ProtectedRoute><Store /></ProtectedRoute>} />
              <Route path="/books/new" element={<ProtectedRoute><CreateBook /></ProtectedRoute>} />
              <Route path="/books/:id/generating" element={<ProtectedRoute><BookGeneration /></ProtectedRoute>} />
              <Route path="/books/:id/read" element={<ProtectedRoute><BookReader /></ProtectedRoute>} />
            </Routes>
          </PageTransition>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
