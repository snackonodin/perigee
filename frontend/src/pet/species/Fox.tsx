// The fox: tall pointed ears with dark tips, cream muzzle and bib, flared cheeks, big brush
// tail with a cream tip, dark socks. Head 124 of ~219 total (ear tip y 22 -> paws y 241) = 57%.
import { Accessories, FOX_CREAM, FOX_TIP, Face, Grain, PALETTE, PetDefs, PetSvg, Rim, Shadow, fill, pivot, type HeadGeo } from "./shared";

const HEAD: HeadGeo = { cx: 128, cy: 108, rx: 86, ry: 62 };
const BODY = "M88 150 C66 172 60 214 78 232 Q128 246 178 232 C196 214 190 172 168 150 Z";
const P = PALETTE.fox;

export function Fox() {
  return <PetSvg species="fox">
    <PetDefs species="fox" head={HEAD} body={BODY} />
    <Shadow rx={92} />
    <g data-part="tail" style={pivot(176, 218)}>
      <path d="M170 226 C214 236 246 206 240 166 C236 140 214 128 204 144 C196 168 214 186 190 206 Z" style={fill(P.shade)} />
      <path d="M240 166 C236 140 214 128 204 144 C208 150 226 152 240 166 Z" style={fill(FOX_CREAM)} />
    </g>
    <g data-part="body" style={pivot(128, 238)}>
      <path d={BODY} fill="url(#fox-body)" />
      <g clipPath="url(#fox-body-clip)">
        <path d="M100 150 Q128 214 156 150 Z" style={fill(FOX_CREAM)} />
        <ellipse cx="128" cy="246" rx="70" ry="22" style={fill(P.deep)} opacity=".4" />
      </g>
      <Grain species="fox" clip="body" />
    </g>
    <g data-part="paws">
      <ellipse cx="104" cy="230" rx="18" ry="11" style={fill(FOX_TIP)} />
      <ellipse cx="152" cy="230" rx="18" ry="11" style={fill(FOX_TIP)} />
    </g>
    <g data-part="head" style={pivot(128, 170)}>
      <g data-part="ear-l" style={pivot(80, 78)}>
        <path d="M50 96 Q46 44 62 22 Q80 28 112 62 Z" style={fill(P.fur)} />
        <path d="M54 50 Q56 32 62 22 Q72 26 82 36 Q66 38 54 50 Z" style={fill(FOX_TIP)} />
        <path d="M64 86 Q62 56 68 44 Q82 50 98 66 Z" style={fill(FOX_CREAM)} />
      </g>
      <g data-part="ear-r" style={pivot(176, 78)}>
        <path d="M206 96 Q210 44 194 22 Q176 28 144 62 Z" style={fill(P.fur)} />
        <path d="M202 50 Q200 32 194 22 Q184 26 174 36 Q190 38 202 50 Z" style={fill(FOX_TIP)} />
        <path d="M192 86 Q194 56 188 44 Q174 50 158 66 Z" style={fill(FOX_CREAM)} />
      </g>
      <path d="M52 118 Q30 138 24 146 Q44 152 66 146 Z" style={fill(P.fur)} />
      <path d="M204 118 Q226 138 232 146 Q212 152 190 146 Z" style={fill(P.fur)} />
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill="url(#fox-fur)" />
      <g clipPath="url(#fox-head-clip)">
        <ellipse cx="128" cy="166" rx="100" ry="26" style={fill(P.shade)} opacity=".6" />
        <path d="M66 128 Q96 120 128 134 Q160 120 190 128 Q182 176 128 178 Q74 176 66 128 Z" style={fill(FOX_CREAM)} />
      </g>
      <Grain species="fox" clip="head" />
      <Rim head={HEAD} />
      <Face species="fox" head={HEAD} />
    </g>
    <Accessories head={HEAD} neckY={158} />
  </PetSvg>;
}
