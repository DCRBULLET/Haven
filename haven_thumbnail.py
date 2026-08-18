#!/usr/bin/env python3
"""
Haven Thumbnail Generator
Creates YouTube thumbnails using the two-color system.

Usage:
    python3 haven_thumbnail.py
    python3 haven_thumbnail.py --title "Custom Title" --output thumb.jpg
"""

import argparse
import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import load_config


class HavenThumbnail:
    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height
    
    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _generate_grain(self, canvas_color, line_color, seed=42):
        np.random.seed(seed)
        grain_w = self.width // 8
        grain_h = self.height // 8
        grain = np.random.rand(grain_h, grain_w).astype(np.float32)
        
        canvas_rgb = self._hex_to_rgb(canvas_color)
        line_rgb = self._hex_to_rgb(line_color)
        grain_rgb = tuple(int(c1 + (c2 - c1) * 0.3) for c1, c2 in zip(canvas_rgb, line_rgb))
        
        grain_img = np.zeros((grain_h, grain_w, 3), dtype=np.uint8)
        for c in range(3):
            grain_img[:, :, c] = np.clip(
                canvas_rgb[c] + (grain_rgb[c] - canvas_rgb[c]) * grain * 0.05,
                0, 255
            ).astype(np.uint8)
        
        grain_pil = Image.fromarray(grain_img, 'RGB')
        grain_pil = grain_pil.resize((self.width, self.height), Image.Resampling.BILINEAR)
        return grain_pil
    
    def _draw_scratch_lines(self, draw, line_color, canvas_color, seed=42):
        random.seed(seed)
        line_rgb = self._hex_to_rgb(line_color)
        
        # Draw 15-25 subtle scratch lines
        for _ in range(random.randint(15, 25)):
            x1 = random.randint(0, self.width)
            y1 = random.randint(0, self.height)
            x2 = x1 + random.randint(-200, 200)
            y2 = y1 + random.randint(-200, 200)
            
            alpha = random.randint(20, 60)
            thickness = random.randint(1, 2)
            color = line_rgb + (alpha,)
            draw.line([(x1, y1), (x2, y2)], fill=color, width=thickness)
    
    def _get_font(self, size, bold=False):
        """Try to find a good system font"""
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except:
                    pass
        
        return ImageFont.load_default()
    
    def generate(self, title, duration_text, canvas_color, line_color, 
                 subtitle="Ambient Music for Deep Focus", seed=42, output_path="thumb.jpg"):
        
        canvas_rgb = self._hex_to_rgb(canvas_color)
        line_rgb = self._hex_to_rgb(line_color)
        
        # Create base image
        img = Image.new('RGB', (self.width, self.height), canvas_rgb)
        
        # Add grain
        grain = self._generate_grain(canvas_color, line_color, seed)
        img = Image.blend(img, grain, 0.5)
        
        # Create overlay for lines
        overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Draw scratch lines
        self._draw_scratch_lines(draw, line_color, canvas_color, seed)
        
        # Composite lines
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)
        
        # Fonts
        title_font = self._get_font(72, bold=True)
        duration_font = self._get_font(90, bold=True)
        subtitle_font = self._get_font(32)
        badge_font = self._get_font(28, bold=True)
        
        # Duration badge (top right)
        badge_text = duration_text.upper()
        bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        badge_w = bbox[2] - bbox[0]
        badge_h = bbox[3] - bbox[1]
        badge_x = self.width - badge_w - 40
        badge_y = 30
        
        # Badge background (subtle rectangle)
        badge_padding = 15
        draw.rectangle(
            [badge_x - badge_padding, badge_y - badge_padding,
             badge_x + badge_w + badge_padding, badge_y + badge_h + badge_padding],
            fill=line_rgb + (40,)
        )
        draw.text((badge_x, badge_y), badge_text, font=badge_font, fill=line_rgb + (255,))
        
        # Main title (center, large)
        # Split title if too long
        words = title.split()
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=title_font)
            if bbox[2] - bbox[0] > self.width - 100:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        if current_line:
            lines.append(' '.join(current_line))
        
        line_height = 85
        total_text_height = len(lines) * line_height
        start_y = (self.height - total_text_height) // 2 - 30
        
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_w = bbox[2] - bbox[0]
            x = (self.width - text_w) // 2
            y = start_y + i * line_height
            
            # Glow effect (multiple offsets)
            for offset in range(3, 0, -1):
                glow_alpha = int(80 / offset)
                glow_color = line_rgb + (glow_alpha,)
                draw.text((x, y), line, font=title_font, fill=glow_color)
            
            # Main text
            draw.text((x, y), line, font=title_font, fill=line_rgb + (255,))
        
        # Subtitle (below title)
        bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        sub_w = bbox[2] - bbox[0]
        sub_x = (self.width - sub_w) // 2
        sub_y = start_y + total_text_height + 20
        draw.text((sub_x, sub_y), subtitle, font=subtitle_font, fill=line_rgb + (150,))
        
        # Bottom accent line
        line_y = self.height - 80
        draw.line([(100, line_y), (self.width - 100, line_y)], 
                  fill=line_rgb + (60,), width=2)
        
        # Convert back to RGB
        img = img.convert('RGB')
        
        # Save
        img.save(output_path, quality=95)
        print(f"✅ Thumbnail saved: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(description='Haven Thumbnail Generator')
    parser.add_argument('--title', default=None, help='Video title')
    parser.add_argument('--duration', default=None, help='Duration text (e.g., "3 HOURS")')
    parser.add_argument('--canvas', default=None, help='Canvas color hex')
    parser.add_argument('--lines', default=None, help='Line color hex')
    parser.add_argument('--seed', type=int, default=None, help='Random seed')
    parser.add_argument('--output', default='thumbs/haven_thumb.jpg', help='Output path')
    args = parser.parse_args()
    
    config = load_config()
    
    title = args.title if args.title else config.get('title', 'Ambient Music')
    duration = args.duration if args.duration else f"{config.get('target_duration_hours', 3)} HOURS"
    canvas = args.canvas if args.canvas else config.get('canvas_color', '#08080c')
    lines = args.lines if args.lines else config.get('line_color', '#7dd3c4')
    seed = args.seed if args.seed is not None else config.get('seed', 42)
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    generator = HavenThumbnail()
    generator.generate(
        title=title,
        duration_text=duration,
        canvas_color=canvas,
        line_color=lines,
        seed=seed,
        output_path=args.output
    )


if __name__ == "__main__":
    main()
