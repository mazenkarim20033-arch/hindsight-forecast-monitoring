import { useCallback, useEffect, useRef, useState } from "react";

export const SPEEDS = [
  { label: "1×", daysPerSecond: 4 },
  { label: "2×", daysPerSecond: 10 },
  { label: "4×", daysPerSecond: 20 },
] as const;

/** A playhead that moves through whole days. `value` is the day now showing; playback stops by itself at `max`. */
export function usePlayer(min: number, max: number, start: number) {
  const [value, setValue] = useState(() => Math.min(Math.max(start, min), max));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const carry = useRef(0);
  const valueRef = useRef(value);
  valueRef.current = value;

  const clamp = useCallback((v: number) => Math.min(Math.max(Math.round(v), min), max), [min, max]);
  const seek = useCallback((v: number) => { setPlaying(false); setValue(clamp(v)); }, [clamp]);
  const step = useCallback((by: number) => { setPlaying(false); setValue((v) => clamp(v + by)); }, [clamp]);

  useEffect(() => {
    setValue((v) => clamp(v));
  }, [clamp]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    carry.current = 0;
    const tick = (now: number) => {
      carry.current += ((now - last) / 1000) * SPEEDS[speed].daysPerSecond;
      last = now;
      const whole = Math.floor(carry.current);
      if (whole > 0) {
        carry.current -= whole;
        const next = Math.min(valueRef.current + whole, max);
        setValue(next);
        if (next >= max) {
          setPlaying(false);
          return;
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, max]);

  const toggle = useCallback(() => {
    if (!playing && valueRef.current >= max) setValue(min);
    setPlaying((p) => !p);
  }, [playing, max, min]);

  return { value, playing, speed, setSpeed, toggle, seek, step, pause: () => setPlaying(false) };
}
