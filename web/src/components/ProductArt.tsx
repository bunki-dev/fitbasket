// Hand-drawn product illustrations in a risograph style: each colour layer is printed
// slightly off its ink outline, like a two-pass riso print. Products are fictional,
// so every pack and piece of produce is drawn rather than photographed.

const INK = "#1b2a4a";
const C = {
  blue: "#0078bf",
  pink: "#ff48b0",
  yellow: "#ffe800",
  green: "#00a95c",
  orange: "#ff6c2f",
  red: "#f15060",
  brown: "#a5602b",
  cream: "#fff6d6",
  leaf: "#68bd45",
  purple: "#765ba7",
  white: "#ffffff",
};
const BRAND_INKS = [C.blue, C.pink, C.green, C.orange, C.purple, C.red];

function brandInk(brand: string): string {
  let h = 0;
  for (const ch of brand) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return BRAND_INKS[h % BRAND_INKS.length];
}

/** A shape printed twice: colour layer nudged off-register, ink outline on top. */
function R({ d, fill, ink = true, w = 2.2 }: { d: string; fill?: string; ink?: boolean; w?: number }) {
  return (
    <>
      {fill && <path d={d} fill={fill} transform="translate(2.2 1.6)" />}
      {ink && <path d={d} fill="none" stroke={INK} strokeWidth={w} strokeLinejoin="round" strokeLinecap="round" />}
    </>
  );
}

const Label = ({ x, y, w, h, color, text }: { x: number; y: number; w: number; h: number; color: string; text: string }) => (
  <>
    <rect x={x + 1.5} y={y + 1.2} width={w} height={h} fill={color} />
    <rect x={x} y={y} width={w} height={h} fill="none" stroke={INK} strokeWidth={1.6} />
    <text x={x + w / 2} y={y + h / 2 + 3.2} textAnchor="middle" fontSize="8.5" fontWeight="700" fill={INK}
      fontFamily="'Atkinson Hyperlegible', sans-serif">
      {text}
    </text>
  </>
);

type Kind =
  | "tray" | "can" | "carton" | "eggs" | "tub" | "block" | "bag" | "bottle" | "jar" | "loaf" | "wraps" | "pouch"
  | "banana" | "avocado" | "lemon" | "capsicum" | "zucchini" | "carrot" | "onion" | "garlic" | "broccoli"
  | "sweet_potato" | "leaves";

const KIND: Record<string, Kind> = {
  chicken_breast: "tray", beef_mince_lean: "tray", salmon_fillet: "tray",
  canned_tuna: "can", tomatoes_canned: "can", chickpeas_canned: "can", black_beans_canned: "can",
  milk: "carton", eggs: "eggs", greek_yoghurt: "tub", feta: "tub", whey_protein: "tub",
  cheddar: "block", tofu_firm: "block",
  rolled_oats: "bag", brown_rice: "bag", wholemeal_pasta: "bag", berries_frozen: "bag",
  olive_oil: "bottle", soy_sauce: "bottle", peanut_butter: "jar", honey: "jar",
  wholemeal_bread: "loaf", wholemeal_wraps: "wraps", almonds: "pouch", taco_seasoning: "pouch",
  banana: "banana", avocado: "avocado", lemon: "lemon", capsicum: "capsicum", zucchini: "zucchini",
  carrot: "carrot", onion: "onion", garlic: "garlic", broccoli: "broccoli", sweet_potato: "sweet_potato",
  baby_spinach: "leaves", mixed_salad: "leaves",
};

// What's inside a pack, to tint the "window" or contents.
const CONTENT: Record<string, string> = {
  chicken_breast: "#ffc2b4", beef_mince_lean: C.red, salmon_fillet: C.orange,
  canned_tuna: C.blue, tomatoes_canned: C.red, chickpeas_canned: C.yellow, black_beans_canned: C.purple,
  rolled_oats: C.cream, brown_rice: "#e2c08d", wholemeal_pasta: "#e9b872", berries_frozen: C.purple,
  olive_oil: "#c4d600", soy_sauce: C.brown, peanut_butter: C.brown, honey: C.yellow,
  greek_yoghurt: C.white, feta: C.white, whey_protein: C.white, cheddar: C.yellow, tofu_firm: C.cream,
  almonds: C.brown, taco_seasoning: C.orange,
};

