#!/usr/bin/env python3
"""
Haven Preview
Renders a single frame so you can see the visual style instantly.

Usage:
    python3 haven_preview.py
    python3 haven_preview.py --canvas "#08080c" --lines "#7dd3c4" --seed 42
"""

import argparse
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from haven_visuals import HavenVisuals
from config import PALETTES


def main():
    parser = argparse.ArgumentParser(description='Haven Visual Preview')
    parser.add_argument('--canvas', default='#08080c', help='Canvas color')
    parser.add_argument('--lines', default='#7dd3c4', help='Line color')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--frame', type=int, default=60, help='Frame to render (0-239)')
    parser.add_argument('--output', default='preview_frame.jpg', help='Output file')
    args = parser.parse_args()
    
    print("🎨 Haven Visual Preview")
    print(f"   Canvas: {args.canvas} | Lines: {args.lines} | Seed: {args.seed}")
    print(f"   Rendering frame {args.frame}...")
    
    haven = HavenVisuals(width=1920, height=1080, fps=24, duration=10, seed=args.seed)
    frame = haven.render_frame(args.frame, args.canvas, args.lines)
    frame.save(args.output, quality=95)
    
    print(f"✅ Preview saved: {args.output}")
    print("   Open it to see the visual style.")


if __name__ == "__main__":
    main()
