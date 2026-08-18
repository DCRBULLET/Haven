import random

import imageio
import numpy as np
from PIL import Image, ImageFilter


class HavenVisuals:
    def __init__(self, width=1920, height=1080, fps=24, duration=10, seed=42):
        self.width = width
        self.height = height
        self.fps = fps
        self.duration = duration
        self.total_frames = fps * duration
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

        self.render_scale = 4
        self.field_width = max(96, width // self.render_scale)
        self.field_height = max(54, height // self.render_scale)

        x = np.linspace(-1.0, 1.0, self.field_width, dtype=np.float32)
        y = np.linspace(-1.0, 1.0, self.field_height, dtype=np.float32)
        self.grid_x, self.grid_y = np.meshgrid(x, y)
        self.radius = np.sqrt(self.grid_x**2 + self.grid_y**2)

        rng = np.random.default_rng(seed)
        self.thresholds = np.linspace(-1.4, 1.4, 12, dtype=np.float32)
        self.band_sigma = 0.055
        self.grain_strength = 8
        self.component_offsets = rng.uniform(-3.0, 3.0, size=(4, 2)).astype(np.float32)
        self.component_phases = rng.uniform(0.0, np.pi * 2.0, size=4).astype(np.float32)
        self.drift = rng.uniform(0.12, 0.36, size=(4, 2)).astype(np.float32)

    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    def _scalar_field(self, frame_idx):
        theta = (frame_idx / max(1, self.total_frames)) * np.pi * 2.0
        orbit_x = np.cos(theta)
        orbit_y = np.sin(theta)

        x1 = self.grid_x * 3.1 + self.grid_y * 1.2 + self.component_offsets[0, 0] + orbit_x * self.drift[0, 0]
        y1 = self.grid_y * 2.8 - self.grid_x * 0.7 + self.component_offsets[0, 1] + orbit_y * self.drift[0, 1]

        x2 = self.grid_x * 4.9 - self.grid_y * 0.9 + self.component_offsets[1, 0] - orbit_y * self.drift[1, 0]
        y2 = self.grid_y * 4.1 + self.grid_x * 0.5 + self.component_offsets[1, 1] + orbit_x * self.drift[1, 1]

        x3 = self.grid_x * 7.0 + self.component_offsets[2, 0] + orbit_x * self.drift[2, 0]
        y3 = self.grid_y * 6.3 + self.component_offsets[2, 1] - orbit_y * self.drift[2, 1]

        field = (
            0.75 * np.sin(x1 + self.component_phases[0])
            + 0.55 * np.cos(y1 + self.component_phases[1])
            + 0.38 * np.sin(x2 + y2 + self.component_phases[2])
            + 0.22 * np.cos((x3 - y3) * 0.7 + self.component_phases[3])
            + 0.18 * np.sin((self.grid_x * 5.4 + self.grid_y * 3.1) + theta * 0.45)
            + 0.14 * np.cos((self.grid_y * 5.0 - self.grid_x * 2.2) - theta * 0.35)
        )
        return field.astype(np.float32)

    def _contour_intensity(self, field):
        intensity = np.zeros_like(field, dtype=np.float32)
        for level in self.thresholds:
            distance = field - level
            intensity += np.exp(-(distance * distance) / (2.0 * self.band_sigma * self.band_sigma))

        intensity /= float(len(self.thresholds))
        intensity = np.power(np.clip(intensity * 2.2, 0.0, 1.0), 1.15)

        center_falloff = np.clip(1.15 - self.radius * 0.55, 0.55, 1.1)
        return np.clip(intensity * center_falloff, 0.0, 1.0)

    def _compose_frame(self, contour, canvas_rgb, line_rgb, frame_idx):
        contour_img = Image.fromarray((contour * 255).astype(np.uint8))
        contour_img = contour_img.resize((self.width, self.height), Image.Resampling.BICUBIC)
        glow_img = contour_img.filter(ImageFilter.GaussianBlur(radius=3.2))
        core_img = contour_img.filter(ImageFilter.GaussianBlur(radius=0.4))

        glow = np.asarray(glow_img, dtype=np.float32) / 255.0
        core = np.asarray(core_img, dtype=np.float32) / 255.0

        glow = np.power(np.clip(glow, 0.0, 1.0), 1.35)
        core = np.power(np.clip(core, 0.0, 1.0), 0.92)
        line_mask = np.clip(glow * 0.35 + core * 0.95, 0.0, 1.0)

        canvas = np.zeros((self.height, self.width, 3), dtype=np.float32)
        canvas[:, :] = np.array(canvas_rgb, dtype=np.float32)
        line = np.array(line_rgb, dtype=np.float32)

        frame = canvas + (line - canvas) * line_mask[..., None] * 0.9

        grain_rng = np.random.default_rng(self.seed + frame_idx)
        grain = grain_rng.normal(0.0, self.grain_strength, size=frame.shape)
        frame = np.clip(frame + grain, 0.0, 255.0)

        return Image.fromarray(frame.astype(np.uint8))

    def render_frame(self, frame_idx, canvas_color, line_color):
        field = self._scalar_field(frame_idx)
        contour = self._contour_intensity(field)
        return self._compose_frame(contour, self._hex_to_rgb(canvas_color), self._hex_to_rgb(line_color), frame_idx)

    def render_video(self, output_path, canvas_color="#08080c", line_color="#7dd3c4"):
        writer = imageio.get_writer(output_path, fps=self.fps)
        for i in range(self.total_frames):
            frame = self.render_frame(i, canvas_color, line_color)
            writer.append_data(np.array(frame))
        writer.close()
        print(f"✅ Video rendered: {output_path}")
