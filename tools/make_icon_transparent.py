from PIL import Image, ImageFilter
import sys
import os

def smooth_icon(image_path):
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    print(f"Processing {image_path}...")
    img = Image.open(image_path).convert("RGBA")
    
    # Extract Alpha
    r, g, b, a = img.split()
    
    # 1. Mild Erosion: Removes the outer 'fringe' of pixels which are often jagged or contain white halo artifacts.
    #    MinFilter(3) is a 3x3 kernel, effectively eroding 1 pixel radius.
    print("Applying erosion to remove jagged artifacts...")
    a = a.filter(ImageFilter.MinFilter(3))
    
    # 2. Gaussian Blur: Softens the transition to create antialiasing.
    #    Radius 1.0 gives a nice smooth edge without being too blurry.
    print("Applying gaussian blur for smoothing...")
    a = a.filter(ImageFilter.GaussianBlur(1.0))
    
    # Merge back the new smooth alpha
    img = Image.merge("RGBA", (r, g, b, a))
    
    img.save(image_path, "PNG")
    print(f"Done! Smoothed {image_path}")

if __name__ == "__main__":
    smooth_icon("icon.png")
