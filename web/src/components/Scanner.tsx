import { useEffect, useRef, useState } from "react";
import { validBarcode } from "../runtime/foodlog";

// Chrome on Android has a built-in BarcodeDetector. Safari (iPhone) doesn't, so we load the
// ZXing decoder from a CDN the first time the scanner opens.
const ZXING_URL = "https://cdn.jsdelivr.net/npm/@zxing/browser@0.2.1/+esm";
const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e"];

interface Detector {
  detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>;
}
type DetectorCtor = new (opts: { formats: string[] }) => Detector;
interface ZxingControls {
  stop(): void;
}
interface ZxingReader {
  decodeFromConstraints(
    c: MediaStreamConstraints,
    video: HTMLVideoElement,
    cb: (result: { getText(): string } | undefined) => void,
  ): Promise<ZxingControls>;
  decodeFromImageUrl(url: string): Promise<{ getText(): string }>;
}

const nativeDetector = (): Detector | null => {
  const Ctor = (globalThis as { BarcodeDetector?: DetectorCtor }).BarcodeDetector;
  return Ctor ? new Ctor({ formats: FORMATS }) : null;
};

async function zxingReader(): Promise<ZxingReader> {
  const mod = await import(/* @vite-ignore */ ZXING_URL);
  return new mod.BrowserMultiFormatReader() as ZxingReader;
}

const CONSTRAINTS: MediaStreamConstraints = {
  video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
  audio: false,
};

export function Scanner({ onCode, onClose }: { onCode: (code: string) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [status, setStatus] = useState("Starting the camera…");
  const [typed, setTyped] = useState("");
  const done = useRef(false);

  const finish = (code: string) => {
    if (done.current || !validBarcode(code)) return;
    done.current = true;
    navigator.vibrate?.(60);
    onCode(code);
  };

  useEffect(() => {
    let stop = () => {};
    let cancelled = false;
    (async () => {
      try {
        const native = nativeDetector();
        if (native) {
          const stream = await navigator.mediaDevices.getUserMedia(CONSTRAINTS);
          if (cancelled) return stream.getTracks().forEach((t) => t.stop());
          const v = video.current!;
          v.srcObject = stream;
          await v.play();
          setStatus("Point the camera at the barcode");
          let timer = 0;
          const tick = async () => {
            if (cancelled || done.current) return;
            try {
              const [hit] = await native.detect(v);
              if (hit) finish(hit.rawValue);
            } catch {
              /* frame not ready */
            }
            timer = window.setTimeout(tick, 150);
          };
          tick();
          stop = () => {
            clearTimeout(timer);
            stream.getTracks().forEach((t) => t.stop());
          };
        } else {
          const reader = await zxingReader();
          if (cancelled) return;
          const controls = await reader.decodeFromConstraints(CONSTRAINTS, video.current!, (result) => {
            if (result) finish(result.getText());
          });
          setStatus("Point the camera at the barcode");
          stop = () => controls.stop();
          if (cancelled) stop();
        }
      } catch (e) {
        const name = (e as Error).name;
        setStatus(
          name === "NotAllowedError"
            ? "Camera access is off. Allow it in your browser settings, take a photo, or type the barcode."
            : "The camera isn't available here. Take a photo of the barcode or type its numbers.",
        );
      }
    })();
    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  async function fromPhoto(file: File) {
    setStatus("Reading the photo…");
    const url = URL.createObjectURL(file);
    try {
      const native = nativeDetector();
      if (native) {
        const img = await createImageBitmap(file);
        const [hit] = await native.detect(img);
        if (hit) return finish(hit.rawValue);
      } else {
        const res = await (await zxingReader()).decodeFromImageUrl(url);
        return finish(res.getText());
      }
      setStatus("No barcode found in that photo. Try closer, with the lines filling the frame.");
    } catch {
      setStatus("No barcode found in that photo. Try closer, with the lines filling the frame.");
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  return (
    <div className="scanner" role="dialog" aria-modal="true" aria-label="Scan a barcode">
      <div className="scanner-view">
        <video ref={video} playsInline muted autoPlay />
        <div className="scanner-frame" aria-hidden />
      </div>
      <p className="scanner-status" aria-live="polite">
        {status}
      </p>
      <div className="scanner-actions">
        <label className="photo-btn">
          Take a photo instead
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => e.target.files?.[0] && fromPhoto(e.target.files[0])}
          />
        </label>
        <form
          className="type-code"
          onSubmit={(e) => {
            e.preventDefault();
            finish(typed.trim());
          }}
        >
          <label htmlFor="barcode">Or type the numbers under the barcode</label>
          <div>
            <input
              id="barcode"
              inputMode="numeric"
              pattern="[0-9]*"
              value={typed}
              onChange={(e) => setTyped(e.target.value.replace(/\D/g, ""))}
              placeholder="9300650018860"
            />
            <button type="submit" disabled={!validBarcode(typed)}>
              Look up
            </button>
          </div>
        </form>
        <button type="button" className="scanner-close" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  );
}
