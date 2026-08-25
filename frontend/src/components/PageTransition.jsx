import { motion, AnimatePresence } from "framer-motion";
import { useLocation } from "react-router-dom";

const reducedMotion = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const variants = reducedMotion
  ? {
      initial: { opacity: 0 },
      animate: { opacity: 1, transition: { duration: 0.25 } },
      exit: { opacity: 0, transition: { duration: 0.2 } },
    }
  : {
      initial: { scaleY: 0.01, opacity: 0, transformOrigin: "center" },
      animate: {
        scaleY: 1,
        opacity: [0, 1, 0.4, 1],
        filter: "brightness(1)",
        transition: { duration: 0.6, ease: "easeOut" },
      },
      exit: {
        scaleY: 0.01,
        opacity: 0,
        filter: "brightness(3) drop-shadow(0 0 20px #FF007F)",
        transition: { duration: 0.35, ease: "easeIn" },
      },
    };

export function PageTransition({ children }) {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial="initial"
        animate="animate"
        exit="exit"
        variants={variants}
        data-testid="page-transition-wrapper"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
