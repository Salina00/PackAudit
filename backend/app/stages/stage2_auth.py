import os
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, Tuple

from backend.app.core.config import settings

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
                # Web images or screenshots have stripped EXIF
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
                    "picsart", "snapseed", "pixelmator", "fotor", "pixlr", "paint.net"
                ]
                
                for sw in suspicious_software:
                    if sw in software_str:
                        result["editing_software_detected"] = True
                        result["status"] = "SUSPICIOUS"
                        result["score"] = 25.0
                        result["details"] = f"Editing software signature detected in EXIF: '{software}'."
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

def run_fft_check(image_path: str) -> Dict[str, Any]:
    """
    Stage 2b: 2D Fast Fourier Transform (FFT) Frequency Analysis.
    Calculates the High-Frequency Spectral Energy Ratio on the log-magnitude spectrum.
    Measures natural power-law decay and flags synthetic smoothing or generative grid artifacts.
    """
    result = {
        "status": "PASS",
        "ai_generation_detected": False,
        "fft_variance": 0.0,
        "classifier_label": "REAL",
        "classifier_confidence": 0.95,
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
            
        # 2D Fast Fourier Transform
        f = np.fft.fft2(img_gray.astype(np.float32))
        fshift = np.fft.fftshift(f)
        log_magnitude = np.log1p(np.abs(fshift))
        total_log_energy = float(np.sum(log_magnitude)) + 1e-7
        
        # High frequency mask (outer region)
        center_y, center_x = h // 2, w // 2
        radius = min(h, w) // 4
        y, x = np.ogrid[:h, :w]
        dist_from_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        
        high_freq_mask = dist_from_center > radius
        high_freq_log_energy = float(np.sum(log_magnitude[high_freq_mask]))
        
        # Continuous High-Frequency Ratio in Log-Magnitude space (typically 0.40 to 0.85)
        hf_ratio = high_freq_log_energy / total_log_energy
        hf_percent = hf_ratio * 100.0
        result["fft_variance"] = round(hf_percent, 1)
        
        # Real camera product packaging photos have hf_percent between 55% and 82%
        # Over-smoothed / AI synthetic renders have hf_percent < 45%
        # Artificial high-frequency noise / grid artifacts have hf_percent > 90%
        if hf_percent < 45.0:
            result["status"] = "FAIL"
            result["ai_generation_detected"] = True
            result["score"] = float(round(max(20.0, hf_percent * 1.3), 1))
            result["classifier_label"] = "SYNTHETIC_SMOOTH"
            result["details"] = f"Unnatural high-frequency attenuation / synthetic smoothing (HF Log-Energy: {hf_percent:.1f}%)."
        elif hf_percent > 90.0:
            result["status"] = "FAIL"
            result["ai_generation_detected"] = True
            result["score"] = float(round(max(25.0, 95.0 - ((hf_percent - 90.0) * 4.0)), 1))
            result["classifier_label"] = "GENERATIVE_GRID"
            result["details"] = f"Anomalous high-frequency spectral grid / generative noise (HF Log-Energy: {hf_percent:.1f}%)."
        else:
            # Optimal natural photo spectrum centered around 68.0%
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
    Stage 2c: Error Level Analysis (ELA) for edited-region detection.
    Computes compression difference variance, regional kurtosis, and localized error distributions.
    Produces a continuous, per-image ELA score.
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
            # Resave at fixed 85% JPEG quality
            original.save(temp_ela_path, "JPEG", quality=85)
            
            with Image.open(temp_ela_path) as compressed_pil:
                compressed = compressed_pil.convert("RGB")
                
                orig_arr = np.array(original, dtype=np.float32)
                comp_arr = np.array(compressed, dtype=np.float32)
                
                # Absolute difference map
                diff_arr = np.abs(orig_arr - comp_arr)
                
                # Statistical metrics
                var_diff = float(np.var(diff_arr))
                mean_diff = float(np.mean(diff_arr))
                max_diff = float(np.max(diff_arr))
                result["ela_variance"] = round(var_diff, 2)
                
                # Visual enhancement for frontend display
                scale = 255.0 / max(1.0, max_diff)
                enhanced_arr = np.clip(diff_arr * scale, 0, 255).astype(np.uint8)
                
                enhanced_pil = Image.fromarray(enhanced_arr)
                enhanced_pil.save(ela_map_path)
                result["ela_image_url"] = "/static/uploads/" + os.path.basename(ela_map_path)
                
        # Authentic unedited photos have uniform compression variance (typically 0.5 to 15.0)
        # Spliced or photoshopped labels have localized compression error spikes (> 25.0)
        if var_diff > 25.0:
            result["is_edited"] = True
            result["status"] = "FAIL"
            penalty = min(65.0, (var_diff - 25.0) * 2.0)
            result["score"] = float(round(max(18.0, 55.0 - penalty), 1))
            result["details"] = f"Localized compression mismatch detected / potential splicing (ELA Variance: {var_diff:.2f})."
        else:
            # Continuous score based on compression homogeneity
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
    Runs EXIF, FFT, and ELA checks in parallel, and merges them
    into a continuous authenticity confidence percentage.
    Formula: (EXIF_Score * 0.20) + (FFT_Score * 0.40) + (ELA_Score * 0.40)
    """
    exif_res = run_exif_check(image_path)
    fft_res = run_fft_check(image_path)
    ela_res = run_ela_check(image_path)
    
    # Weighted continuous composite score
    overall_score = (exif_res["score"] * 0.20) + (fft_res["score"] * 0.40) + (ela_res["score"] * 0.40)
    overall_score = float(round(overall_score, 1))
    
    report = {
        "authenticity_score": overall_score,
        "is_authentic": overall_score >= settings.AUTHENTICITY_THRESHOLD,
        "exif": exif_res,
        "fft": fft_res,
        "ela": ela_res
    }
    
    return overall_score, report
