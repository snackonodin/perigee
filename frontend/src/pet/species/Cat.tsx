// The cat: pointed ears, round cheeks, curled tail. Sitting pose, viewBox 256.
// Head 128 tall of ~212 total (ear tip y 26 -> paw bottom y 238) = 60%.
import { Accessories, Face, Grain, PALETTE, PetDefs, PetSvg, Rim, Shadow, fill, pivot, stroke, type HeadGeo } from "./shared";

const HEAD: HeadGeo = { cx: 128, cy: 100, rx: 84, ry: 64 };
const BODY = "M86 146 C64 170 58 214 76 232 Q128 246 180 232 C198 214 192 170 170 146 Z";
const P = PALETTE.cat;

export function Cat() {
  return <PetSvg species="cat">
    <PetDefs species="cat" head={HEAD} body={BODY} />
    <Shadow />
    <g data-part="tail" style={pivot(182, 216)}>
      <path d="M178 222 C214 226 230 196 216 170 C208 156 192 160 196 174" style={stroke(P.shade, 16)} />
      <path d="M202 166 C196 160 190 166 194 174" style={stroke(P.deep, 12)} />
    </g>
    <g data-part="body" style={pivot(128, 238)}>
      <path d={BODY} fill="url(#cat-body)" />
      <g clipPath="url(#cat-body-clip)">
        <ellipse cx="128" cy="244" rx="70" ry="22" style={fill(P.deep)} opacity=".45" />
      </g>
      <Grain species="cat" clip="body" />
    </g>
    <g data-part="paws">
      <ellipse cx="104" cy="230" rx="18" ry="11" style={fill(P.fur)} />
      <ellipse cx="152" cy="230" rx="18" ry="11" style={fill(P.fur)} />
      <path d="M98 232 v4 M110 232 v4 M146 232 v4 M158 232 v4" style={stroke(P.shade, 4)} />
    </g>
    <g data-part="head" style={pivot(128, 164)}>
      <g data-part="ear-l" style={pivot(80, 70)}>
        <path d="M52 92 Q44 42 58 26 Q74 26 108 54 Z" style={fill(P.fur)} />
        <path d="M64 82 Q60 52 68 40 Q80 44 96 60 Z" style={fill(P.inner)} />
      </g>
      <g data-part="ear-r" style={pivot(176, 70)}>
        <path d="M204 92 Q212 42 198 26 Q182 26 148 54 Z" style={fill(P.fur)} />
        <path d="M192 82 Q196 52 188 40 Q176 44 160 60 Z" style={fill(P.inner)} />
      </g>
      <circle cx="48" cy="118" r="13" style={fill(P.fur)} />
      <circle cx="208" cy="118" r="13" style={fill(P.fur)} />
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill="url(#cat-fur)" />
      <g clipPath="url(#cat-head-clip)">
        <ellipse cx="128" cy="160" rx="100" ry="34" style={fill(P.shade)} opacity=".7" />
        <path d="M88 160 Q128 172 168 160 Q128 168 88 160 Z" style={fill(P.deep)} opacity=".6" />
      </g>
      <Grain species="cat" clip="head" />
      <Rim head={HEAD} />
      <Face species="cat" head={HEAD} />
    </g>
    <Accessories head={HEAD} neckY={152} />
  </PetSvg>;
}
