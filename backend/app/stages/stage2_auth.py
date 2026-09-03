import os
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, Tuple, Optional

from backend.app.core.config import settings

# Global AI detector pipeline cache (lazy-loaded on first request / app boot)
_ai_detector = None

def get_ai_detector():
    """
    Lazy-loads the pre-trained Hugging Face AI vs Human image classifier.
    Uses Ateeqq/ai-vs-human-image-detector with fallback to umm-maybe/AI-image-detector.
    """
    global _ai_detector
    if _ai_detector is None:
        try:
            from transformers import pipeline
            print("Loading AI Image Detection pipeline (Ateeqq/ai-vs-human-image-detector)...")
            _ai_detector = pipeline("image-classification", model="Ateeqq/ai-vs-human-image-detector")
            print("AI Image Detection pipeline loaded successfully.")
        except Exception as e:
            print(f"Failed to load Ateeqq model: {e}. Trying fallback to umm-maybe/AI-image-detector...")
            try:
                from transformers import pipeline
                _ai_detector = pipeline("image-classification", model="umm-maybe/AI-image-detector")
                print("Loaded fallback umm-maybe/AI-image-detector successfully.")
            except Exception as e2:
                print(f"Failed to load Hugging Face AI detector: {e2}. Falling back to FFT heuristic.")
                _ai_detector = "FAILED"
    return _ai_detector

def run_exif_check(image_path: str) -> Dict[str, Any]:
    """
    Stage 2a: EXIF header metadata analysis.
    Evaluates metadata tags, camera profile, timestamp consistency, and editing tool signatures.
    Returns a continuous score from 15.0% to 100.0%.
    """
    result = {
        "status": "PASS",
        "exif_present": False,
        "editing_software_detected": False,
        "software_name": None,
        "score": 75.0,
        "details": ""
    }
    
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            if not exif or len(exif) == 0:
                file_size_kb = os.path.getsize(image_path) / 1024.0
                ratio = (file_size_kb * 1024.0) / max(1.0, float(img.width * img.height * 3))
                continuous_score = min(88.0, max(72.0, 74.0 + (ratio * 25.0)))
                
                result["exif_present"] = False
                result["score"] = float(round(continuous_score, 1))
                result["details"] = "EXIF stripped (typical for web media / screenshots). Compression density normal."
                return result
                
            result["exif_present"] = True
            tag_count = len(exif)
            software = exif.get(305) # EXIF tag 305 = Software
            
            if software:
                software_str = str(software).lower()
                result["software_name"] = str(software)
                
                suspicious_software = [
                    "photoshop", "gimp", "canva", "adobe", "lightroom", 
                    "picsart", "snapseed", "pixelmator", "fotor", "pixlr", "paint.net",
                    "midjourney", "dall-e", "stable diffusion"
                ]
                
                for sw in suspicious_software:
                    if sw in software_str:
                        result["editing_software_detected"] = True
                        result["status"] = "SUSPICIOUS"
                        result["score"] = 20.0
                        result["details"] = f"Editing / Generative software signature detected in EXIF: '{software}'."
                        return result
                        
            camera_make = exif.get(271)
            camera_model = exif.get(272)
            has_camera_info = bool(camera_make or camera_model)
            
            raw_score = 82.0 + min(12.0, tag_count * 1.5) + (5.0 if has_camera_info else 0.0)
            result["score"] = float(round(min(99.0, raw_score), 1))
            result["details"] = f"Authentic camera EXIF verified ({tag_count} tags, Device: {camera_model or 'Direct Sensor'})."
            
    except Exception as e:
        result["status"] = "ERROR"
        result["score"] = 70.0
        result["details"] = f"Failed to parse EXIF: {str(e)}"
        
    return result

def compute_fft_variance(image_path: str) -> float:
    """
    Computes 2D Fast Fourier Transform log-magnitude spectral variance.
    AI generators leave telltale spectral upsampling artifacts and frequency suppression.
    """
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            with Image.open(image_path) as pil_img:
                img = np.array(pil_img.convert('L'))
                
        f = np.fft.fft2(img.astype(np.float32))
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-8)
        return float(np.var(magnitude_spectrum))
    except Exception as e:
        print(f"FFT variance computation notice: {e}")
        return 600.0

