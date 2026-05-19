type Palette = {
  /** lid background (radial gradient stops, light → dark) */
  lid: [string, string, string];
  /** outer chrome rim gradient stops, light → dark */
  rim: [string, string, string, string];
  /** small label color under the wordmark */
  label: string;
};

export const TIN_PALETTES: Record<string, Palette> = {
  navy: {
    lid: ["#16284c", "#0d1f3c", "#06122a"],
    rim: ["#e7eef8", "#a8c4e0", "#3c5b8a", "#0c1530"],
    label: "#a8c4e0",
  },
  mint: {
    lid: ["#163b39", "#0b2422", "#031312"],
    rim: ["#e0f5ec", "#9bd9c6", "#357f74", "#08221f"],
    label: "#bce6d4",
  },
  citrus: {
    lid: ["#4a2e15", "#2a190a", "#120a04"],
    rim: ["#fce7c2", "#f0c98a", "#9a6a2b", "#241208"],
    label: "#f0c98a",
  },
};

type TinProps = {
  /** Color palette key. Defaults to navy. */
  palette?: keyof typeof TIN_PALETTES;
  /** Caption shown under the ZIBS wordmark (e.g. "GUM HEALTH POUCH · 30 CT") */
  caption?: string;
  /** Show the soft cast shadow under the tin. Default true. */
  shadow?: boolean;
  /** Optional className passthrough to the SVG */
  className?: string;
  /** Accessibility label. Default "Zibs tin". */
  ariaLabel?: string;
};

/**
 * Top-down render of a Zibs tin: clean concentric chrome rim, soft lit lid,
 * centered serif wordmark. Same shape across the site — just swap the palette
 * for flavor variants.
 */
export function Tin({
  palette = "navy",
  caption = "GUM HEALTH POUCH · 30 CT",
  shadow = true,
  className,
  ariaLabel = "Zibs tin",
}: TinProps) {
  const p = TIN_PALETTES[palette];
  const id = palette;

  return (
    <svg
      viewBox="0 0 320 320"
      className={className}
      role="img"
      aria-label={ariaLabel}
    >
      <defs>
        {/* Lid gradient — key light from upper-left */}
        <radialGradient id={`lid-${id}`} cx="36%" cy="30%" r="78%">
          <stop offset="0%" stopColor={p.lid[0]} />
          <stop offset="60%" stopColor={p.lid[1]} />
          <stop offset="100%" stopColor={p.lid[2]} />
        </radialGradient>

        {/* Chrome rim — diagonal sweep of light → dark for a polished feel */}
        <linearGradient
          id={`rim-${id}`}
          x1="20%"
          y1="0%"
          x2="80%"
          y2="100%"
        >
          <stop offset="0%" stopColor={p.rim[0]} />
          <stop offset="35%" stopColor={p.rim[1]} />
          <stop offset="65%" stopColor={p.rim[2]} />
          <stop offset="100%" stopColor={p.rim[3]} />
        </linearGradient>

        {/* Inner lid specular */}
        <radialGradient id={`spec-${id}`} cx="34%" cy="22%" r="38%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>

        {/* Soft drop shadow */}
        <radialGradient id={`ground-${id}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#000" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#000" stopOpacity="0" />
        </radialGradient>
      </defs>

      {shadow && (
        <ellipse cx="160" cy="278" rx="120" ry="14" fill={`url(#ground-${id})`} />
      )}

      {/* Outer chrome rim */}
      <circle cx="160" cy="160" r="148" fill={`url(#rim-${id})`} />

      {/* Inner step — narrow groove */}
      <circle
        cx="160"
        cy="160"
        r="134"
        fill="none"
        stroke={p.rim[2]}
        strokeOpacity="0.55"
        strokeWidth="1"
      />

      {/* Recessed lid */}
      <circle cx="160" cy="160" r="130" fill={`url(#lid-${id})`} />

      {/* Lid inner debossed ring (catches the eye, suggests the seam) */}
      <circle
        cx="160"
        cy="160"
        r="114"
        fill="none"
        stroke={p.rim[0]}
        strokeOpacity="0.12"
        strokeWidth="1"
      />

      {/* Soft specular highlight on the lid */}
      <circle cx="160" cy="160" r="130" fill={`url(#spec-${id})`} />

      {/* Brand mark */}
      <text
        x="160"
        y="167"
        textAnchor="middle"
        fontFamily="Cormorant Garamond, serif"
        fontWeight="500"
        fontSize="46"
        fill="#f5f1e8"
        letterSpacing="10"
      >
        ZIBS
      </text>

      {/* Caption */}
      <text
        x="160"
        y="192"
        textAnchor="middle"
        fontFamily="DM Sans, sans-serif"
        fontSize="8"
        fill={p.label}
        letterSpacing="4"
        opacity="0.85"
      >
        {caption}
      </text>
    </svg>
  );
}
