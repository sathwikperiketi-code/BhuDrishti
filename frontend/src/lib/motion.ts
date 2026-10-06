import { useReducedMotion } from "framer-motion";
import type { Transition, Variants } from "framer-motion";

export const motionDuration = { fast: 0.14, medium: 0.24, slow: 0.42 } as const;
export const motionEase = [0.22, 1, 0.36, 1] as const;

export function useMotionPresets() {
  const reducedMotion = Boolean(useReducedMotion());
  const transition: Transition = { duration: reducedMotion ? 0 : motionDuration.medium, ease: motionEase };
  const slowTransition: Transition = { duration: reducedMotion ? 0 : motionDuration.slow, ease: motionEase };
  const page: Variants = {
    initial: { opacity: 0, y: reducedMotion ? 0 : 10 },
    animate: { opacity: 1, y: 0, transition },
    exit: { opacity: 0, y: reducedMotion ? 0 : -6, transition },
  };
  const card: Variants = {
    initial: { opacity: 0, y: reducedMotion ? 0 : 6 },
    animate: { opacity: 1, y: 0, transition },
  };
  const panel: Variants = {
    initial: { opacity: 0, x: reducedMotion ? 0 : 16 },
    animate: { opacity: 1, x: 0, transition: slowTransition },
    exit: { opacity: 0, x: reducedMotion ? 0 : 12, transition },
  };
  const status: Variants = {
    initial: { opacity: 0, scale: reducedMotion ? 1 : 0.96 },
    animate: { opacity: 1, scale: 1, transition: { duration: reducedMotion ? 0 : motionDuration.fast, ease: motionEase } },
  };
  return { reducedMotion, transition, slowTransition, page, card, panel, status };
}
