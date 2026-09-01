"use client";

import { useEffect, useState, useRef } from "react";
import Sidebar from "@/components/Sidebar";

const API_BASE = "http://127.0.0.1:8000";

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

interface Field {
  field_name: string;
  field_value: string | null;
  ocr_confidence: number;
}

interface Check {
  rule_id: string;
  rule_citation: string;
  description?: string;
  severity?: string;
  fix_suggestion?: string;
  status: string;
  explanation: string;
}

interface ScanDetail {
  id: string;
  created_at: string;
  input_type: string;
  image_path: string | null;
  authenticity_score: number;
  object_classification: string;
  fields: Field[];
  checks: Check[];
  authenticity_report?: {
    is_authentic: boolean;
    exif: { status: string; details: string; exif_present: boolean; editing_software_detected: boolean };
    fft: { status: string; details: string; fft_variance: number };
    ela: { status: string; details: string; ela_variance: number; ela_image_url: string | null };
  };
  report_pdf_url: string;
}

interface ScanSummary {
  id: string;
  created_at: string;
  input_type: string;
  authenticity_score: number;
  object_classification: string;
}

export default function Dashboard() {
  // Consumer Auth State
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);

  // Auth Form State
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Regulatory Domain Category State
  const [selectedCategory, setSelectedCategory] = useState<"food" | "apparel" | "general">("food");

  // Navigation & Data
  const [history, setHistory] = useState<ScanSummary[]>([]);
  const [selectedScan, setSelectedScan] = useState<ScanDetail | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Scanning State
  const [scanning, setScanning] = useState(false);
  const [scanStep, setScanStep] = useState(0);
  const [scanError, setScanError] = useState<string | null>(null);

  // Form Inputs
  const [inputUrl, setInputUrl] = useState("");
  const [webcamActive, setWebcamActive] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Restore authenticated session from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem("packaudit_consumer_user");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed && parsed.email) {
          setCurrentUser(parsed);
        }
      }
    } catch {
      localStorage.removeItem("packaudit_consumer_user");
    } finally {
      setAuthChecking(false);
    }
  }, []);

  // Password validation rules
  const hasMinLength = password.length >= 8;
  const hasUpperCase = /[A-Z]/.test(password);
  const hasLowerCase = /[a-z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>\-_+=\[\]]/.test(password);
  const passwordsMatch = password.length > 0 && password === confirmPassword;

  const validScore = [hasMinLength, hasUpperCase, hasLowerCase, hasDigit, hasSpecialChar].filter(Boolean).length;
  const isPasswordValid = validScore === 5;
  const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  // Load Scan History when logged in
  const loadHistory = () => {
    setLoadingHistory(true);
    fetch(`${API_BASE}/api/scans/history`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch history");
        return res.json();
      })
      .then((data) => {
        setHistory(Array.isArray(data) ? data : []);
        setLoadingHistory(false);
      })
      .catch(() => {
        setHistory([]);
        setLoadingHistory(false);
      });
  };

  useEffect(() => {
    if (currentUser) {
      loadHistory();
    }
  }, [currentUser]);

  // Handle Login & Signup Submit
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);

    // Client-side validations
    if (!isEmailValid) {
      setAuthError("Please enter a valid email address (e.g. name@domain.com).");
      return;
    }

    if (authMode === "signup") {
      if (!fullName.trim()) {
        setAuthError("Please enter your full name.");
        return;
      }
      if (!isPasswordValid) {
        setAuthError("Password does not meet the security requirements.");
        return;
      }
      if (!passwordsMatch) {
        setAuthError("Passwords do not match. Please re-enter.");
        return;
      }
    }

    setAuthLoading(true);
    const endpoint = authMode === "signup" ? "/api/auth/signup" : "/api/auth/login";
    const payload = authMode === "signup" 
      ? { email: email.trim().toLowerCase(), full_name: fullName.trim(), password }
      : { email: email.trim().toLowerCase(), password };

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed. Please check your details.");
      }

      const user: User = data.user;
      setCurrentUser(user);
      localStorage.setItem("packaudit_consumer_user", JSON.stringify(user));
      if (data.access_token) {
        localStorage.setItem("packaudit_token", data.access_token);
      }
    } catch (err: any) {
      setAuthError(err.message || "Unable to complete request. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem("packaudit_consumer_user");
    localStorage.removeItem("packaudit_token");
    setCurrentUser(null);
    setSelectedScan(null);
    setPassword("");
    setConfirmPassword("");
  };

  // Set scanning steps labels
  const PIPELINE_STEPS = [
    "Uploading target media...",
    "Analyzing EXIF & image headers...",
    "Computing FFT variance & ELA compression error maps...",
    "Evaluating package classifier (YOLOv8)...",
    `Routing to ${selectedCategory.toUpperCase()} regulatory engine...`,
    "Running multilingual OCR (English & Hindi)...",
    "Extracting domain-specific statutory declarations...",
    "Executing statutory rule checks (25 parameters)...",
    "Assembling report & compiling PDF..."
  ];

  const executeAudit = async (endpoint: string, formData: FormData) => {
    setScanning(true);
    setScanStep(0);
    setScanError(null);

    const interval = setInterval(() => {
      setScanStep((prev) => (prev < PIPELINE_STEPS.length - 2 ? prev + 1 : prev));
    }, 450);

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Audit request failed with HTTP ${res.status}`);
      }

      setScanStep(PIPELINE_STEPS.length - 1);
      const data: ScanDetail = await res.json();
      setSelectedScan(data);
      loadHistory();
    } catch (err: any) {
      setScanError(err.message || "Failed to process audit. Please try again with a clearer photo or link.");
    } finally {
      clearInterval(interval);
      setScanning(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];

    const formData = new FormData();
    formData.append("file", file);
    formData.append("category", selectedCategory);

    await executeAudit("/api/scans/upload", formData);
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputUrl) return;

    const formData = new FormData();
    formData.append("url", inputUrl);
    formData.append("category", selectedCategory);

    await executeAudit("/api/scans/url", formData);
  };

  const startWebcam = async () => {
    setWebcamActive(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch {
      alert("Unable to access camera. Please check browser permissions.");
      setWebcamActive(false);
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      if (!blob) return;
      closeWebcam();

      const formData = new FormData();
      formData.append("file", blob, "webcam_capture.jpg");
      formData.append("category", selectedCategory);

      executeAudit("/api/scans/upload", formData);
    }, "image/jpeg");
  };

  const closeWebcam = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setWebcamActive(false);
  };

  const loadScanDetails = (scanId: string) => {
    fetch(`${API_BASE}/api/scans/${scanId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load scan");
        return res.json();
      })
      .then((data) => {
        setSelectedScan(data);
      })
      .catch((err) => {
        alert("Failed to load scan record: " + err.message);
      });
  };

  const getStatusColor = (checks: Check[]) => {
    if (!Array.isArray(checks)) return { text: "UNKNOWN", class: "border-[#737373]/20 bg-[#737373]/5 text-[#A3A3A3]" };
    const fails = checks.filter((c) => c.status === "fail");
    const unverifiable = checks.filter((c) => c.status === "unverifiable");
    if (fails.length > 0) {
      return { text: "NON-COMPLIANT", class: "border-[#DC2626]/20 bg-[#DC2626]/5 text-[#EF4444]" };
    }
    if (unverifiable.length > 0) {
      return { text: "WARNING (UNVERIFIABLE)", class: "border-[#F59E0B]/20 bg-[#F59E0B]/5 text-[#F59E0B]" };
    }
    return { text: "COMPLIANT", class: "border-[#10B981]/20 bg-[#10B981]/5 text-[#10B981]" };
  };

  if (authChecking) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0A0A0A] text-[#EDEDED] font-mono text-xs">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin"></div>
          <span>Loading PackAudit Consumer Portal...</span>
        </div>
      </div>
    );
  }

  // If user is not logged in, render Clean Centered Login / Signup Screen (No Sidebar)
  if (!currentUser) {
    return (
      <div className="min-h-screen w-full bg-[#070707] text-[#EDEDED] flex flex-col justify-between selection:bg-[#10B981]/30">
        {/* Top Navbar */}
        <header className="h-16 border-b border-[#1F1F1F] bg-[#0A0A0A] flex items-center justify-between px-8">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-[#10B981]/10 border border-[#10B981]/30 flex items-center justify-center text-[#10B981] font-mono font-bold text-sm">
              🛡️
            </div>
            <div>
              <span className="font-mono text-sm font-bold tracking-tight text-[#EDEDED] block">
                PACKAUDIT
              </span>
              <span className="text-[10px] font-mono text-[#737373] block">
                Consumer Legal Metrology & Food Safety
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs text-[#737373]">
            <span className="w-2 h-2 rounded-full bg-[#10B981]"></span>
            <span>Consumer Protection Portal</span>
          </div>
        </header>

        {/* Center Auth Card */}
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-md bg-[#0F0F0F] border border-[#262626] rounded-xl p-8 shadow-2xl space-y-6">
            <div className="space-y-2 text-center">
              <span className="text-[10px] font-mono font-bold tracking-wider uppercase px-2.5 py-1 rounded-full bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/20">
                Citizen & Consumer Access
              </span>
              <h1 className="text-xl font-bold font-mono text-[#EDEDED] tracking-tight mt-2">
                {authMode === "login" ? "Sign in to PackAudit" : "Create Consumer Account"}
              </h1>
              <p className="text-xs text-[#737373] font-mono">
                {authMode === "login"
                  ? "Verify packaged goods, check MRP compliance, and detect tampered labels."
                  : "Join PackAudit to audit consumer packaging, check FSSAI licenses, and verify fiber blends."}
              </p>
            </div>

            {/* Mode Switch Tabs */}
            <div className="grid grid-cols-2 p-1 bg-[#141414] border border-[#262626] rounded-lg font-mono text-xs">
              <button
                type="button"
                onClick={() => { setAuthMode("login"); setAuthError(null); }}
                className={`py-2 rounded-md transition font-medium ${
                  authMode === "login"
                    ? "bg-[#10B981] text-[#0A0A0A] font-bold shadow"
                    : "text-[#737373] hover:text-[#EDEDED]"
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => { setAuthMode("signup"); setAuthError(null); }}
                className={`py-2 rounded-md transition font-medium ${
                  authMode === "signup"
                    ? "bg-[#10B981] text-[#0A0A0A] font-bold shadow"
                    : "text-[#737373] hover:text-[#EDEDED]"
                }`}
              >
                Create Account
              </button>
            </div>

            {/* Error Banner */}
            {authError && (
              <div className="p-3 bg-[#DC2626]/10 border border-[#DC2626]/30 rounded-lg text-xs font-mono text-[#EF4444] flex items-start gap-2">
                <span className="shrink-0 font-bold">⚠️</span>
                <span className="leading-snug">{authError}</span>
              </div>
            )}

            {/* Authentication Form */}
            <form onSubmit={handleAuthSubmit} className="space-y-4 font-mono text-xs">
              {authMode === "signup" && (
                <div className="space-y-1.5">
                  <label className="text-[#A3A3A3] font-medium flex justify-between">
                    <span>Full Name</span>
                    <span className="text-[#737373] text-[10px]">required</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Salina Tamboli"
                    className="w-full px-3.5 py-2.5 rounded-lg bg-[#141414] border border-[#262626] text-[#EDEDED] focus:border-[#10B981] focus:outline-none transition"
                  />
                </div>
              )}

              {/* Email Input */}
              <div className="space-y-1.5">
                <label className="text-[#A3A3A3] font-medium flex justify-between">
                  <span>Email Address</span>
                  {email.length > 0 && (
                    <span className={`text-[10px] ${isEmailValid ? "text-[#10B981]" : "text-[#EF4444]"}`}>
                      {isEmailValid ? "✓ Valid email format" : "✕ Invalid format"}
                    </span>
                  )}
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className={`w-full px-3.5 py-2.5 rounded-lg bg-[#141414] border text-[#EDEDED] focus:outline-none transition ${
                    email.length > 0
                      ? isEmailValid
                        ? "border-[#10B981]/50 focus:border-[#10B981]"
                        : "border-[#DC2626]/50 focus:border-[#DC2626]"
                      : "border-[#262626] focus:border-[#10B981]"
                  }`}
                />
              </div>

              {/* Password Input */}
              <div className="space-y-1.5">
                <label className="text-[#A3A3A3] font-medium flex justify-between">
                  <span>Password</span>
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-[#737373] hover:text-[#EDEDED] text-[10px]"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </label>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your secure password"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-[#141414] border border-[#262626] text-[#EDEDED] focus:border-[#10B981] focus:outline-none transition"
                />
              </div>

              {/* Password Requirement Checklist (Shown on Signup) */}
              {authMode === "signup" && (
                <div className="space-y-2 p-3 bg-[#141414] border border-[#262626] rounded-lg text-[11px]">
                  <div className="flex justify-between items-center text-[#737373]">
                    <span>Password Strength:</span>
                    <span className={`font-bold ${
                      validScore === 5 ? "text-[#10B981]" : validScore >= 3 ? "text-[#F59E0B]" : "text-[#EF4444]"
                    }`}>
                      {validScore === 5 ? "Strong" : validScore >= 3 ? "Moderate" : "Weak"}
                    </span>
                  </div>

                  {/* Strength Bar */}
                  <div className="w-full h-1 bg-[#262626] rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        validScore === 5 ? "bg-[#10B981]" : validScore >= 3 ? "bg-[#F59E0B]" : "bg-[#EF4444]"
                      }`}
                      style={{ width: `${(validScore / 5) * 100}%` }}
                    ></div>
                  </div>

                  {/* Requirements grid */}
                  <div className="grid grid-cols-2 gap-1 text-[10px] pt-1">
                    <span className={hasMinLength ? "text-[#10B981]" : "text-[#737373]"}>
                      {hasMinLength ? "✓" : "○"} 8+ characters
                    </span>
                    <span className={hasUpperCase ? "text-[#10B981]" : "text-[#737373]"}>
                      {hasUpperCase ? "✓" : "○"} 1 uppercase (A-Z)
                    </span>
                    <span className={hasLowerCase ? "text-[#10B981]" : "text-[#737373]"}>
                      {hasLowerCase ? "✓" : "○"} 1 lowercase (a-z)
                    </span>
                    <span className={hasDigit ? "text-[#10B981]" : "text-[#737373]"}>
                      {hasDigit ? "✓" : "○"} 1 number (0-9)
                    </span>
                    <span className={`col-span-2 ${hasSpecialChar ? "text-[#10B981]" : "text-[#737373]"}`}>
                      {hasSpecialChar ? "✓" : "○"} 1 special symbol (@, #, $, %, etc.)
                    </span>
                  </div>
                </div>
              )}

              {/* Confirm Password (Shown on Signup) */}
              {authMode === "signup" && (
                <div className="space-y-1.5">
                  <label className="text-[#A3A3A3] font-medium flex justify-between">
                    <span>Confirm Password</span>
                    {confirmPassword.length > 0 && (
                      <span className={`text-[10px] ${passwordsMatch ? "text-[#10B981]" : "text-[#EF4444]"}`}>
                        {passwordsMatch ? "✓ Passwords match" : "✕ Passwords do not match"}
                      </span>
                    )}
                  </label>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter your password"
                    className="w-full px-3.5 py-2.5 rounded-lg bg-[#141414] border border-[#262626] text-[#EDEDED] focus:border-[#10B981] focus:outline-none transition"
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={authLoading}
                className="w-full py-3 rounded-lg bg-[#10B981] hover:bg-[#059669] text-[#0A0A0A] font-bold font-mono transition text-xs flex items-center justify-center gap-2 shadow-lg disabled:opacity-50"
              >
                {authLoading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-[#0A0A0A] border-t-transparent rounded-full animate-spin"></div>
                    <span>Processing...</span>
                  </>
                ) : (
                  <span>{authMode === "login" ? "Sign In to Dashboard" : "Create Consumer Account"}</span>
                )}
              </button>
            </form>

            {/* Quick Demo Consumer Preset */}
            <div className="pt-2 border-t border-[#1F1F1F] text-center space-y-2">
              <span className="text-[10px] text-[#737373] font-mono block">
                Quick Demo Preset:
              </span>
              <button
                type="button"
                onClick={() => {
                  setAuthMode("login");
                  setEmail("salina.consumer@gmail.com");
                  setPassword("SecurePassword@2026");
                }}
                className="text-[11px] font-mono text-[#10B981] hover:underline"
              >
                Auto-fill Demo Consumer Credentials
              </button>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="h-12 border-t border-[#1F1F1F] bg-[#0A0A0A] flex items-center justify-between px-8 text-xs font-mono text-[#737373]">
          <span>Legal Metrology Act 2009 | FSSAI Regulations 2020</span>
          <span>PackAudit v1.0.0</span>
        </footer>
      </div>
    );
  }

  // Main Authenticated Workspace with Sidebar
  return (
    <div className="flex min-h-screen bg-[#0A0A0A] text-[#EDEDED]">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Console Layout */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Top Console Bar */}
        <header className="h-14 border-b border-[#262626] bg-[#0A0A0A] flex items-center justify-between px-6 z-10 shrink-0">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-bold tracking-tight text-[#EDEDED]">
              PACKAUDIT CONSUMER PORTAL
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-[#10B981]/10 text-[#10B981] font-mono">
              LM + FSSAI + TEXTILE
            </span>
          </div>

          {/* Consumer Profile & Sign Out */}
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span className="text-[#A3A3A3]">Consumer:</span>
              <span className="text-[#10B981] font-bold">{currentUser.full_name}</span>
              <button
                onClick={handleSignOut}
                className="text-[10px] text-[#EF4444] hover:text-[#FF6B6B] border border-[#DC2626]/30 hover:border-[#DC2626]/60 px-2 py-0.5 rounded transition ml-2"
              >
                Sign Out
              </button>
            </div>
          </div>
        </header>

        {/* Main Workspace Layout */}
        <div className="flex-1 grid grid-cols-12 overflow-hidden h-[calc(100vh-3.5rem)]">
          {/* Left Side: Operations */}
          <section className="col-span-4 border-r border-[#262626] bg-[#0A0A0A] p-6 space-y-6 overflow-y-auto flex flex-col h-full">
            {/* 3-Category Regulatory Domain Selector */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase flex items-center justify-between">
                <span>Target Category</span>
                <span className="text-[10px] text-[#10B981] lowercase">required for audit routing</span>
              </label>
              <div className="grid grid-cols-3 gap-1.5 p-1 bg-[#0F0F0F] border border-[#262626] rounded text-xs font-mono">
                <button
                  type="button"
                  onClick={() => setSelectedCategory("food")}
                  className={`py-2 px-1 rounded transition text-center flex flex-col items-center gap-0.5 ${
                    selectedCategory === "food"
                      ? "bg-[#10B981] text-[#0A0A0A] font-bold shadow"
                      : "text-[#A3A3A3] hover:text-[#EDEDED] hover:bg-[#151515]"
                  }`}
                >
                  <span>🍏 Food & Bev</span>
                  <span className="text-[9px] opacity-80">FSSAI 2020</span>
                </button>

                <button
                  type="button"
                  onClick={() => setSelectedCategory("apparel")}
                  className={`py-2 px-1 rounded transition text-center flex flex-col items-center gap-0.5 ${
                    selectedCategory === "apparel"
                      ? "bg-[#EC4899] text-[#0A0A0A] font-bold shadow"
                      : "text-[#A3A3A3] hover:text-[#EDEDED] hover:bg-[#151515]"
                  }`}
                >
                  <span>👕 Apparel</span>
                  <span className="text-[9px] opacity-80">Textile 2011</span>
                </button>

                <button
                  type="button"
                  onClick={() => setSelectedCategory("general")}
                  className={`py-2 px-1 rounded transition text-center flex flex-col items-center gap-0.5 ${
                    selectedCategory === "general"
                      ? "bg-[#3B82F6] text-[#0A0A0A] font-bold shadow"
                      : "text-[#A3A3A3] hover:text-[#EDEDED] hover:bg-[#151515]"
                  }`}
                >
                  <span>📦 General</span>
                  <span className="text-[9px] opacity-80">Legal Metro</span>
                </button>
              </div>
            </div>

            {/* Uploader Section */}
            <div className="space-y-3">
              <h2 className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase">
                Upload / Camera Scan
              </h2>

              {webcamActive ? (
                <div className="border border-[#262626] bg-[#0F0F0F] rounded overflow-hidden flex flex-col items-center">
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    className="w-full bg-black aspect-video object-cover"
                  ></video>
                  <div className="p-3 flex gap-2 w-full justify-between border-t border-[#262626]">
                    <button
                      onClick={closeWebcam}
                      className="px-3 py-1.5 rounded text-xs bg-[#262626] text-[#EDEDED] font-mono hover:bg-[#333333]"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={capturePhoto}
                      className="px-3 py-1.5 rounded text-xs bg-[#10B981] text-[#0A0A0A] font-mono font-bold hover:bg-[#059669]"
                    >
                      Capture Photo
                    </button>
                  </div>
                  <canvas ref={canvasRef} className="hidden"></canvas>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex flex-col items-center justify-center p-4 border border-dashed border-[#262626] bg-[#0F0F0F] hover:border-[#10B981] hover:bg-[#151515] transition rounded text-center cursor-pointer"
                  >
                    <svg
                      className="w-6 h-6 text-[#737373] mb-2"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                    <span className="text-xs font-mono font-medium">Upload Label Photo</span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleFileUpload}
                    />
                  </button>

                  <button
                    onClick={startWebcam}
                    className="flex flex-col items-center justify-center p-4 border border-dashed border-[#262626] bg-[#0F0F0F] hover:border-[#10B981] hover:bg-[#151515] transition rounded text-center cursor-pointer"
                  >
                    <svg
                      className="w-6 h-6 text-[#737373] mb-2"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                    </svg>
                    <span className="text-xs font-mono font-medium">Live Camera</span>
                  </button>
                </div>
              )}
            </div>

            {/* URL Scraper Section */}
            <div className="space-y-3">
              <h2 className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase">
                Scrape URL Listing
              </h2>
              <form onSubmit={handleUrlSubmit} className="flex gap-2">
                <input
                  type="url"
                  required
                  value={inputUrl}
                  onChange={(e) => setInputUrl(e.target.value)}
                  placeholder="Amazon/Flipkart product URL..."
                  className="flex-1 px-3 py-2 rounded text-xs bg-[#0F0F0F] border border-[#262626] text-[#EDEDED] font-mono focus:border-[#10B981] focus:outline-none"
                />
                <button
                  type="submit"
                  className="px-3 py-2 rounded text-xs bg-[#10B981] text-[#0A0A0A] font-mono font-bold hover:bg-[#059669]"
                >
                  Scrape
                </button>
              </form>
            </div>

            {/* Audit History Log */}
            <div className="flex-1 flex flex-col min-h-0 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase">
                  Compliance History
                </h2>
                <span className="text-[10px] font-mono text-[#737373]">
                  {Array.isArray(history) ? history.length : 0} Audits
                </span>
              </div>

              {loadingHistory ? (
                <div className="text-xs text-[#737373] p-4 font-mono">Loading history logs...</div>
              ) : !Array.isArray(history) || history.length === 0 ? (
                <div className="text-xs text-[#737373] border border-[#262626] rounded p-6 text-center font-mono">
                  No past compliance audits found.
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto space-y-1.5 min-h-0 pr-1">
                  {(Array.isArray(history) ? history : []).map((scan) => (
                    <button
                      key={scan.id}
                      onClick={() => loadScanDetails(scan.id)}
                      className="w-full p-3 text-left border border-[#262626] bg-[#0F0F0F] hover:bg-[#151515] transition rounded flex items-center justify-between"
                    >
                      <div className="space-y-1">
                        <div className="font-mono text-xs font-bold text-[#EDEDED] truncate max-w-[160px]">
                          ID: {scan.id.slice(0, 8)}
                        </div>
                        <div className="text-[10px] font-mono text-[#737373]">
                          {new Date(scan.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} | {scan.input_type.toUpperCase()}
                        </div>
                      </div>
                      <div className="text-right space-y-1">
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#262626] text-[#A3A3A3] block w-fit ml-auto">
                          {scan.object_classification}
                        </span>
                        <span className="text-[10px] font-mono text-[#737373] block">
                          Auth: {scan.authenticity_score}%
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Right Side: Compliance Report Viewer */}
          <section className="col-span-8 bg-[#070707] flex flex-col h-full relative overflow-y-auto">
            {scanning ? (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center space-y-6">
                <div className="w-10 h-10 rounded-full border-2 border-[#262626] border-t-[#10B981] animate-spin"></div>
                <div className="space-y-2 max-w-md">
                  <h3 className="font-mono text-sm font-bold text-[#EDEDED]">
                    Executing Statutory Compliance Audit
                  </h3>
                  <p className="text-xs text-[#10B981] font-mono">
                    {PIPELINE_STEPS[scanStep]}
                  </p>
                  <div className="w-48 h-1 bg-[#1A1A1A] rounded overflow-hidden mx-auto mt-2">
                    <div
                      className="h-full bg-[#10B981] transition-all duration-300"
                      style={{ width: `${((scanStep + 1) / PIPELINE_STEPS.length) * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            ) : scanError ? (
              <div className="flex-1 flex items-center justify-center p-12">
                <div className="max-w-md border border-[#DC2626]/20 bg-[#DC2626]/5 rounded p-6 space-y-3">
                  <h3 className="font-mono text-sm font-bold text-[#EF4444] flex items-center gap-2">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                      />
                    </svg>
                    Audit Process Aborted
                  </h3>
                  <p className="text-xs text-[#D4D4D4] leading-relaxed font-mono">
                    {scanError}
                  </p>
                  <button
                    onClick={() => setScanError(null)}
                    className="px-3 py-1.5 rounded text-xs bg-[#262626] text-[#EDEDED] font-mono hover:bg-[#333333] transition"
                  >
                    Dismiss & Try Again
                  </button>
                </div>
              </div>
            ) : selectedScan ? (
              // Full Compliance Report View
              <div className="p-8 space-y-8">
                {/* Header Panel */}
                <div className="flex items-center justify-between border-b border-[#262626] pb-6">
                  <div>
                    <h2 className="text-xl font-bold tracking-tight text-[#EDEDED] font-mono">
                      Statutory Compliance Report
                    </h2>
                    <p className="text-xs text-[#737373] mt-1 font-mono">
                      Scan ID: {selectedScan.id} | Audited for: <span className="text-[#EDEDED] font-bold">{currentUser.full_name}</span> | {new Date(selectedScan.created_at).toLocaleString()}
                    </p>
                  </div>

                  <div className="flex gap-3">
                    <a
                      href={`${API_BASE}${selectedScan.report_pdf_url}`}
                      download
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 px-3 py-2 border border-[#262626] bg-[#0F0F0F] hover:bg-[#1A1A1A] transition text-xs font-mono text-[#EDEDED] rounded"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                        />
                      </svg>
                      Export PDF Report
                    </a>
                  </div>
                </div>

                {/* Status & Authenticity Overview */}
                <div className="grid grid-cols-3 gap-4">
                  {/* 1. Overall Status Card */}
                  {(() => {
                    const status = getStatusColor(selectedScan.checks);
                    return (
                      <div
                        className={`border p-4 rounded flex flex-col justify-between h-28 ${status.class}`}
                      >
                        <span className="text-[10px] font-mono font-bold tracking-wider uppercase text-[#737373]">
                          Statutory Audit Status
                        </span>
                        <span className="text-lg font-bold font-mono tracking-tight">
                          {status.text}
                        </span>
                      </div>
                    );
                  })()}

                  {/* 2. Authenticity Score Card */}
                  <div
                    className={`border p-4 rounded flex flex-col justify-between h-28 ${
                      selectedScan.authenticity_score >= 70.0
                        ? "border-[#10B981]/20 bg-[#10B981]/5 text-[#10B981]"
                        : "border-[#DC2626]/20 bg-[#DC2626]/5 text-[#EF4444]"
                    }`}
                  >
                    <span className="text-[10px] font-mono font-bold tracking-wider uppercase text-[#737373]">
                      Image Authenticity Score
                    </span>
                    <span className="text-lg font-bold font-mono tracking-tight">
                      {selectedScan.authenticity_score}%
                    </span>
                  </div>

                  {/* 3. Package Classification Card */}
                  <div className="border border-[#262626] bg-[#0F0F0F] p-4 rounded flex flex-col justify-between h-28 text-[#EDEDED]">
                    <span className="text-[10px] font-mono font-bold tracking-wider uppercase text-[#737373]">
                      Target Object Class
                    </span>
                    <span className="text-lg font-bold font-mono tracking-tight truncate capitalize">
                      {selectedScan.object_classification ? selectedScan.object_classification.replace("_", " ") : "Retail Package"}
                    </span>
                  </div>
                </div>

                {/* Prominent Statutory Failure Summary Banner */}
                {(() => {
                  const failedChecks = (selectedScan.checks || []).filter(
                    (c) => c.status === "fail"
                  );
                  if (failedChecks.length === 0) {
                    return (
                      <div className="border border-[#10B981]/30 bg-[#10B981]/10 rounded p-4 flex items-start gap-3">
                        <div className="text-[#10B981] font-bold text-base leading-none mt-0.5">
                          ✓
                        </div>
                        <div className="space-y-1">
                          <div className="text-xs font-mono font-bold text-[#10B981]">
                            Fully Compliant with Statutory Regulations
                          </div>
                          <p className="text-[11px] font-mono text-[#A3A3A3]">
                            All statutory packaging declarations (MRP, Net Quantity, Origin, Mfg/Packer details, Consumer Care, Fiber/Size, Food Safety) verified successfully.
                          </p>
                        </div>
                      </div>
                    );
                  }

                  const severityWeight: Record<string, number> = {
                    CRITICAL: 3,
                    MAJOR: 2,
                    MINOR: 1
                  };
                  const sortedFails = [...failedChecks].sort(
                    (a, b) =>
                      (severityWeight[b.severity || "MAJOR"] || 2) -
                      (severityWeight[a.severity || "MAJOR"] || 2)
                  );
                  const topFails = sortedFails.slice(0, 3);
                  const remainingFails = sortedFails.length - topFails.length;

                  return (
                    <div className="border border-[#DC2626]/40 bg-[#DC2626]/10 rounded p-4 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-mono font-bold text-[#EF4444] flex items-center gap-2">
                          <svg
                            className="w-4 h-4 shrink-0"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.5"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                            />
                          </svg>
                          Non-Compliance Summary: {failedChecks.length} Statutory Violation
                          {failedChecks.length > 1 ? "s" : ""} Found
                        </div>
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#DC2626]/20 text-[#EF4444] uppercase">
                          Action Required
                        </span>
                      </div>

                      <div className="space-y-1.5 pt-1">
                        {topFails.map((fc) => (
                          <div
                            key={fc.rule_id}
                            className="text-xs font-mono text-[#EDEDED] flex items-start gap-2 bg-[#0A0A0A]/70 p-2.5 rounded border border-[#262626]"
                          >
                            <span className="text-[#EF4444] font-bold shrink-0">
                              {fc.rule_citation}:
                            </span>
                            <span className="text-[#C2C2C2] leading-snug">
                              {fc.explanation}
                            </span>
                          </div>
                        ))}
                        {remainingFails > 0 && (
                          <div className="text-[11px] font-mono text-[#A3A3A3] pt-1 italic">
                            + {remainingFails} additional statutory violation
                            {remainingFails > 1 ? "s" : ""} (see complete checklist table below)
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {/* Authenticity Maps */}
                {selectedScan.authenticity_report && (
                  <div className="space-y-4">
                    <h3 className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase">
                      Authenticity Verification
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      {/* ELA Visual Map */}
                      {selectedScan.authenticity_report.ela.ela_image_url ? (
                        <div className="border border-[#262626] bg-[#0F0F0F] rounded overflow-hidden flex flex-col">
                          <div className="p-3 border-b border-[#262626] bg-[#151515] flex justify-between items-center text-xs font-mono">
                            <span className="text-[#A3A3A3]">
                              Error Level Analysis (ELA) Map
                            </span>
                            <span className="text-[#737373]">
                              Var:{" "}
                              {selectedScan.authenticity_report.ela.ela_variance.toFixed(1)}
                            </span>
                          </div>
                          <img
                            src={`${API_BASE}${selectedScan.authenticity_report.ela.ela_image_url}`}
                            alt="ELA Map"
                            className="w-full aspect-video object-contain bg-black"
                          />
                        </div>
                      ) : (
                        <div className="border border-[#262626] bg-[#0F0F0F] rounded p-6 flex items-center justify-center text-xs font-mono text-[#737373] text-center">
                          ELA analysis bypassed for digital listing URLs.
                        </div>
                      )}

                      {/* Statistics details */}
                      <div className="border border-[#262626] bg-[#0F0F0F] rounded p-4 space-y-3 text-xs font-mono">
                        <div className="border-b border-[#262626] pb-2 font-bold text-[#A3A3A3]">
                          Image Forensics & Header Diagnostics
                        </div>

                        <div className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-[#737373]">EXIF Header Tags:</span>
                            <span
                              className={
                                selectedScan.authenticity_report.exif.exif_present
                                  ? "text-[#10B981]"
                                  : "text-[#F59E0B]"
                              }
                            >
                              {selectedScan.authenticity_report.exif.exif_present
                                ? "Present"
                                : "Missing / Stripped"}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-[#737373]">EXIF Editing Signatures:</span>
                            <span
                              className={
                                selectedScan.authenticity_report.exif.editing_software_detected
                                  ? "text-[#EF4444]"
                                  : "text-[#10B981]"
                              }
                            >
                              {selectedScan.authenticity_report.exif
                                .editing_software_detected
                                ? "Editing Tool Detected"
                                : "Clean Camera Raw"}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-[#737373]">FFT Spectral Variance:</span>
                            <span className="text-[#EDEDED]">
                              {selectedScan.authenticity_report.fft.fft_variance.toFixed(1)}
                            </span>
                          </div>
                        </div>
                        <div className="pt-2 border-t border-[#262626] text-[10px] text-[#A3A3A3] leading-relaxed">
                          <b>EXIF:</b> {selectedScan.authenticity_report.exif.details}
                          <br />
                          <b>FFT:</b> {selectedScan.authenticity_report.fft.details}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Extracted Declarations Table */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase">
                    Extracted Declarations
                  </h3>
                  <div className="border border-[#262626] bg-[#0F0F0F] rounded overflow-hidden">
                    <table className="w-full text-left border-collapse font-mono text-xs">
                      <thead>
                        <tr className="border-b border-[#262626] bg-[#151515] text-[#A3A3A3] font-bold">
                          <th className="p-3">Statutory Field</th>
                          <th className="p-3">Extracted Value</th>
                          <th className="p-3">
                            {selectedScan.input_type === "url" ||
                            selectedScan.object_classification === "e-commerce_listing"
                              ? "Extraction Confidence"
                              : "OCR Confidence"}
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#262626] text-[#EDEDED]">
                        {(selectedScan.fields || []).map((field) => (
                          <tr
                            key={field.field_name}
                            className="hover:bg-[#151515] transition"
                          >
                            <td className="p-3 font-bold text-[#A3A3A3]">
                              {field.field_name
                                ? field.field_name.replace("_", " ").toUpperCase()
                              : ""}
                            </td>
                            <td className="p-3 text-[#C2C2C2]">
                              {field.field_value || (
                                <span className="text-[#737373] italic">
                                  [Not Detected]
                                </span>
                              )}
                            </td>
                            <td className="p-3 text-[#737373]">
                              {((field.ocr_confidence || 1.0) * 100).toFixed(1)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Statutory Checklist Table (25 Checks) */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase">
                      Statutory Rule Checklist & Guidance (25 Rules)
                    </h3>
                    <div className="flex gap-2 text-[10px] font-mono text-[#737373]">
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6]"></span>
                        Legal Metrology (1-12)
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]"></span>
                        FSSAI Food (13-18)
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#EC4899]"></span>
                        Apparel & Textile (19-25)
                      </span>
                    </div>
                  </div>

                  <div className="border border-[#262626] bg-[#0F0F0F] rounded overflow-hidden">
                    <table className="w-full text-left border-collapse font-mono text-xs">
                      <thead>
                        <tr className="border-b border-[#262626] bg-[#151515] text-[#A3A3A3] font-bold">
                          <th className="p-3">Citation & Law</th>
                          <th className="p-3">Status</th>
                          <th className="p-3">Audit Details & Guidance</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#262626]">
                        {(selectedScan.checks || []).map((check) => {
                          let badgeClass = "bg-[#262626] text-[#737373]";
                          if (check.status === "pass")
                            badgeClass = "bg-[#10B981]/10 text-[#10B981]";
                          if (check.status === "fail")
                            badgeClass = "bg-[#DC2626]/10 text-[#EF4444]";
                          if (check.status === "unverifiable")
                            badgeClass = "bg-[#F59E0B]/10 text-[#F59E0B]";

                          const isFssai = check.rule_id.startsWith("fssai_");
                          const isApparel = check.rule_id.startsWith("apparel_");

                          return (
                            <tr
                              key={check.rule_id}
                              className="hover:bg-[#151515] transition"
                            >
                              <td className="p-3 font-bold text-[#EDEDED] max-w-[150px] align-top space-y-1">
                                <div>{check.rule_citation}</div>
                                <span
                                  className={`text-[9px] px-1.5 py-0.5 rounded font-mono block w-fit ${
                                    isFssai
                                      ? "bg-[#10B981]/10 text-[#10B981]"
                                      : isApparel
                                      ? "bg-[#EC4899]/10 text-[#F472B6]"
                                      : "bg-[#3B82F6]/10 text-[#60A5FA]"
                                  }`}
                                >
                                  {isFssai ? "FSSAI 2020" : isApparel ? "TEXTILE 2011" : "LM 2011"}
                                </span>
                              </td>
                              <td className="p-3 align-top">
                                <span
                                  className={`px-2 py-0.5 rounded font-bold uppercase tracking-wider ${badgeClass}`}
                                >
                                  {check.status}
                                </span>
                              </td>
                              <td className="p-3 space-y-1.5 align-top">
                                <div className="text-[#C2C2C2] leading-relaxed">
                                  {check.explanation}
                                </div>
                                {check.status === "fail" && check.fix_suggestion && (
                                  <div className="text-[11px] text-[#10B981] font-mono bg-[#10B981]/5 border border-[#10B981]/20 rounded p-2 flex items-start gap-1.5">
                                    <span className="font-bold shrink-0">
                                      💡 Consumer Tip:
                                    </span>
                                    <span className="leading-snug">
                                      {check.fix_suggestion}
                                    </span>
                                  </div>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : (
              // Empty State
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-[#737373] space-y-4">
                <svg
                  className="w-8 h-8 text-[#262626]"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <div className="space-y-1">
                  <h3 className="font-mono text-sm font-bold text-[#A3A3A3]">
                    No Product Audit Selected
                  </h3>
                  <p className="text-xs max-w-sm mx-auto font-mono">
                    Select a category above, then upload a product label photo, snap with live camera, or paste an e-commerce listing URL to audit.
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
