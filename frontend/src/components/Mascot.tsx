import { useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
import { useInView, useReducedMotion } from "./site/motion";
import { cx } from "./ui";

/** wave: hello · busy: hurrying on it · idea: the light-bulb moment (plays once unless `loop`). */
export type MascotPose = "wave" | "busy" | "idea";

// width / height of each cut-out, so the box is reserved before anything loads
const RATIO: Record<MascotPose, number> = { wave: 239 / 200, busy: 1, idea: 165 / 200 };

// Safari (and every iOS browser) can't show a transparent WebM, so it gets a small animated WebP instead.
const WEBKIT =
  typeof navigator !== "undefined" &&
  (/iPad|iPhone|iPod/.test(navigator.userAgent) || /^((?!chrome|chromium|android|crios|fxios|edg).)*safari/i.test(navigator.userAgent));

/**
 * The Javab mascot. A tiny still (under 10 KB) is shown first; the animation (a transparent WebM
 * of 30-80 KB) loads only once it scrolls into view, so it never slows the page down.
 * With reduced motion it stays still.
 */
export function Mascot({ pose, className, alt = "", loop }: { pose: MascotPose; className?: string; alt?: string; /** default: every pose loops except "idea" */ loop?: boolean }) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref);
  const reduced = useReducedMotion();
  const still = `/mascot/mascot-${pose}-still.webp`;
  const once = !(loop ?? pose !== "idea");
  const box = cx("pointer-events-none select-none object-contain", className);
  const style = { aspectRatio: RATIO[pose] };
  const a11y = alt ? { role: "img", "aria-label": alt } : { "aria-hidden": true };

  if (reduced) return <img src={still} alt={alt} aria-hidden={alt ? undefined : true} draggable={false} className={box} style={style} />;

  if (WEBKIT)
    return <WebpMascot file={pose === "idea" && !once ? "idea-loop" : pose} still={still} inView={inView} imgRef={ref} className={box} style={style} alt={alt} />;

  return (
    <video
      ref={ref as RefObject<HTMLVideoElement>}
      src={inView ? `/mascot/mascot-${pose}.webm` : undefined}
      poster={still}
      autoPlay
      muted
      loop={!once}
      playsInline
      preload="none"
      disablePictureInPicture
      className={box}
      style={style}
      {...a11y}
    />
  );
}

function WebpMascot({
  file,
  still,
  inView,
  imgRef,
  className,
  style,
  alt,
}: {
  file: string;
  still: string;
  inView: boolean;
  imgRef: RefObject<HTMLElement | null>;
  className: string;
  style: CSSProperties;
  alt: string;
}) {
  const anim = `/mascot/mascot-${file}.webp`;
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!inView) return;
    const img = new Image();
    img.src = anim;
    let live = true;
    img.decode().then(
      () => live && setReady(true),
      () => {},
    );
    return () => {
      live = false;
    };
  }, [anim, inView]);
  return (
    <img
      ref={imgRef as RefObject<HTMLImageElement>}
      src={ready ? anim : still}
      alt={alt}
      aria-hidden={alt ? undefined : true}
      draggable={false}
      decoding="async"
      className={className}
      style={style}
    />
  );
}
