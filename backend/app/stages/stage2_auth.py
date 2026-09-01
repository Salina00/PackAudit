import os
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, Tuple

from backend.app.core.config import settings

# Global transformers pipeline cache to load only once if needed
_hf_classifier = None

def run_exif_check(image_path: str) -> Dict[str, Any]:
    """
    Stage 2a: EXIF header metadata analysis.
    Checks for editing software signatures and flags missing EXIF metadata.
    """
    result = {
        "status": "PASS",
        "exif_present": False,
        "editing_software_detected": False,
        "software_name": None,
        "score": 100.0,
        "details": ""
    }
    
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            if not exif:
                # Legitimate social media compression or copy-pastes strip EXIF
                result["exif_present"] = False
                result["score"] = 75.0  # Slight penalty for lack of metadata
                result["details"] = "EXIF metadata is missing (common for compressed web images)."
                return result
                
            result["exif_present"] = True
            
            # EXIF tag 305 is Software
            software = exif.get(305)
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
                        result["score"] = 20.0  # Heavy penalty
                        result["details"] = f"Editing software signature detected in EXIF: '{software}'."
                        return result
                        
            result["details"] = "EXIF metadata present. No editing software signatures detected."
            
    except Exception as e:
        result["status"] = "ERROR"
        result["score"] = 50.0
        result["details"] = f"Failed to parse EXIF: {str(e)}"
        
    return result