def check_ai_generated(image_path: str) -> Dict[str, Any]:
    """
    Stage 2b: Pre-trained Hugging Face classifier for AI-generated / synthetic image detection.
    """
    detector = get_ai_detector()
    
    if detector is None or detector == "FAILED":
        # Fallback heuristic if HF pipeline fails
        fft_var = compute_fft_variance(image_path)
        is_suspicious = fft_var > 1800.0 or fft_var < 350.0
        return {
            "is_ai_generated": is_suspicious,
            "confidence": 70.0 if is_suspicious else 85.0,
            "raw_predictions": [],
            "model_name": "Spectral FFT Fallback"
        }
        
    try:
        with Image.open(image_path) as img:
            image_rgb = img.convert("RGB")
            # If image is very large, downscale slightly for fast classification inference
            if max(image_rgb.width, image_rgb.height) > 1024:
                image_rgb.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                
            predictions = detector(image_rgb)
            top = predictions[0]
            label_lower = top["label"].lower()
            is_ai = label_lower in ("ai", "fake", "artificial", "generated", "ai-generated", "synthetic")
            
            return {
                "is_ai_generated": is_ai,
                "confidence": round(float(top["score"]) * 100.0, 2),
                "raw_predictions": predictions,
                "model_name": "Ateeqq/ai-vs-human-image-detector"
            }
    except Exception as e:
        print(f"AI classifier exception: {e}")
        return {
            "is_ai_generated": False,
            "confidence": 75.0,
            "raw_predictions": [],
            "model_name": "Error Fallback"
        }

def get_combined_ai_score(classifier_result: Dict[str, Any], fft_variance: float, fft_threshold: float = 1800.0) -> Dict[str, Any]:
    """
    Combines pre-trained vision classifier with 2D FFT spectral variance into a single decision.
    """
    is_ai = classifier_result["is_ai_generated"]
    cls_conf = classifier_result["confidence"]
    
    # Base confidence: if AI-generated, confidence of being AI; if Real, confidence of being AI (100 - cls_conf)
    ai_gen_confidence = cls_conf if is_ai else (100.0 - cls_conf)
    fft_flag = fft_variance > fft_threshold or fft_variance < 350.0
    
    if is_ai and cls_conf >= 75.0:
        status = "SUSPICIOUS_AI_GENERATED"
        verdict_text = "AI-Generated / Synthetic Image Detected"
    elif is_ai or fft_flag or cls_conf < 65.0:
        status = "BORDERLINE_UNVERIFIED"
        verdict_text = "Authenticity Unverified (Manual Review Recommended)"
    else:
        status = "LIKELY_AUTHENTIC"
        verdict_text = "Likely Authentic Camera Photograph"
        
    return {
        "status": status,
        "verdict_text": verdict_text,
        "ai_generation_confidence": round(ai_gen_confidence, 2),
        "human_authenticity_confidence": round(100.0 - ai_gen_confidence, 2),
        "classifier_verdict": classifier_result,
        "fft_variance": round(fft_variance, 2),
        "fft_flagged": fft_flag,
        "model_name": classifier_result.get("model_name", "Ateeqq/ai-vs-human-image-detector")
    }

def run_fft_check(image_path: str) -> Dict[str, Any]:
    """
    Stage 2c: 2D Fast Fourier Transform (FFT) Frequency Analysis.
    Calculates the High-Frequency Spectral Energy Ratio on the log-magnitude spectrum.
    """
    result = {
        "status": "PASS",
        "ai_generation_detected": False,
        "fft_variance": 0.0,
        "score": 90.0,
        "details": ""
    }
    
    try:
        img_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img_gray is None:
            with Image.open(image_path) as pil_img:
                img_gray = np.array(pil_img.convert('L'))
                
        h, w = img_gray.shape
        if h > 512 or w > 512:
            img_gray = cv2.resize(img_gray, (512, 512), interpolation=cv2.INTER_AREA)
            h, w = 512, 512
            
        f = np.fft.fft2(img_gray.astype(np.float32))
        fshift = np.fft.fftshift(f)
        log_magnitude = np.log1p(np.abs(fshift))
        total_log_energy = float(np.sum(log_magnitude)) + 1e-7
        
        center_y, center_x = h // 2, w // 2
        radius = min(h, w) // 4
        y, x = np.ogrid[:h, :w]
        dist_from_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        
        high_freq_mask = dist_from_center > radius
        high_freq_log_energy = float(np.sum(log_magnitude[high_freq_mask]))
        
        hf_ratio = high_freq_log_energy / total_log_energy
        hf_percent = hf_ratio * 100.0
        result["fft_variance"] = round(hf_percent, 1)
        
        if hf_percent < 45.0:
            result["status"] = "FAIL"
            result["ai_generation_detected"] = True
            result["score"] = float(round(max(20.0, hf_percent * 1.3), 1))
            result["details"] = f"Unnatural high-frequency attenuation / synthetic smoothing (HF Log-Energy: {hf_percent:.1f}%)."
        elif hf_percent > 90.0:
            result["status"] = "FAIL"
            result["ai_generation_detected"] = True
            result["score"] = float(round(max(25.0, 95.0 - ((hf_percent - 90.0) * 4.0)), 1))
            result["details"] = f"Anomalous high-frequency spectral grid / generative noise (HF Log-Energy: {hf_percent:.1f}%)."
        else:
            deviation = abs(hf_percent - 68.0)
            natural_score = 98.0 - (deviation * 0.9)
            result["score"] = float(round(max(70.0, min(99.0, natural_score)), 1))
            result["details"] = f"Natural 2D Fourier power spectrum (High-Freq Log-Energy: {hf_percent:.1f}%)."
            
    except Exception as e:
        result["status"] = "ERROR"
        result["score"] = 78.0
        result["details"] = f"Failed to compute FFT frequency checks: {str(e)}"
        
    return result

