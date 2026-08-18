"""Manual live check; deliberately not collected by pytest."""
import sys


def main():
    sys.path.insert(0, '.')
    from haven_music_gen import generate_music
    result = generate_music("A deep sleep soundscape for sleeping.")
    print(f"Success! Saved to: {result}")


if __name__ == "__main__":
    main()
