import { useEffect, useRef, useState } from "react";
import { motion, useMotionValue, useSpring } from "framer-motion";

const INTERACTIVE_SELECTOR = "button, a, input, textarea, select, [role='button']";

export function CustomCursor() {
  const [enabled, setEnabled] = useState(false);
  const [target, setTarget] = useState(null);
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const sx = useSpring(x, { stiffness: 500, damping: 40 });
  const sy = useSpring(y, { stiffness: 500, damping: 40 });
  const boxRef = useRef(null);

  useEffect(() => {
    const isFinePointer = window.matchMedia("(pointer: fine)").matches;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!isFinePointer || reducedMotion) return;
    setEnabled(true);
    document.body.classList.add("custom-cursor-on");

    const handleMove = (e) => {
      x.set(e.clientX);
      y.set(e.clientY);
      const el = e.target.closest(INTERACTIVE_SELECTOR);
      setTarget(el || null);
    };
    window.addEventListener("mousemove", handleMove);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      document.body.classList.remove("custom-cursor-on");
    };
  }, [x, y]);

  if (!enabled) return null;

  const rect = target?.getBoundingClientRect();
  const isSnapped = !!rect;

  return (
    <motion.div
      ref={boxRef}
      className="fixed pointer-events-none z-[9999] mix-blend-difference"
      style={{
        left: isSnapped ? rect.left + rect.width / 2 : sx,
        top: isSnapped ? rect.top + rect.height / 2 : sy,
        x: "-50%",
        y: "-50%",
      }}
      data-testid="custom-cursor"
    >
      <motion.div
        animate={{
          width: isSnapped ? (rect.width || 40) + 12 : 14,
          height: isSnapped ? (rect.height || 40) + 12 : 14,
          scale: isSnapped ? [1, 1.05, 1] : 1,
        }}
        transition={{ type: "spring", stiffness: 300, damping: 24 }}
        style={{
          border: "1.5px solid #E6FF00",
          boxShadow: "inset 0 0 10px #E6FF00, 0 0 15px #FF007F",
        }}
      >
        {!isSnapped && (
          <div className="absolute inset-0 m-auto w-1 h-1 rounded-full" style={{ background: "#E6FF00", boxShadow: "0 0 6px #E6FF00" }} />
        )}
      </motion.div>
    </motion.div>
  );
}