function initials(brand: string) {
  return brand
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function Art({ kind, ingredient, brand }: { kind: Kind; ingredient: string; brand: string }) {
  const b = brandInk(brand);
  const c = CONTENT[ingredient] ?? C.yellow;
  const tag = initials(brand);
  switch (kind) {
    case "tray":
      return (
        <>
          <R d="M18 46c2-12 18-16 26-10 6-6 20-4 18 10z" fill={c} />
          {ingredient === "salmon_fillet" && <R d="M28 40l4 6M38 38l4 7M48 38l3 7" w={1.4} />}
          {ingredient === "beef_mince_lean" && <R d="M26 42h2M34 39h2M44 41h2M52 40h2" w={2} />}
          <R d="M9 46h62l-7 18H16z" fill={C.white} />
          <Label x={31} y={50} w={18} h={10} color={b} text={tag} />
        </>
      );
    case "can":
      return (
        <>
          <R d="M24 18h32v48H24z" fill="#d9dde3" />
          <R d="M24 18c0-4 32-4 32 0M24 66c0 4 32 4 32 0" w={1.8} />
          <R d="M24 30h32v24H24z" fill={b} />
          <circle cx="40" cy="42" r="6.5" fill={c} stroke={INK} strokeWidth={1.6} />
        </>
      );
    case "carton":
      return (
        <>
          <R d="M26 26l14-12 14 12v42H26z" fill={C.white} />
          <R d="M26 26h28" w={1.6} />
          <R d="M26 40h28v16H26z" fill={b} />
          <text x="40" y="51.5" textAnchor="middle" fontSize="8.5" fontWeight="700" fill={C.white}
            fontFamily="'Atkinson Hyperlegible', sans-serif">{ingredient === "milk" ? "MILK" : tag}</text>
        </>
      );
    case "eggs":
      return (
        <>
          {[18, 31, 44, 57].map((x) => (
            <R key={x} d={`M${x} 44c0-10 4-15 6.5-15s6.5 5 6.5 15`} fill={C.cream} />
          ))}
          <R d="M10 44h60v10c-5 6-10 6-15 0-5 6-10 6-15 0-5 6-10 6-15 0-5 6-10 6-15 0z" fill={b} />
        </>
      );
    case "tub": {
      const big = ingredient === "whey_protein";
      return big ? (
        <>
          <R d="M22 22h36v6H22z" fill={INK} />
          <R d="M20 28h40v38H20z" fill={C.white} />
          <R d="M20 36h40v18H20z" fill={b} />
          <text x="40" y="48" textAnchor="middle" fontSize="9" fontWeight="700" fill={C.white}
            fontFamily="'Atkinson Hyperlegible', sans-serif">WHEY</text>
        </>
      ) : (
        <>
          <R d="M17 30h46v6H17z" fill={b} />
          <R d="M19 36h42l-5 26H24z" fill={c} />
          <Label x={31} y={42} w={18} h={10} color={C.yellow} text={tag} />
        </>
      );
    }
    case "block":
      return (
        <>
          <R d="M14 40l16-12h36l-16 12z" fill={c} />
          <R d="M14 40h36v20H14zM50 40l16-12v20l-16 12" fill={c} />
          <Label x={21} y={45} w={22} h={10} color={b} text={tag} />
        </>
      );
    case "bag":
      return (
        <>
          <R d="M22 16q18-5 36 0l3 50q-21 6-42 0z" fill={b} />
          <R d="M30 30h20v20H30z" fill={c} />
          {ingredient === "berries_frozen" ? (
            <>
              <circle cx="36" cy="38" r="3" fill={C.pink} stroke={INK} strokeWidth={1.2} />
              <circle cx="44" cy="43" r="3" fill={C.blue} stroke={INK} strokeWidth={1.2} />
            </>
          ) : (
            <R d="M34 36l2 2M42 34l2 2M38 42l2 2M45 44l2 2" w={1.4} />
          )}
          <R d="M22 22q18-4 36 0" w={1.4} />
        </>
      );
    case "bottle":
      return (
        <>
          <R d="M35 8h10v8H35z" fill={INK} />
          <R d="M35 16h10v6c10 4 12 10 12 18v26H23V40c0-8 2-14 12-18z" fill={c} />
          <R d="M23 44h34v14H23z" fill={C.white} />
          <text x="40" y="54" textAnchor="middle" fontSize="8" fontWeight="700" fill={b}
            fontFamily="'Atkinson Hyperlegible', sans-serif">{tag}</text>
        </>
      );
    case "jar":
      return (
        <>
          <R d="M26 20h28v8H26z" fill={b} />
          <R d="M24 28h32c4 0 4 4 4 8v24c0 6-4 8-8 8H28c-4 0-8-2-8-8V36c0-4 0-8 4-8z" fill={c} />
          <Label x={28} y={42} w={24} h={12} color={C.white} text={tag} />
        </>
      );
    case "loaf":
      return (
        <>
          <R d="M12 42q0-20 28-20t28 20v22H12z" fill="#e9b872" />
          <R d="M24 32q4-4 8 0M38 30q4-4 8 0M52 32q4-4 8 0" w={1.4} />
          <Label x={28} y={48} w={24} h={10} color={b} text={tag} />
        </>
      );
    case "wraps":
      return (
        <>
          <R d="M14 52a26 10 0 1 0 52 0a26 10 0 1 0-52 0" fill={C.cream} />
          <R d="M14 46a26 10 0 1 0 52 0a26 10 0 1 0-52 0" fill="#e9b872" />
          <R d="M14 40a26 10 0 1 0 52 0a26 10 0 1 0-52 0" fill={C.cream} />
          <Label x={30} y={35} w={20} h={10} color={b} text={tag} />
        </>
      );
    case "pouch":
      return (
        <>
          <R d="M22 16h36l2 50H20z" fill={b} />
          <R d="M22 22h36" w={1.4} />
          <circle cx="40" cy="44" r="10" fill={c} stroke={INK} strokeWidth={1.8} />
        </>
      );
    case "banana":
      return <R d="M16 30c6 22 34 30 50 14 2-2 0-6-3-4-14 10-34 6-40-12-2-4-8-2-7 2z" fill={C.yellow} />;
    case "avocado":
      return (
        <>
          <R d="M40 12c10 0 10 16 16 26s2 30-16 30-22-20-16-30 6-26 16-26z" fill={C.leaf} />
          <R d="M40 42a8 8 0 1 0 .1 0" fill={C.brown} />
        </>
      );
    case "lemon":
      return <R d="M14 42c0-12 12-22 26-22s26 10 26 22-12 20-26 20-26-8-26-20zM12 42h4M64 42h4" fill={C.yellow} />;
    case "capsicum":
      return (
        <>
          <R d="M22 28c4-6 12-5 18-1 6-4 14-5 18 1 6 9 6 24 1 33-2 5-7 7-11 4-3 4-6 4-8 0-2 4-5 4-8 0-4 3-9 1-11-4-5-9-5-24 1-33z" fill={C.red} />
          <R d="M34 34c-2 8-2 18 0 26M46 34c2 8 2 18 0 26" w={1.3} />
          <path d="M40 27c0-6 2-10 7-13" stroke={C.green} strokeWidth={5} fill="none" strokeLinecap="round"
            transform="translate(2 1.5)" />
          <R d="M40 27c0-6 2-10 7-13" w={2.4} />
        </>
      );
    case "zucchini":
      return (
        <>
          <R d="M12 50c4-6 40-26 54-22 4 2 2 8-2 10-16 10-42 20-50 16-3-1-4-2-2-4z" fill={C.green} />
          <R d="M64 30l6-4" w={3} />
        </>
      );
    case "carrot":
      return (
        <>
          <R d="M28 26l24 6-14 40c-2 2-4 2-4 0z" fill={C.orange} />
          <R d="M36 34l8 2M34 44l6 2M33 54l4 1" w={1.4} />
          <R d="M38 26c-4-8-2-14 0-16M42 27c2-8 6-12 10-12M34 26c-6-4-10-4-12-2" fill={undefined} w={2.4} />
          <path d="M38 26c-4-8-2-14 0-16M42 27c2-8 6-12 10-12" stroke={C.leaf} strokeWidth={4} fill="none"
            transform="translate(2 1.5)" strokeLinecap="round" />
        </>
      );
    case "onion":
      return (
        <>
          <R d="M40 16c4 8 22 14 22 30 0 14-10 20-22 20s-22-6-22-20c0-16 18-22 22-30z" fill="#d9a066" />
          <R d="M34 30c-4 8-4 20 0 30M46 30c4 8 4 20 0 30" w={1.4} />
        </>
      );
    case "garlic":
      return (
        <>
          <R d="M40 14c2 8 20 14 20 30 0 14-10 20-20 20s-20-6-20-20c0-16 18-22 20-30z" fill={C.white} />
          <R d="M40 30v32M32 34c-4 8-4 18 0 26M48 34c4 8 4 18 0 26" w={1.4} />
        </>
      );
    case "broccoli":
      return (
        <>
          <R d="M36 46l-4 22h16l-4-22z" fill={C.leaf} />
          <R d="M20 40c-4-10 6-18 12-14 2-10 18-10 20 0 8-4 16 6 10 14-2 8-10 8-14 6-4 4-12 4-16 0-4 2-10 2-12-6z" fill={C.green} />
        </>
      );
    case "sweet_potato":
      return <R d="M12 48c0-12 20-22 40-20s18 14 14 20-20 12-36 10-18-4-18-10z" fill={C.purple} />;
    case "leaves":
      return (
        <>
          <R d="M16 22h48l-4 44H20z" fill="#e6f4f8" />
          <R d="M26 56c-4-14 4-24 14-26-2 10-6 20-14 26zM54 56c4-14-4-24-14-26 2 10 6 20 14 26z" fill={C.leaf} />
          <R d="M40 58c-6-12-2-22 0-26 2 4 6 14 0 26z" fill={C.green} />
          <Label x={30} y={24} w={20} h={9} color={b} text={tag} />
        </>
      );
  }
}

export function ProductArt({ ingredient, brand, name }: { ingredient: string; brand: string; name: string }) {
  let kind: Kind = KIND[ingredient] ?? "bag";
  if (ingredient === "broccoli" && /frozen/i.test(name)) kind = "bag";
  return (
    <svg viewBox="0 0 80 80" width="64" height="64" role="img" aria-label={name} className="product-art">
      <Art kind={kind} ingredient={ingredient} brand={brand} />
    </svg>
  );
}
