import { useId } from "react";
import logo from "./assets/brand/ays-connect.png";

/** The approved logo artwork; both themes share exactly the same lettering mask. */
export function BrandLogo({ inverse = false }: { inverse?: boolean }) {
  const id = useId().replace(/:/g, "");
  const letters = `ays-letters-${id}`;
  const stroke = `ays-stroke-${id}`;
  return (
    <span className={`brand-logo${inverse ? " brand-logo-inverse" : ""}`} role="img" aria-label="AYS! Connect">
      <svg width="0" height="0" aria-hidden="true" className="brand-filters">
        <defs>
          <filter id={letters} colorInterpolationFilters="sRGB">
            <feColorMatrix type="luminanceToAlpha" />
            <feComponentTransfer result="letters"><feFuncA type="linear" slope="4" intercept="-2" /></feComponentTransfer>
            <feFlood floodColor="currentColor" />
            <feComposite in2="letters" operator="in" />
          </filter>
          <filter id={stroke} colorInterpolationFilters="sRGB">
            <feColorMatrix type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 1 1 1 0 0" />
          </filter>
        </defs>
      </svg>
      <img className="brand-stroke" src={logo} alt="" aria-hidden="true" style={{ filter: `url(#${stroke})` }} />
      <span className="brand-lettering" aria-hidden="true">
        <img src={logo} alt="" style={{ filter: `url(#${letters})` }} />
      </span>
    </span>
  );
}
