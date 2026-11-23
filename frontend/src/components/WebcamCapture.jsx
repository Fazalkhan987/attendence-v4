import { useEffect, useRef, useState } from "react";
import { Alert } from "./ui";

const PROMPTS = ["Look straight at the camera", "Turn slightly to your left", "Turn slightly to your right", "Tilt your chin up a little", "Tilt your chin down a little", "Smile naturally", "Neutral expression", "Look straight again"];

/** Opens the webcam and captures several JPEG frames (base64) for enrollment. */
export default function WebcamCapture({ target = 6, onChange }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [shots, setShots] = useState([]);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [auto, setAuto] = useState(false);

  const start = async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720, facingMode: "user" }, audio: false });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setReady(true);
    } catch (e) {
      setError("Could not open the camera. Allow camera access in the browser (needs https or localhost). " + (e.message || ""));
    }
  };

  const stop = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setReady(false);
    setAuto(false);
  };

  useEffect(() => stop, []);
  useEffect(() => { onChange?.(shots); }, [shots]); // eslint-disable-line

  const capture = () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    const data = c.toDataURL("image/jpeg", 0.92);
    setShots((s) => (s.length >= 10 ? s : [...s, data]));
  };

  // guided auto-capture: one frame every 1.6 s while the person follows the prompts
  useEffect(() => {
    if (!auto) return;
    if (shots.length >= target) { setAuto(false); return; }
    const t = setTimeout(capture, 1600);
    return () => clearTimeout(t);
  }, [auto, shots.length]); // eslint-disable-line

  return (
    <div>
      <Alert>{error}</Alert>
      <div className="cam">
        <video ref={videoRef} playsInline muted />
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        {!ready ? (
          <button type="button" className="btn primary" onClick={start}>Open camera</button>
        ) : (
          <>
            <button type="button" className="btn primary" onClick={() => { setShots([]); setAuto(true); }} disabled={auto}>
              {auto ? "Capturing…" : `Guided capture (${target} photos)`}
            </button>
            <button type="button" className="btn" onClick={capture}>Take photo</button>
            <button type="button" className="btn" onClick={stop}>Close camera</button>
          </>
        )}
        {shots.length > 0 && <button type="button" className="btn danger" onClick={() => setShots([])}>Clear</button>}
      </div>
      {auto && <div className="alert info" style={{ marginTop: 10 }}>{PROMPTS[shots.length % PROMPTS.length]} — {shots.length}/{target}</div>}
      <div className="thumbs">{shots.map((s, i) => <img key={i} src={s} alt={`sample ${i + 1}`} />)}</div>
      <div className="muted small" style={{ marginTop: 6 }}>{shots.length} photo(s) captured. Use good lighting, one face only, vary the angle slightly.</div>
    </div>
  );
}