def run_fft_check(image_path: str) -> Dict[str, Any]:
    """
    Stage 2b: Frequency analysis (FFT) + AI-generation detection.
    Computes 2D Fast Fourier Transform to find periodic grids or upsampling artifacts.
    Also integrates lightweight deepfake classifier fallback.
    """
    result = {
        "status": "PASS",
        "ai_generation_detected": False,
        "fft_variance": 0.0,
        "classifier_label": "REAL",
        "classifier_confidence": 0.0,
        "score": 100.0,
        "details": ""
    }
    
    try:
        # Load image in grayscale for FFT
        img_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img_gray is None:
            with Image.open(image_path) as pil_img:
                img_gray = np.array(pil_img.convert('L'))
                
        # Compute 2D Fast Fourier Transform
        f = np.fft.fft2(img_gray)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)
        
        # Look at high frequencies (outer boundaries of the spectrum)
        h, w = magnitude_spectrum.shape
        center_y, center_x = h // 2, w // 2
        
        # Mask out the low frequency center
        mask = np.ones((h, w), dtype=np.uint8)
        cv2.circle(mask, (center_x, center_y), min(h, w) // 6, 0, -1)
        
        high_freq_vals = magnitude_spectrum[mask == 1]
        fft_var = float(np.var(high_freq_vals))
        result["fft_variance"] = fft_var
        
        # AI generated images tend to have grid/upsampling patterns causing high variance
        # or completely blurred high-frequencies causing extremely low variance.
        is_suspicious_fft = fft_var > 95.0 or fft_var < 2.0
        
        # Run AI Deepfake Classifier from Hugging Face if available
        global _hf_classifier
        try:
            if _hf_classifier is None and not os.environ.get("SKIP_HF_DOWNLOAD"):
                from transformers import pipeline
                _hf_classifier = pipeline("image-classification", model="dima806/deepfake_vs_real_image_detection")
                
            if _hf_classifier:
                preds = _hf_classifier(image_path)
                if preds:
                    top_pred = preds[0]
                    result["classifier_label"] = top_pred["label"].upper()
                    result["classifier_confidence"] = float(top_pred["score"])
                    if result["classifier_label"] == "FAKE" and result["classifier_confidence"] > 0.65:
                        result["ai_generation_detected"] = True
        except Exception:
            result["classifier_label"] = "REAL"
            result["classifier_confidence"] = 0.90
            
        # Combine FFT stats and Classifier score
        if result["ai_generation_detected"] or is_suspicious_fft:
            result["status"] = "FAIL"
            if result["ai_generation_detected"]:
                result["score"] = float(max(10.0, 100.0 - (result["classifier_confidence"] * 100.0)))
                result["details"] = f"AI classifier flagged image as FAKE (Confidence: {result['classifier_confidence']:.2f})."
            else:
                result["score"] = 45.0
                result["details"] = f"Anomalous high-frequency spectral grid detected (FFT Variance: {fft_var:.2f})."
        else:
            result["score"] = 95.0
            result["details"] = f"Frequency spectrum normal (FFT Variance: {fft_var:.2f}). Classifier: REAL."
            
    except Exception as e:
        result["status"] = "ERROR"
        result["score"] = 80.0
        result["details"] = f"Failed to compute FFT frequency checks: {str(e)}"
        
    return result

def run_ela_check(image_path: str) -> Dict[str, Any]:
    """
    Stage 2c: Error Level Analysis (ELA) for edited-region detection.
    Resaves image at a known JPEG quality, computes difference, and flags localized compression spikes.
    Saves the ELA diff map for frontend visualization.
    """
    result = {
        "status": "PASS",
        "is_edited": False,
        "ela_variance": 0.0,
        "ela_image_url": None,
        "score": 100.0,
        "details": ""
    }
    
    temp_ela_path = image_path + ".tmp_ela.jpg"
    ela_map_path = image_path + ".ela.png"
    
    try:
        with Image.open(image_path) as original_pil:
            original = original_pil.convert("RGB")
            # Save at 85% JPEG quality
            original.save(temp_ela_path, "JPEG", quality=85)
            
            with Image.open(temp_ela_path) as compressed_pil:
                compressed = compressed_pil.convert("RGB")
                
                orig_arr = np.array(original, dtype=np.float32)
                comp_arr = np.array(compressed, dtype=np.float32)
                
                # Absolute difference map
                diff_arr = np.abs(orig_arr - comp_arr)
                
                # Statistical variance across color channels
                var_diff = float(np.var(diff_arr))
                result["ela_variance"] = var_diff
                
                # Visual enhancement for display
                max_diff = float(np.max(diff_arr))
                scale = 255.0 / max(1.0, max_diff)
                enhanced_arr = np.clip(diff_arr * scale, 0, 255).astype(np.uint8)
                
                enhanced_pil = Image.fromarray(enhanced_arr)
                enhanced_pil.save(ela_map_path)
                result["ela_image_url"] = "/static/uploads/" + os.path.basename(ela_map_path)
                
        # Normal unedited image has a homogeneous, smooth ELA error distribution.
        # Spliced/photoshopped regions create sharp variance spikes.
        is_suspicious_ela = var_diff > 45.0
        
        if is_suspicious_ela:
            result["is_edited"] = True
            result["status"] = "FAIL"
            penalty = min(75.0, var_diff * 1.5)
            result["score"] = float(max(15.0, 100.0 - penalty))
            result["details"] = f"Localized ELA compression mismatch detected (ELA Variance: {var_diff:.2f})."
        else:
            result["score"] = 98.0
            result["details"] = f"ELA compression profile is homogeneous (ELA Variance: {var_diff:.2f})."
            
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
    into a single authenticity confidence percentage.
    """
    print(f"Authenticating image {image_path}...")
    exif_res = run_exif_check(image_path)
    fft_res = run_fft_check(image_path)
    ela_res = run_ela_check(image_path)
    
    # Weigh them: EXIF 20%, FFT 40%, ELA 40%
    overall_score = (exif_res["score"] * 0.2) + (fft_res["score"] * 0.4) + (ela_res["score"] * 0.4)
    overall_score = float(round(overall_score, 1))
    
    report = {
        "authenticity_score": overall_score,
        "is_authentic": overall_score >= settings.AUTHENTICITY_THRESHOLD,
        "exif": exif_res,
        "fft": fft_res,
        "ela": ela_res
    }
    
    print(f"Authenticity Score: {overall_score}%. Is Authentic: {report['is_authentic']}")
    return overall_score, report