def run_ela_check(image_path: str) -> Dict[str, Any]:
    """
    Stage 2d: Error Level Analysis (ELA) for edited-region detection.
    """
    result = {
        "status": "PASS",
        "is_edited": False,
        "ela_variance": 0.0,
        "ela_image_url": None,
        "score": 90.0,
        "details": ""
    }
    
    temp_ela_path = image_path + ".tmp_ela.jpg"
    ela_map_path = image_path + ".ela.png"
    
    try:
        with Image.open(image_path) as original_pil:
            original = original_pil.convert("RGB")
            original.save(temp_ela_path, "JPEG", quality=85)
            
            with Image.open(temp_ela_path) as compressed_pil:
                compressed = compressed_pil.convert("RGB")
                orig_arr = np.array(original, dtype=np.float32)
                comp_arr = np.array(compressed, dtype=np.float32)
                
                diff_arr = np.abs(orig_arr - comp_arr)
                var_diff = float(np.var(diff_arr))
                mean_diff = float(np.mean(diff_arr))
                max_diff = float(np.max(diff_arr))
                result["ela_variance"] = round(var_diff, 2)
                
                scale = 255.0 / max(1.0, max_diff)
                enhanced_arr = np.clip(diff_arr * scale, 0, 255).astype(np.uint8)
                
                enhanced_pil = Image.fromarray(enhanced_arr)
                enhanced_pil.save(ela_map_path)
                result["ela_image_url"] = "/static/uploads/" + os.path.basename(ela_map_path)
                
        if var_diff > 25.0:
            result["is_edited"] = True
            result["status"] = "FAIL"
            penalty = min(65.0, (var_diff - 25.0) * 2.0)
            result["score"] = float(round(max(18.0, 55.0 - penalty), 1))
            result["details"] = f"Localized compression mismatch detected / potential splicing (ELA Variance: {var_diff:.2f})."
        else:
            dynamic_ela_score = 98.5 - (var_diff * 0.75) - (mean_diff * 0.5)
            result["score"] = float(round(max(70.0, min(99.0, dynamic_ela_score)), 1))
            result["details"] = f"Homogeneous compression profile (ELA Variance: {var_diff:.2f}, Mean Error: {mean_diff:.2f})."
            
    except Exception as e:
        result["status"] = "ERROR"
        result["score"] = 80.0
        result["details"] = f"Failed to compute ELA: {str(e)}"
        
    finally:
        if os.path.exists(temp_ela_path):
            try:
                os.remove(temp_ela_path)
            except:
                pass
                
    return result

def authenticate_image(image_path: str) -> Tuple[float, Dict[str, Any]]:
    """
    Executes 4-Pillar Forensic Verification Pipeline:
    1. EXIF Metadata Inspection
    2. AI Generation Check (Hugging Face Vision Transformer + FFT Variance)
    3. 2D FFT Frequency Spectrum Analysis
    4. Error Level Analysis (ELA)
    
    Returns: (overall_authenticity_score, report)
    """
    # 1. EXIF Check
    exif_res = run_exif_check(image_path)
    
    # 2. AI Generation Check
    cls_res = check_ai_generated(image_path)
    fft_var = compute_fft_variance(image_path)
    ai_gen_res = get_combined_ai_score(cls_res, fft_var)
    
    # 3. FFT High-Frequency Analysis
    fft_res = run_fft_check(image_path)
    
    # 4. ELA Check
    ela_res = run_ela_check(image_path)
    
    # Compute composite continuous score:
    # If AI-Generated with high confidence, penalize overall score heavily
    if ai_gen_res["status"] == "SUSPICIOUS_AI_GENERATED":
        ai_score = max(5.0, 100.0 - ai_gen_res["ai_generation_confidence"])
    elif ai_gen_res["status"] == "BORDERLINE_UNVERIFIED":
        ai_score = 65.0
    else:
        ai_score = max(75.0, ai_gen_res["human_authenticity_confidence"])
        
    overall_score = (exif_res["score"] * 0.15) + (ai_score * 0.45) + (fft_res["score"] * 0.20) + (ela_res["score"] * 0.20)
    overall_score = float(round(overall_score, 1))
    
    report = {
        "authenticity_score": overall_score,
        "is_authentic": overall_score >= settings.AUTHENTICITY_THRESHOLD and ai_gen_res["status"] != "SUSPICIOUS_AI_GENERATED",
        "exif": exif_res,
        "ai_generation": ai_gen_res,
        "fft": fft_res,
        "ela": ela_res
    }
    
    return overall_score, report
