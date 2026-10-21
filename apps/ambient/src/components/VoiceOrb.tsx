import React, { useEffect, useRef, useCallback, useState } from "react";
import siriOrbImage from "../assets/siri_orb.png";

interface VoiceOrbProps {
  onSpeechEnd?: (text: string) => void;
  onWakeWord?: (phrase?: string) => void;
  statusText?: string;
  isProcessing?: boolean;
  isSpeaking?: boolean;
}

interface FluidBlob {
  angle: number;
  baseSpeed: number;
  baseOrbitR: number;
  baseR: number;
  colorCore: string;
  colorOuter: string;
  phase: number;
}

interface FluidDroplet {
  x: number;
  y: number;
  radius: number;
  speed: number;
  angle: number;
  orbit: number;
  color: string;
  alpha: number;
}

export const VoiceOrb: React.FC<VoiceOrbProps> = ({
  onSpeechEnd,
  onWakeWord,
  statusText,
  isProcessing = false,
  isSpeaking = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const recognitionRef = useRef<any>(null);
  const volumeRef = useRef<number>(0);
  const isListeningRef = useRef<boolean>(true);
  const [shimmerActive, setShimmerActive] = useState<boolean>(false);

  const isSpeakingRef = useRef<boolean>(isSpeaking);
  isSpeakingRef.current = isSpeaking;

  const isProcessingRef = useRef<boolean>(isProcessing);
  isProcessingRef.current = isProcessing;

  // Ripples list for click / wake-word shockwaves
  const ripplesRef = useRef<{ r: number; maxR: number; alpha: number }[]>([]);

  // Trigger ripple shockwave and glass shimmer
  const triggerGleam = useCallback(() => {
    setShimmerActive(true);
    ripplesRef.current.push({ r: 5, maxR: 54, alpha: 0.85 });
    setTimeout(() => {
      setShimmerActive(false);
    }, 750);
  }, []);

  // Initialize Microphone & Web Audio Analyser
  const initAudio = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.75;
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      let smoothVol = 0;

      const checkVolume = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);

        let sum = 0;
        const count = dataArray.length;
        for (let i = 0; i < count; i++) {
          sum += dataArray[i];
        }
        const avg = sum / count;
        // Non-linear normalized speech detection
        const rawVol = Math.min(1, Math.max(0, (avg - 8) / 65));
        smoothVol = smoothVol * 0.75 + rawVol * 0.25;
        volumeRef.current = smoothVol;

        animFrameRef.current = requestAnimationFrame(checkVolume);
      };

      animFrameRef.current = requestAnimationFrame(checkVolume);
    } catch (err) {
      console.warn("[VoiceOrb] Mic permission not yet active, using gentle idle pulse:", err);
      // Gentle breathing idle if mic access is not yet permitted
      let t = 0;
      const fakePulse = () => {
        t += 0.03;
        volumeRef.current = (Math.sin(t) + 1) * 0.06;
        animFrameRef.current = requestAnimationFrame(fakePulse);
      };
      animFrameRef.current = requestAnimationFrame(fakePulse);
    }
  }, []);

  // Initialize Speech Recognition with Wake-Word Detection & Auto-Restart
  const initSpeechRecognition = useCallback(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) return;

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-IN";

      let silenceTimer: ReturnType<typeof setTimeout> | null = null;

      recognition.onresult = (event: any) => {
        // Echo cancellation: Do not listen to self while assistant is speaking or processing
        if (isSpeakingRef.current || isProcessingRef.current) {
          if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
          }
          return;
        }

        let currentTranscript = "";
        let hasFinal = false;

        for (let i = event.resultIndex; i < event.results.length; i++) {
          currentTranscript += event.results[i][0]?.transcript || "";
          if (event.results[i]?.isFinal) {
            hasFinal = true;
          }
        }
        const clean = currentTranscript.trim();
        if (!clean || clean.length < 2) return;

        // If user finished a substantive command (>3 words or punctuation), dispatch on final
        const words = clean.split(/\s+/);
        if (hasFinal && (words.length >= 3 || /[.?!]$/.test(clean))) {
          if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
          }
          triggerGleam();
          if (onSpeechEnd) {
            onSpeechEnd(clean);
          }
          return;
        }

        // Natural conversational pause (1200ms) giving the user time to breathe and finish
        if (silenceTimer) clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => {
          if (clean.length > 1 && !isSpeakingRef.current && !isProcessingRef.current) {
            triggerGleam();
            if (onSpeechEnd) {
              onSpeechEnd(clean);
            }
          }
        }, 1200);
      };

      recognition.onerror = (event: any) => {
        console.debug("[VoiceOrb] SpeechRecognition status:", event.error);
        if (event.error !== "not-allowed" && isListeningRef.current) {
          setTimeout(() => {
            try {
              recognition.start();
            } catch { }
          }, 800);
        }
      };

      recognition.onend = () => {
        if (isListeningRef.current) {
          try {
            recognition.start();
          } catch { }
        }
      };

      recognition.start();
      recognitionRef.current = recognition;
    } catch (err) {
      console.debug("[VoiceOrb] SpeechRecognition fallback:", err);
    }
  }, [onSpeechEnd, triggerGleam]);

  useEffect(() => {
    isListeningRef.current = true;
    initAudio();
    initSpeechRecognition();

    return () => {
      isListeningRef.current = false;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => { });
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch { }
      }
    };
  }, [initAudio, initSpeechRecognition]);

  // Click handler
  const handleClick = useCallback(() => {
    triggerGleam();
    if (onWakeWord) onWakeWord("click");
  }, [onWakeWord, triggerGleam]);

  // Canvas Liquid Plasma Simulation Engine
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Retina pixel ratio
    const dpr = window.devicePixelRatio || 2;
    const size = 116; // Perfectly fits 116px orb container without clipping
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(dpr, dpr);

    const center = size / 2;
    const radius = size / 2 - 1.5; // ~56.5px sphere radius

    // 7 dynamic fluid plasma nodes matching the exact Apple Siri Orb reference image colors
    const blobs: FluidBlob[] = [
      {
        angle: 0.2,
        baseSpeed: 0.009,
        baseOrbitR: 12,
        baseR: 24,
        colorCore: "rgba(0, 240, 255, 0.90)", // Electric Neon Cyan
        colorOuter: "rgba(0, 186, 255, 0.02)",
        phase: 0.0,
      },
      {
        angle: 1.25,
        baseSpeed: -0.008,
        baseOrbitR: 15,
        baseR: 26,
        colorCore: "rgba(217, 70, 239, 0.85)", // Radiant Siri Magenta
        colorOuter: "rgba(168, 85, 247, 0.02)",
        phase: 1.1,
      },
      {
        angle: 2.3,
        baseSpeed: 0.011,
        baseOrbitR: 13,
        baseR: 23,
        colorCore: "rgba(56, 189, 248, 0.90)", // Azure Blue
        colorOuter: "rgba(2, 132, 199, 0.02)",
        phase: 2.3,
      },
      {
        angle: 3.4,
        baseSpeed: -0.009,
        baseOrbitR: 11,
        baseR: 27,
        colorCore: "rgba(236, 72, 153, 0.82)", // Soft Violet Pink
        colorOuter: "rgba(190, 24, 93, 0.02)",
        phase: 3.5,
      },
      {
        angle: 4.5,
        baseSpeed: 0.008,
        baseOrbitR: 16,
        baseR: 25,
        colorCore: "rgba(37, 99, 235, 0.88)", // Deep Sapphire Cobalt
        colorOuter: "rgba(29, 78, 216, 0.02)",
        phase: 4.7,
      },
      {
        angle: 5.4,
        baseSpeed: -0.010,
        baseOrbitR: 14,
        baseR: 24,
        colorCore: "rgba(34, 211, 238, 0.85)", // Luminous Turquoise
        colorOuter: "rgba(8, 145, 178, 0.02)",
        phase: 5.6,
      },
      {
        angle: 2.8,
        baseSpeed: 0.007,
        baseOrbitR: 8,
        baseR: 22,
        colorCore: "rgba(255, 255, 255, 0.92)", // Luminous White Crest
        colorOuter: "rgba(56, 189, 248, 0.03)",
        phase: 1.7,
      },
    ];

    // Floating fluid micro-droplets for organic liquid texture
    const droplets: FluidDroplet[] = Array.from({ length: 6 }).map((_, i) => ({
      x: 0,
      y: 0,
      radius: 1.2 + Math.random() * 1.5,
      speed: 0.012 + Math.random() * 0.015 * (i % 2 === 0 ? 1 : -1),
      angle: (i / 6) * Math.PI * 2,
      orbit: 8 + Math.random() * 16,
      color: i % 2 === 0 ? "rgba(255, 255, 255, 0.85)" : "rgba(56, 189, 248, 0.9)",
      alpha: 0.4 + Math.random() * 0.4,
    }));

    let animationId: number;
    let time = 0;

    const render = () => {
      time += 0.016;
      const vol = volumeRef.current;
      const isSpeakingVal = isSpeakingRef.current;
      const isProcessingVal = isProcessingRef.current;

      // Pulse calculations
      const speakingPulse = isSpeakingVal ? Math.sin(time * 7.5) * 0.3 + 0.48 : 0;
      const processingPulse = isProcessingVal ? Math.sin(time * 12) * 0.2 + 0.35 : 0;
      const effectiveVol = Math.max(vol, speakingPulse, processingPulse);

      // Speed multiplier: calm idle -> rapid fluid vortex when speaking or processing
      let speedMultiplier = 1.0 + effectiveVol * 6.5;
      if (isProcessingVal) {
        speedMultiplier = 3.8 + Math.sin(time * 5) * 0.8;
      }

      // Clear transparent canvas
      ctx.clearRect(0, 0, size, size);

      // Clip strictly to smooth circular glass interior
      ctx.save();
      ctx.beginPath();
      ctx.arc(center, center, radius, 0, Math.PI * 2);
      ctx.closePath();
      ctx.clip();

      // Switch to luminous screen blend for vibrant liquid plasma directly on top of Siri Orb
      ctx.globalCompositeOperation = "screen";

      // Modulate plasma intensity: subtle breathing idle, intense vibrant flares on speech/processing
      const plasmaAlpha = Math.min(1.0, 0.25 + effectiveVol * 0.75);
      ctx.globalAlpha = plasmaAlpha;

      // Render each swirling liquid blob with harmonic non-linear convection
      for (let i = 0; i < blobs.length; i++) {
        const b = blobs[i];

        // Advance fluid angle with speed
        b.angle += b.baseSpeed * speedMultiplier;

        // Dynamic fluid orbit: breathes organically, expands on audio volume
        const orbitR =
          b.baseOrbitR +
          Math.sin(time * 1.8 + b.phase) * 1.8 +
          Math.cos(time * 1.2 + b.phase) * 1.2 +
          effectiveVol * 8.5;

        // Dynamic blob radius with non-linear viscosity
        const r =
          b.baseR +
          Math.sin(time * 2.5 + b.phase) * 1.5 +
          effectiveVol * 6.5;

        // Coordinated fluid convection coordinates
        const bx = center + Math.cos(b.angle) * orbitR;
        const by = center + Math.sin(b.angle) * orbitR;

        // Multi-stop liquid radial gradient
        const grad = ctx.createRadialGradient(bx, by, 0, bx, by, r);
        grad.addColorStop(0, b.colorCore);
        grad.addColorStop(0.55, b.colorCore);
        grad.addColorStop(0.85, b.colorOuter);
        grad.addColorStop(1, "rgba(0, 0, 0, 0)");

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(bx, by, r, 0, Math.PI * 2);
        ctx.fill();
      }

      // Render floating micro-droplets
      for (let i = 0; i < droplets.length; i++) {
        const d = droplets[i];
        d.angle += d.speed * (speedMultiplier * 0.8);
        const dx = center + Math.cos(d.angle) * d.orbit;
        const dy = center + Math.sin(d.angle) * d.orbit;

        ctx.fillStyle = d.color;
        ctx.beginPath();
        ctx.arc(dx, dy, d.radius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Render acoustic ripple rings
      if (ripplesRef.current.length > 0) {
        ctx.globalCompositeOperation = "lighter";
        for (let i = ripplesRef.current.length - 1; i >= 0; i--) {
          const rip = ripplesRef.current[i];
          rip.r += 1.4;
          rip.alpha -= 0.025;

          if (rip.alpha <= 0 || rip.r >= rip.maxR) {
            ripplesRef.current.splice(i, 1);
            continue;
          }

          ctx.strokeStyle = `rgba(56, 189, 248, ${Math.max(0, rip.alpha)})`;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(center, center, rip.r, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      // Gentle internal glass caustic glow overlay
      const causticGrad = ctx.createRadialGradient(
        center + 12,
        center + 14,
        2,
        center + 12,
        center + 14,
        radius * 0.75
      );
      causticGrad.addColorStop(0, "rgba(56, 189, 248, 0.22)");
      causticGrad.addColorStop(0.5, "rgba(45, 212, 191, 0.08)");
      causticGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = causticGrad;
      ctx.beginPath();
      ctx.arc(center, center, radius, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();

      animationId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, []);

  return (
    <div
      className="liquid-glass-container"
      onClick={handleClick}
      title="Click or say 'Hey Nexus' to talk"
    >
      {/* Outer ambient caustic glow */}
      <div
        className={`liquid-glass-ambient-glow ${isProcessing ? "processing" : ""} ${isSpeaking ? "speaking" : ""
          }`}
      />

      {/* Main Glass Sphere Housing */}
      <div
        className={`liquid-glass-orb ${isProcessing ? "processing" : ""} ${isSpeaking ? "speaking" : ""
          }`}
      >
        {/* Layer 1: Frosted Glass Substrate with Backdrop Filter */}
        <div className="liquid-glass-substrate" />

        {/* Layer 2: Apple Siri Orb Master Texture */}
        <img
          src={siriOrbImage}
          alt="NEXUS Apple Siri Orb"
          className="liquid-glass-siri-base"
          draggable={false}
        />

        {/* Layer 3: Dynamic Audio-Reactive Canvas Liquid Waveforms */}
        <canvas ref={canvasRef} className="liquid-glass-canvas" />

        {/* Layer 4: Internal Caustic Light Pool */}
        <div className="liquid-glass-caustic-pool" />

        {/* Layer 4.5: Glowing NEXUS Logo SVG Emblem */}
        <div className="liquid-glass-nexus-logo">
          <svg
            viewBox="0 0 100 100"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="nexus-center-svg"
          >
            <defs>
              <linearGradient id="nexusSvgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#38bdf8" />
                <stop offset="45%" stopColor="#818cf8" />
                <stop offset="100%" stopColor="#e879f9" />
              </linearGradient>
              <filter id="nexusSvgGlow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            {/* Luminous NEXUS 4-pointed radiant star emblem */}
            <path
              d="M50 12 C50 34 66 50 88 50 C66 50 50 66 50 88 C50 66 34 50 12 50 C34 50 50 34 50 12 Z"
              fill="url(#nexusSvgGrad)"
              filter="url(#nexusSvgGlow)"
              opacity="0.95"
            />
            {/* Central Pure White Diamond Specular Core */}
            <polygon
              points="50,44 54,50 50,56 46,50"
              fill="#ffffff"
              opacity="0.95"
            />
          </svg>
        </div>

        {/* Layer 5: Prismatic Chromatic Dispersion Edge Ring */}
        <div className="liquid-glass-chromatic-ring" />

        {/* Layer 6: Primary Specular Crescent Highlight (Apple Glass Style) */}
        <div className="liquid-glass-specular-primary" />

        {/* Layer 7: Secondary Ambient Specular Sheen */}
        <div className="liquid-glass-specular-secondary" />

        {/* Layer 8: Crisp Top Bezel Rim Light */}
        <div className="liquid-glass-top-rim" />

        {/* Layer 9: Interactive Glass Shimmer on Click/Wake */}
        {shimmerActive && <div className="liquid-glass-shimmer" />}
      </div>

      {/* Floating Micro Glass Status Badge */}
      {statusText && (
        <div className="liquid-glass-status-badge">
          <span className="liquid-glass-status-dot" />
          <span className="liquid-glass-status-text">{statusText}</span>
        </div>
      )}
    </div>
  );
};
