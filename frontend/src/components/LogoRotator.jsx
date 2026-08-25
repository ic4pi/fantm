import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { Skull } from "lucide-react";

/**
 * Two layouts share one rotation pool (see backend/logos.py):
 *  - "icon"   — a standalone glyph, cropped small and paired with the
 *               "fantm.ink" text next to it (the original three ghost marks).
 *  - "lockup" — the wordmark is already baked into the art; shown whole,
 *               no separate text alongside it.
 * The pool stays name-indifferent — type comes from a filename prefix
 * on the backend, not from anything hardcoded here.
 */
export function LogoRotator() {
  const [logo, setLogo] = useState(null);
  const [type, setType] = useState(null);
  const [failed, setFailed] = useState(false);
  const [isLightGround, setIsLightGround] = useState(false);
  const imgRef = useRef(null);

  useEffect(() => {
    api.get("/logos/random").then(({ data }) => {
      if (data.logo) {
        setLogo(data.logo);
        setType(data.type || "lockup");
      }
    }).catch(() => {});
  }, []);

  // Icon marks don't share a common background — some are neon-on-black,
  // some are line art on white. Screen-blending a light-ground image
  // uniformly would leave a pale tile in the header, so sample the
  // artwork's corners at load time and flip it if needed. Holds for any
  // icon dropped into the pool later, not just the current three.
  const handleLoad = () => {
    if (type !== "icon" || !imgRef.current) return;
    try {
      const img = imgRef.current;
      const c = document.createElement("canvas");
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      const ctx = c.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      const pts = [
        [2, 2], [img.naturalWidth - 3, 2],
        [2, img.naturalHeight - 3], [img.naturalWidth - 3, img.naturalHeight - 3],
      ];
      let lum = 0;
      for (const [x, y] of pts) {
        const d = ctx.getImageData(x, y, 1, 1).data;
        lum += 0.2126 * d[0] + 0.7152 * d[1] + 0.0722 * d[2];
      }
      setIsLightGround(lum / pts.length > 128);
    } catch (_) {
      // canvas read can fail (e.g. CORS on some hosts) — art stays as-is
    }
  };

  if (!logo || failed) {
    return (
      <span className="flex items-center gap-2" data-testid="navbar-logo-fallback">
        <Skull className="w-5 h-5 text-primary" />
        fantm<span className="text-primary">.ink</span>
      </span>
    );
  }

  if (type === "icon") {
    return (
      <span className="flex items-center gap-2.5" data-testid="navbar-logo-icon">
        <span className="relative w-11 h-11 overflow-hidden flex-none">
          <img
            ref={imgRef}
            src={`/logos/${logo}`}
            alt=""
            onLoad={handleLoad}
            onError={() => setFailed(true)}
            className={`absolute w-[88px] h-[88px] -left-[22px] -top-[14px] mix-blend-screen ${isLightGround ? "[filter:invert(1)_hue-rotate(180deg)_contrast(1.12)_saturate(1.15)]" : "[filter:contrast(1.55)_saturate(1.15)_brightness(1.02)]"}`}
            data-testid="navbar-logo-image"
          />
        </span>
        <span className="font-serif text-2xl tracking-tight text-foreground">
          fantm<span className="text-primary">.ink</span>
        </span>
      </span>
    );
  }

  return (
    <img
      src={`/logos/${logo}`}
      alt="fantm.ink"
      className="h-9 w-auto object-contain"
      onError={() => setFailed(true)}
      data-testid="navbar-logo-image"
    />
  );
}

