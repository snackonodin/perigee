// The bunny: two long upright rounded ears (0.9x head height), round face slightly taller
// than wide, round body, pom tail at the side. Head 136 (y 70..206); ear tips y ~6.
import { Accessories, Face, Grain, PALETTE, PetDefs, PetSvg, Rim, Shadow, fill, pivot, type HeadGeo } from "./shared";

const HEAD: HeadGeo = { cx: 128, cy: 138, rx: 66, ry: 68 };
const BODY = "M84 176 C62 196 64 230 88 238 Q128 248 168 238 C192 230 194 196 172 176 Z";
const P = PALETTE.bunny;

export function Bunny() {
  return <PetSvg species="bunny">
    <PetDefs species="bunny" head={HEAD} body={BODY} />
    <Shadow rx={78} />
    <g data-part="tail" style={pivot(186, 218)}>
      <circle cx="196" cy="214" r="18" style={fill(P.fur)} />
      <circle cx="200" cy="220" r="10" style={fill(P.shade)} opacity=".7" />
    </g>
    <g data-part="body" style={pivot(128, 240)}>
      <path d={BODY} fill="url(#bunny-body)" />
      <g clipPath="url(#bunny-body-clip)"><ellipse cx="128" cy="248" rx="66" ry="20" style={fill(P.deep)} opacity=".45" /></g>
      <Grain species="bunny" clip="body" />
    </g>
    <g data-part="paws">
      <ellipse cx="106" cy="234" rx="16" ry="10" style={fill(P.fur)} />
      <ellipse cx="150" cy="234" rx="16" ry="10" style={fill(P.fur)} />
    </g>
    <g data-part="head" style={pivot(128, 206)}>
      <g data-part="ear-l" style={pivot(102, 86)}>
        <path d="M86 92 C74 60 76 14 94 6 C112 2 118 50 114 90 Z" style={fill(P.fur)} />
        <path d="M92 84 C86 58 88 26 96 20 C106 18 108 52 106 84 Z" style={fill(P.inner)} />
      </g>
      <g data-part="ear-r" style={pivot(154, 86)}>
        <path d="M170 92 C182 60 180 14 162 6 C144 2 138 50 142 90 Z" style={fill(P.fur)} />
        <path d="M164 84 C170 58 168 26 160 20 C150 18 148 52 150 84 Z" style={fill(P.inner)} />
      </g>
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill="url(#bunny-fur)" />
      <g clipPath="url(#bunny-head-clip)">
        <ellipse cx="128" cy="204" rx="84" ry="30" style={fill(P.shade)} opacity=".7" />
        <path d="M96 200 Q128 210 160 200 Q128 206 96 200 Z" style={fill(P.deep)} opacity=".6" />
      </g>
      <Grain species="bunny" clip="head" />
      <Rim head={HEAD} />
      <Face species="bunny" head={HEAD} />
    </g>
    <Accessories head={HEAD} neckY={202} />
  </PetSvg>;
}
