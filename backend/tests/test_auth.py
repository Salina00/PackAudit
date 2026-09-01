import sys
import os
import numpy as np
from PIL import Image, ImageDraw

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.stages.stage2_auth import (
    run_exif_check,
    run_fft_check,
    run_ela_check,
    authenticate_image
)

def create_synthetic_test_images():
    os.makedirs("test_artifacts", exist_ok=True)
    
    # 1. Clean Authentic image
    img_clean = Image.new("RGB", (300, 300), color=(240, 240, 240))
    draw = ImageDraw.Draw(img_clean)
    draw.rectangle([50, 50, 250, 250], outline=(20, 20, 20), width=2)
    draw.text((80, 120), "Authentic Package Label", fill=(0, 0, 0))
    clean_path = os.path.join("test_artifacts", "clean_sample.jpg")
    img_clean.save(clean_path, "JPEG", quality=95)
    
    # 2. Tampered Spliced image (creating heavy local compression mismatch)
    img_tampered = img_clean.copy()
    draw_t = ImageDraw.Draw(img_tampered)
    # Inject a distinct noisy block to simulate spliced price/date
    noise_block = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)
    noise_pil = Image.fromarray(noise_block)
    img_tampered.paste(noise_pil, (100, 100))
    tampered_path = os.path.join("test_artifacts", "tampered_sample.jpg")
    img_tampered.save(tampered_path, "JPEG", quality=95)
    
    return clean_path, tampered_path

def test_stage2_forensics():
    clean_path, tampered_path = create_synthetic_test_images()
    
    print("\n=======================================================")
    print("TEST 1: EXIF Metadata & Editing Software Detection")
    print("=======================================================")
    
    # Test un-edited image (missing EXIF or clean)
    exif_clean = run_exif_check(clean_path)
    print("Clean Image EXIF:", exif_clean["status"], f"(Score: {exif_clean['score']}%) ->", exif_clean["details"])
    assert exif_clean["editing_software_detected"] is False
    assert exif_clean["score"] >= 70.0
    
    print("\n=======================================================")
    print("TEST 2: Error Level Analysis (ELA) Splicing Detection")
    print("=======================================================")
    
    ela_clean = run_ela_check(clean_path)
    print(f"Clean ELA Variance: {ela_clean['ela_variance']:.2f}, Status: {ela_clean['status']}")
    assert os.path.exists(clean_path + ".ela.png"), "ELA diff image map was not generated."
    
    ela_tampered = run_ela_check(tampered_path)
    print(f"Tampered ELA Variance: {ela_tampered['ela_variance']:.2f}, Status: {ela_tampered['status']}, Details: {ela_tampered['details']}")
    assert ela_tampered["ela_variance"] > ela_clean["ela_variance"]
    
    print("\n=======================================================")
    print("TEST 3: Fast Fourier Transform (FFT) 2D Frequency Analysis")
    print("=======================================================")
    
    fft_clean = run_fft_check(clean_path)
    print(f"Clean FFT High-Freq Variance: {fft_clean['fft_variance']:.2f}, Status: {fft_clean['status']}")
    assert "fft_variance" in fft_clean
    assert fft_clean["fft_variance"] > 0
    
    print("\n=======================================================")
    print("TEST 4: End-to-End Authenticity Weighted Pipeline")
    print("=======================================================")
    
    overall_score, report = authenticate_image(clean_path)
    print(f"Overall Authenticity Score: {overall_score}%, Is Authentic: {report['is_authentic']}")
    assert report["is_authentic"] is True
    assert "exif" in report and "fft" in report and "ela" in report
    
    # Cleanup test artifacts
    for p in [clean_path, tampered_path, clean_path + ".ela.png", tampered_path + ".ela.png"]:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists("test_artifacts"):
        try:
            os.rmdir("test_artifacts")
        except:
            pass
            
    print("\nALL STAGE 2 IMAGE FORENSICS & ANTI-SPOOFING CHECKS PASSED!")

if __name__ == "__main__":
    test_stage2_forensics()
