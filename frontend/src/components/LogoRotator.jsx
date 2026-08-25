import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Skull } from "lucide-react";

export function LogoRotator() {
  const [logo, setLogo] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api.get("/logos/random").then(({ data }) => {
      if (data.logo) setLogo(data.logo);
    }).catch(() => {});
  }, []);

  if (!logo || failed) {
    return (
      <span className="flex items-center gap-2" data-testid="navbar-logo-fallback">
        <Skull className="w-5 h-5 text-primary" />
        fantm<span className="text-primary">.ink</span>
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
