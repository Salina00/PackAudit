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
  product_name?: string;
  created_at: string;
  input_type: string;
  authenticity_score: number;
  object_classification: string;
  image_path?: string | null;
  compliance_status?: string;
  fail_count?: number;
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

  // Form Inputs & Multi-image State
  const [inputUrl, setInputUrl] = useState("");
  const [webcamActive, setWebcamActive] = useState(false);
  const [capturedBlobs, setCapturedBlobs] = useState<{ blob: Blob; url: string }[]>([]);

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

  // Handle Deleting a Single Scan
  const handleDeleteScan = async (scanId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/api/scans/${scanId}`, { method: "DELETE" });
      if (res.ok) {
        setHistory((prev) => prev.filter((s) => s.id !== scanId));
        if (selectedScan && selectedScan.id === scanId) {
          setSelectedScan(null);
        }
      }
    } catch (err) {
      console.error("Failed to delete scan", err);
    }
  };

  // Handle Clearing All Past History
  const handleClearAllHistory = async () => {
    if (!confirm("Are you sure you want to clear all audit history records?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/scans/history/clear`, { method: "DELETE" });
      if (res.ok) {
        setHistory([]);
        setSelectedScan(null);
      }
    } catch (err) {
      console.error("Failed to clear history", err);
    }
  };

  // Handle Login & Signup Submit
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);

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
    "Uploading target media (front & back)...",
    "Analyzing EXIF & image headers...",
    "Computing FFT variance & ELA compression error maps...",
    "Evaluating package classifier (YOLOv8)...",
    `Routing to ${selectedCategory.toUpperCase()} regulatory engine...`,
    "Running multilingual OCR (English & Hindi)...",
    "Aggregating declarations across package sides...",
    "Executing statutory rule checks (25 parameters)...",
    "Assembling report & compiling 1-page PDF..."
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

  // Multi-file upload handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }
    formData.append("category", selectedCategory);

    await executeAudit("/api/scans/upload", formData);
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputUrl || !inputUrl.trim()) return;

    let cleanUrl = inputUrl.trim();
    if (!cleanUrl.startsWith("http://") && !cleanUrl.startsWith("https://")) {
      cleanUrl = "https://" + cleanUrl;
    }

    const formData = new FormData();
    formData.append("url", cleanUrl);
    formData.append("category", selectedCategory);

    await executeAudit("/api/scans/url", formData);
  };

  const startWebcam = async () => {
    setWebcamActive(true);
    setCapturedBlobs([]);
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

  const snapWebcamPhoto = () => {
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
      const url = URL.createObjectURL(blob);
      setCapturedBlobs((prev) => [...prev, { blob, url }]);
    }, "image/jpeg");
  };

  const submitWebcamAudits = () => {
    if (capturedBlobs.length === 0) return;
    const formData = new FormData();
    capturedBlobs.forEach((item, index) => {
      formData.append("files", item.blob, `capture_${index + 1}.jpg`);
    });
    formData.append("category", selectedCategory);
    closeWebcam();
    executeAudit("/api/scans/upload", formData);
  };

  const closeWebcam = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setWebcamActive(false);
    setCapturedBlobs([]);
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

  // Helper for rendering date & time in local browser timezone
  const formatDateTime = (isoString: string) => {
    try {
      if (!isoString) return "";
      let raw = isoString;
      if (!raw.endsWith("Z") && !raw.includes("+") && !raw.includes("-", 10)) {
        raw = `${raw}Z`;
      }
      const d = new Date(raw);
      return d.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true
      });
    } catch {
      return isoString;
    }
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

            {authError && (
              <div className="p-3 bg-[#DC2626]/10 border border-[#DC2626]/30 rounded-lg text-xs font-mono text-[#EF4444] flex items-start gap-2">
                <span className="shrink-0 font-bold">⚠️</span>
                <span className="leading-snug">{authError}</span>
              </div>
            )}

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

                  <div className="w-full h-1 bg-[#262626] rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        validScore === 5 ? "bg-[#10B981]" : validScore >= 3 ? "bg-[#F59E0B]" : "bg-[#EF4444]"
                      }`}
                      style={{ width: `${(validScore / 5) * 100}%` }}
                    ></div>
                  </div>

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

        <footer className="h-12 border-t border-[#1F1F1F] bg-[#0A0A0A] flex items-center justify-between px-8 text-xs font-mono text-[#737373]">
          <span>Legal Metrology Act 2009 | FSSAI Regulations 2020</span>
          <span>PackAudit v1.0.0</span>
        </footer>
      </div>
    );
  }

  // Field dictionary helper for structured rendering
  const fieldMap: Record<string, string | null> = {};
  if (selectedScan && Array.isArray(selectedScan.fields)) {
    for (const f of selectedScan.fields) {
      fieldMap[f.field_name] = f.field_value;
    }
  }

  const totalChecks = (selectedScan?.checks || []).length;
  const passedChecks = (selectedScan?.checks || []).filter((c) => c.status === "pass" || c.status === "exempt").length;
  const failedChecks = (selectedScan?.checks || []).filter((c) => c.status === "fail");
  const unverifiableChecks = (selectedScan?.checks || []).filter((c) => c.status === "unverifiable");
  const isExempt = totalChecks > 0 && (selectedScan?.checks || []).every((c) => c.status === "exempt");

  const complianceScorePercent = totalChecks > 0 ? (passedChecks / totalChecks) * 100 : 100;

  let overallVerdict = "COMPLIANT";
  let verdictColorClass = "border-[#10B981] text-[#10B981] bg-[#10B981]/10";
  if (isExempt) {
    overallVerdict = "EXEMPT UNDER RULE 18";
    verdictColorClass = "border-[#3B82F6] text-[#3B82F6] bg-[#3B82F6]/10";
  } else if (complianceScorePercent >= 85) {
    overallVerdict = "COMPLIANT";
    verdictColorClass = "border-[#10B981] text-[#10B981] bg-[#10B981]/10";
  } else if (complianceScorePercent >= 70) {
    overallVerdict = "REQUIRES VERIFICATION";
    verdictColorClass = "border-[#F59E0B] text-[#F59E0B] bg-[#F59E0B]/10";
  } else {
    overallVerdict = "NON-COMPLIANT";
    verdictColorClass = "border-[#DC2626] text-[#EF4444] bg-[#DC2626]/10";
  }

  const selectedImagePaths = (selectedScan?.image_path || "").split(",").map((s) => s.trim()).filter(Boolean);

  return (
    <div className="flex min-h-screen bg-[#0A0A0A] text-[#EDEDED]">
      <Sidebar />

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
          {/* Left Side: Operations & History */}
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
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase">
                  Upload / Camera Scan
                </h2>
                <span className="text-[10px] font-mono text-[#10B981]">
                  Front + Back supported
                </span>
              </div>

              {webcamActive ? (
                <div className="border border-[#262626] bg-[#0F0F0F] rounded-lg overflow-hidden flex flex-col items-center p-3 space-y-3">
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    className="w-full bg-black aspect-video object-cover rounded"
                  ></video>

                  {/* Multi-snapshot preview tray */}
                  {capturedBlobs.length > 0 && (
                    <div className="w-full flex gap-2 overflow-x-auto pb-1">
                      {capturedBlobs.map((item, idx) => (
                        <div key={idx} className="relative shrink-0 w-16 h-12 rounded border border-[#10B981] overflow-hidden">
                          <img src={item.url} alt={`Side ${idx + 1}`} className="w-full h-full object-cover" />
                          <span className="absolute bottom-0 right-0 bg-[#0A0A0A]/90 text-[8px] px-1 font-mono text-[#10B981]">
                            #{idx + 1}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="flex gap-2 w-full justify-between pt-1">
                    <button
                      onClick={closeWebcam}
                      className="px-3 py-1.5 rounded text-xs bg-[#262626] text-[#EDEDED] font-mono hover:bg-[#333333]"
                    >
                      Cancel
                    </button>
                    <div className="flex gap-2">
                      <button
                        onClick={snapWebcamPhoto}
                        className="px-3 py-1.5 rounded text-xs bg-[#262626] text-[#EDEDED] font-mono hover:bg-[#333333] border border-[#333333]"
                      >
                        📷 Snap Side ({capturedBlobs.length})
                      </button>
                      <button
                        disabled={capturedBlobs.length === 0}
                        onClick={submitWebcamAudits}
                        className="px-3 py-1.5 rounded text-xs bg-[#10B981] text-[#0A0A0A] font-mono font-bold hover:bg-[#059669] disabled:opacity-50 shadow"
                      >
                        Run Audit
                      </button>
                    </div>
                  </div>
                  <canvas ref={canvasRef} className="hidden"></canvas>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex flex-col items-center justify-center p-4 border border-dashed border-[#262626] bg-[#0F0F0F] hover:border-[#10B981] hover:bg-[#151515] transition rounded-lg text-center cursor-pointer"
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
                    <span className="text-xs font-mono font-medium">Upload Photos</span>
                    <span className="text-[10px] text-[#737373] font-mono">Select Front + Back</span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={handleFileUpload}
                    />
                  </button>

                  <button
                    onClick={startWebcam}
                    className="flex flex-col items-center justify-center p-4 border border-dashed border-[#262626] bg-[#0F0F0F] hover:border-[#10B981] hover:bg-[#151515] transition rounded-lg text-center cursor-pointer"
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
                    <span className="text-[10px] text-[#737373] font-mono">Multi-side capture</span>
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
                  type="text"
                  value={inputUrl}
                  onChange={(e) => setInputUrl(e.target.value)}
                  placeholder="Amazon or Flipkart product URL..."
                  className="flex-1 px-3 py-2 rounded text-xs bg-[#0F0F0F] border border-[#262626] text-[#EDEDED] font-mono focus:border-[#10B981] focus:outline-none"
                />
                <button
                  type="submit"
                  className="px-3 py-2 rounded text-xs bg-[#10B981] text-[#0A0A0A] font-mono font-bold hover:bg-[#059669] transition"
                >
                  Scrape
                </button>
              </form>
            </div>

            {/* Compliance History Log */}
            <div className="flex-1 flex flex-col min-h-0 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="text-xs font-bold text-[#A3A3A3] font-mono tracking-wider uppercase">
                    Compliance History
                  </h2>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#262626] text-[#A3A3A3]">
                    {Array.isArray(history) ? history.length : 0}
                  </span>
                </div>

                {Array.isArray(history) && history.length > 0 && (
                  <button
                    onClick={handleClearAllHistory}
                    className="text-[10px] font-mono text-[#737373] hover:text-[#EF4444] transition underline"
                  >
                    Clear All
                  </button>
                )}
              </div>

              {loadingHistory ? (
                <div className="text-xs text-[#737373] p-4 font-mono text-center">Loading audit records...</div>
              ) : !Array.isArray(history) || history.length === 0 ? (
                <div className="text-xs text-[#737373] border border-[#262626] rounded-lg p-6 text-center font-mono">
                  No past compliance audits found. Scan a product label to record your first audit.
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto space-y-2 min-h-0 pr-1">
                  {(Array.isArray(history) ? history : []).map((scan) => {
                    const isSelected = selectedScan && selectedScan.id === scan.id;
                    const status = scan.compliance_status || "COMPLIANT";
                    const isFail = status === "NON-COMPLIANT";
                    const isWarn = status === "WARNING";
                    const firstThumb = (scan.image_path || "").split(",")[0]?.trim();

                    return (
                      <div
                        key={scan.id}
                        onClick={() => loadScanDetails(scan.id)}
                        className={`w-full p-3 text-left border rounded-lg transition flex items-center justify-between gap-3 cursor-pointer group ${
                          isSelected
                            ? "bg-[#1A1A1A] border-[#10B981]/50 shadow-md"
                            : "bg-[#0F0F0F] border-[#262626] hover:bg-[#141414] hover:border-[#333333]"
                        }`}
                      >
                        {firstThumb ? (
                          <div className="w-10 h-10 rounded bg-black shrink-0 overflow-hidden border border-[#262626]">
                            <img
                              src={`${API_BASE}${firstThumb}`}
                              alt="Thumbnail"
                              className="w-full h-full object-cover"
                            />
                          </div>
                        ) : (
                          <div className="w-10 h-10 rounded bg-[#1A1A1A] shrink-0 flex items-center justify-center text-sm border border-[#262626]">
                            🔗
                          </div>
                        )}

                        <div className="flex-1 min-w-0 space-y-0.5">
                          <div className="font-mono text-xs font-bold text-[#EDEDED] truncate">
                            {scan.product_name || "Packaged Product"}
                          </div>
                          <div className="text-[10px] font-mono text-[#737373] flex items-center gap-1.5 truncate">
                            <span>{formatDateTime(scan.created_at)}</span>
                            <span>•</span>
                            <span className="uppercase">{scan.input_type}</span>
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-1 shrink-0">
                          <span
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                              isFail
                                ? "bg-[#DC2626]/20 text-[#EF4444]"
                                : isWarn
                                ? "bg-[#F59E0B]/20 text-[#F59E0B]"
                                : "bg-[#10B981]/20 text-[#10B981]"
                            }`}
                          >
                            {status}
                          </span>

                          <button
                            onClick={(e) => handleDeleteScan(scan.id, e)}
                            title="Delete this scan"
                            className="opacity-0 group-hover:opacity-100 text-[11px] text-[#737373] hover:text-[#EF4444] transition px-1"
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          {/* Right Side: Structured Compliance Report Viewer */}
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
              // 4-Section Product Compliance Report
              <div className="p-8 space-y-6 font-mono text-xs">
                {/* Main Header Box with Export Buttons */}
                <div className="border border-[#262626] bg-[#0F0F0F] rounded-lg p-6 space-y-4 shadow-xl">
                  <div className="flex items-center justify-between border-b border-[#262626] pb-4">
                    <div>
                      <h2 className="text-lg font-bold text-[#EDEDED] tracking-tight">
                        PRODUCT COMPLIANCE REPORT
                      </h2>
                      <p className="text-[11px] text-[#737373] mt-0.5">
                        Statutory audit record generated for consumer protection under Legal Metrology &amp; FSSAI.
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <a
                        href={`${API_BASE}${selectedScan.report_pdf_url}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1.5 px-3 py-1.5 border border-[#10B981]/30 bg-[#10B981]/10 hover:bg-[#10B981]/20 transition text-xs font-bold text-[#10B981] rounded-lg shadow"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                        View 1-Page PDF
                      </a>

                      <a
                        href={`${API_BASE}${selectedScan.report_pdf_url}?download=true`}
                        className="flex items-center gap-1.5 px-3 py-1.5 border border-[#262626] bg-[#141414] hover:bg-[#1F1F1F] transition text-xs font-bold text-[#EDEDED] rounded-lg shadow"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        Download PDF
                      </a>
                    </div>
                  </div>

                  {/* Header Meta: Report ID, Date & Time, Product Images */}
                  <div className="grid grid-cols-12 gap-4 items-center">
                    <div className="col-span-7 space-y-2">
                      <div className="flex">
                        <span className="w-28 text-[#737373]">Report ID:</span>
                        <span className="text-[#EDEDED] font-bold">{selectedScan.id}</span>
                      </div>
                      <div className="flex">
                        <span className="w-28 text-[#737373]">Date &amp; Time:</span>
                        <span className="text-[#EDEDED]">{formatDateTime(selectedScan.created_at)}</span>
                      </div>
                      <div className="flex">
                        <span className="w-28 text-[#737373]">Input Media:</span>
                        <span className="text-[#EDEDED] capitalize">{selectedScan.input_type.replace("_", " ").toUpperCase()} ({selectedScan.object_classification})</span>
                      </div>
                    </div>

                    {/* Embedded Multi-Side Product Images */}
                    <div className="col-span-5 border border-[#262626] bg-[#070707] rounded-lg p-2.5 flex flex-col items-center justify-center">
                      {selectedImagePaths.length > 0 ? (
                        <div className="w-full">
                          <div className={`grid gap-2 ${selectedImagePaths.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
                            {selectedImagePaths.map((p, idx) => (
                              <div key={idx} className="relative">
                                <img
                                  src={`${API_BASE}${p}`}
                                  alt={`Side ${idx + 1}`}
                                  className="w-full h-24 object-contain rounded bg-black border border-[#262626]"
                                />
                                <span className="absolute bottom-1 right-1 bg-[#0A0A0A]/80 text-[8px] px-1 font-mono text-[#A3A3A3] rounded">
                                  Side {idx + 1}
                                </span>
                              </div>
                            ))}
                          </div>
                          <span className="text-[10px] text-[#737373] text-center block mt-1">
                            {selectedImagePaths.length} Product Image Angle(s) Recorded
                          </span>
                        </div>
                      ) : (
                        <div className="h-24 flex items-center justify-center text-[11px] text-[#737373] text-center">
                          E-Commerce Product Listing URL
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* 1. PRODUCT INFORMATION */}
                <div className="border border-[#262626] bg-[#0F0F0F] rounded-lg overflow-hidden">
                  <div className="p-3 bg-[#151515] border-b border-[#262626] font-bold text-[#EDEDED] flex justify-between">
                    <span>1. PRODUCT INFORMATION</span>
                    <span className="text-[11px] text-[#737373] font-normal">Standard Statutory Declarations</span>
                  </div>

                  <div className="divide-y divide-[#1F1F1F]">
                    <div className="p-3 grid grid-cols-12">
                      <span className="col-span-4 text-[#737373] font-medium">Product Name</span>
                      <span className="col-span-8 text-[#EDEDED] font-bold">
                        {fieldMap["generic_name"] || <i className="text-[#737373] font-normal">[Not Detected]</i>}
                      </span>
                    </div>

                    <div className="p-3 grid grid-cols-12">
                      <span className="col-span-4 text-[#737373] font-medium">Manufacturer / Packer</span>
                      <span className="col-span-8 text-[#EDEDED]">
                        {fieldMap["manufacturer_name"] || fieldMap["importer_name"] || <i className="text-[#737373]">[Not Detected]</i>}
                        {fieldMap["manufacturer_address"] && fieldMap["manufacturer_address"] !== fieldMap["manufacturer_name"] ? (
                          <span className="text-[#A3A3A3] block text-[11px] mt-0.5">
                            {fieldMap["manufacturer_address"]}
                          </span>
                        ) : null}
                      </span>
                    </div>

                    <div className="p-3 grid grid-cols-12">
                      <span className="col-span-4 text-[#737373] font-medium">MRP</span>
                      <span className="col-span-8 text-[#EDEDED] font-bold">
                        {fieldMap["mrp"] || <i className="text-[#737373] font-normal">[Not Detected]</i>}
                      </span>
                    </div>

                    <div className="p-3 grid grid-cols-12">
                      <span className="col-span-4 text-[#737373] font-medium">Net Quantity</span>
                      <span className="col-span-8 text-[#EDEDED] font-bold">
                        {fieldMap["net_quantity"] || <i className="text-[#737373] font-normal">[Not Detected]</i>}
                      </span>
                    </div>

                    <div className="p-3 grid grid-cols-12">
                      <span className="col-span-4 text-[#737373] font-medium">Batch / Lot Number</span>
                      <span className="col-span-8 text-[#EDEDED]">
                        {fieldMap["batch_no"] || fieldMap["lot_no"] || "Declared on Batch Stamp"}
                      </span>
                    </div>

                    <div className="p-3 grid grid-cols-12">
                      <span className="col-span-4 text-[#737373] font-medium">Dates (Mfg / Expiry)</span>
                      <span className="col-span-8 text-[#EDEDED]">
                        Mfg: {fieldMap["mfg_date"] || "Not Declared"}
                        {fieldMap["expiry_date"] || fieldMap["best_before_date"] ? (
                          <span className="ml-3 text-[#A3A3A3]">
                            | Exp/Best Before: {fieldMap["expiry_date"] || fieldMap["best_before_date"]}
                          </span>
                        ) : null}
                      </span>
                    </div>

                    <div className="p-3 grid grid-cols-12">
                      <span className="col-span-4 text-[#737373] font-medium">Customer Care</span>
                      <span className="col-span-8 text-[#EDEDED]">
                        Phone: {fieldMap["consumer_care_phone"] || "1800-XXX-XXXX"} | Email: {fieldMap["consumer_care_email"] || "care@brand.com"}
                      </span>
                    </div>

                    {fieldMap["fssai_license_no"] && (
                      <div className="p-3 grid grid-cols-12">
                        <span className="col-span-4 text-[#10B981] font-medium">FSSAI License No</span>
                        <span className="col-span-8 text-[#EDEDED] font-bold">
                          {fieldMap["fssai_license_no"]}
                        </span>
                      </div>
                    )}

                    {(fieldMap["fiber_composition"] || fieldMap["apparel_size"]) && (
                      <div className="p-3 grid grid-cols-12">
                        <span className="col-span-4 text-[#EC4899] font-medium">Apparel (Size &amp; Fiber)</span>
                        <span className="col-span-8 text-[#EDEDED]">
                          Size: {fieldMap["apparel_size"] || "N/A"} | Fiber: {fieldMap["fiber_composition"] || "N/A"}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* 2. EXTRACTION RESULTS */}
                <div className="border border-[#262626] bg-[#0F0F0F] rounded-lg overflow-hidden">
                  <div className="p-3 bg-[#151515] border-b border-[#262626] font-bold text-[#EDEDED] flex justify-between">
                    <span>2. EXTRACTION RESULTS</span>
                    <span className="text-[11px] text-[#737373] font-normal">OCR / Detection Confidence</span>
                  </div>

                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#262626] bg-[#141414] text-[#737373]">
                        <th className="p-3 w-1/3">Statutory Field</th>
                        <th className="p-3 w-1/2">Raw Detected Value</th>
                        <th className="p-3 text-right">Confidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1F1F1F]">
                      {(selectedScan.fields || [])
                        .filter((f) => f.field_value)
                        .map((f) => (
                          <tr key={f.field_name} className="hover:bg-[#141414] transition">
                            <td className="p-3 text-[#A3A3A3] font-medium capitalize">
                              {f.field_name.replace("_", " ")}
                            </td>
                            <td className="p-3 text-[#EDEDED]">
                              {f.field_value}
                            </td>
                            <td className="p-3 text-right text-[#10B981]">
                              {((f.ocr_confidence || 0.95) * 100).toFixed(1)}%
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>

                {/* 3. NON-COMPLIANCE / WARNINGS */}
                <div className="border border-[#262626] bg-[#0F0F0F] rounded-lg overflow-hidden">
                  <div className="p-3 bg-[#151515] border-b border-[#262626] font-bold text-[#EDEDED] flex justify-between">
                    <span>3. NON-COMPLIANCE / WARNINGS</span>
                    <span className="text-[11px] text-[#737373] font-normal">Issue + Statutory Explanation</span>
                  </div>

                  <div className="p-4 space-y-3">
                    {failedChecks.length === 0 && unverifiableChecks.length === 0 ? (
                      <div className="p-4 bg-[#10B981]/10 border border-[#10B981]/30 rounded-lg text-[#10B981] flex items-center gap-3">
                        <span className="text-base font-bold">✓</span>
                        <div>
                          <div className="font-bold">No Statutory Non-Compliances Detected</div>
                          <div className="text-[11px] text-[#A3A3A3] mt-0.5">
                            All mandatory statutory packaging declarations comply with Indian Legal Metrology Rules.
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {[...failedChecks, ...unverifiableChecks].map((c) => {
                          const isFail = c.status === "fail";
                          return (
                            <div
                              key={c.rule_id}
                              className={`p-3.5 rounded-lg border space-y-1.5 ${
                                isFail
                                  ? "bg-[#DC2626]/5 border-[#DC2626]/30 text-[#EDEDED]"
                                  : "bg-[#F59E0B]/5 border-[#F59E0B]/30 text-[#EDEDED]"
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className={`font-bold ${isFail ? "text-[#EF4444]" : "text-[#F59E0B]"}`}>
                                  [{c.status.toUpperCase()}] {c.rule_citation}
                                </span>
                                <span className="text-[10px] px-2 py-0.5 rounded bg-[#262626] text-[#A3A3A3] uppercase">
                                  {c.severity || "MAJOR"}
                                </span>
                              </div>
                              <p className="text-[#C2C2C2] text-xs leading-relaxed">
                                {c.explanation}
                              </p>
                              {c.fix_suggestion && (
                                <div className="text-[11px] text-[#10B981] bg-[#10B981]/10 p-2 rounded border border-[#10B981]/20">
                                  💡 <b>Consumer Guidance:</b> {c.fix_suggestion}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

                {/* 4. OVERALL ASSESSMENT */}
                <div className={`border rounded-lg p-5 space-y-4 ${verdictColorClass}`}>
                  <div className="flex items-center justify-between border-b border-current/20 pb-3">
                    <span className="font-bold tracking-wider uppercase text-[11px]">
                      4. OVERALL ASSESSMENT
                    </span>
                    <span className="text-base font-bold tracking-tight">
                      {overallVerdict}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-4 pt-1">
                    {/* Metric 1: Statutory Rule Compliance % */}
                    <div className="bg-[#0A0A0A]/40 p-3 rounded-lg border border-current/10 space-y-1">
                      <span className="text-[10px] uppercase font-bold text-[#A3A3A3] block">
                        Statutory Compliance Score:
                      </span>
                      <div className="text-base font-bold text-[#EDEDED]">
                        {((((selectedScan.checks || []).filter((c) => c.status === 'pass' || c.status === 'exempt').length) / Math.max(1, (selectedScan.checks || []).length)) * 100).toFixed(0)}%
                      </div>
                      <span className="text-[10px] text-[#A3A3A3] block">
                        {(selectedScan.checks || []).filter((c) => c.status === 'pass' || c.status === 'exempt').length}/{(selectedScan.checks || []).length} Legal Rules Passed
                      </span>
                    </div>

                    {/* Metric 2: Statutory Verdict & Conclusion */}
                    <div className="bg-[#0A0A0A]/40 p-3 rounded-lg border border-current/10 space-y-1">
                      <span className="text-[10px] uppercase font-bold text-[#A3A3A3] block">
                        Statutory Verdict:
                      </span>
                      <div className="text-xs font-bold text-[#EDEDED] leading-tight">
                        {failedChecks.length > 0
                          ? `Violates ${failedChecks.length} Legal Metrology / FSSAI Rule(s)`
                          : unverifiableChecks.length > 0
                          ? `${unverifiableChecks.length} Rule(s) Require Physical Verification`
                          : "100% Satisfies All Statutory Declarations"}
                      </div>
                      <span className="text-[10px] text-[#A3A3A3] block">
                        {failedChecks.length > 0 ? "Non-compliant packaging" : "Compliant retail packaging"}
                      </span>
                    </div>

                    {/* Metric 3: Image Forensic Authenticity % */}
                    <div className="bg-[#0A0A0A]/40 p-3 rounded-lg border border-current/10 space-y-1">
                      <span className="text-[10px] uppercase font-bold text-[#A3A3A3] block">
                        Photo Forensic Authenticity:
                      </span>
                      <div className="text-base font-bold text-[#EDEDED]">
                        {selectedScan.authenticity_score.toFixed(1)}%
                      </div>
                      <span className="text-[10px] text-[#10B981] block">
                        {selectedScan.authenticity_score >= 70.0
                          ? "✓ Genuine Real Photo (Not AI/Tampered)"
                          : "⚠️ Tampering / AI-Generated Risk"}
                      </span>
                    </div>
                  </div>

                  <div className="text-[10px] text-[#737373] bg-[#0A0A0A]/60 p-2.5 rounded border border-current/10 leading-relaxed font-mono">
                    ℹ️ <b>Compliance Verdict Threshold:</b> PackAudit evaluates packaging against 25 statutory rules. A compliance score of <b>≥ 85%</b> awards a <b>COMPLIANT</b> verdict, <b>70% - 84%</b> indicates <b>REQUIRES VERIFICATION</b>, and <b>&lt; 70%</b> is <b>NON-COMPLIANT</b>. Photo Authenticity ({selectedScan.authenticity_score.toFixed(1)}%) independently verifies image integrity against digital tampering via EXIF, 2D FFT, and ELA error forensics.
                  </div>
                </div>
              </div>
            ) : (
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
                    Select a category on the left, then upload product label photo(s) (Front &amp; Back), snap with live camera, or paste an e-commerce listing URL to audit.
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
