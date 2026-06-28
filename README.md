# AI iCloud UGC Image Organizer

AI-powered image organizer with two versions — one for iPad (browser-based) and one for Windows PC (desktop app). Both use Claude AI to analyze images and suggest descriptive filenames, then sort them into your folder structure.

---

## iPad Version (GitHub Pages)

**Live at:** `https://hduggan72-source.github.io/AI-iCloud-UGC-Image-Organizer/`

- Opens in Safari on iPad — works like a native app
- Select images from iCloud Drive via the Files picker
- Claude AI suggests a filename for each image
- Pick a category with one tap
- Exports an organized ZIP you save back to iCloud Drive

**To use:**
1. Open the URL in Safari on your iPad
2. Tap the Share button → Add to Home Screen for easy access
3. Enter your Anthropic API key on first launch (saved for future sessions)
4. Select images → name → categorize → download ZIP

---

## Desktop Version (Windows PC)

Runs a local browser UI. Files are **actually moved** into your folder structure (or exported as ZIP — your choice).

**Setup:**
1. Install Python from [python.org](https://python.org)
2. Download or clone this repo
3. Open `desktop/ugc_organizer_desktop.py` in Notepad
4. Edit the **CONFIG section** at the top:
   - Paste your Anthropic API key
   - Set `WATCH_PATH` to your folder
   - Choose `EXPORT_MODE` — `"move"` or `"zip"`
   - Customize `CATEGORIES` if needed
5. Double-click `desktop/run_organizer.bat`

**Config options:**

```python
ANTHROPIC_API_KEY = "sk-ant-YOUR-KEY-HERE"   # from console.anthropic.com
WATCH_PATH        = r"C:\Users\...\Avatars"   # your root folder
INBOX_FOLDER      = "_inbox"                  # drop files here
EXPORT_MODE       = "move"                    # "move" or "zip"
ZIP_OUTPUT_PATH   = r"C:\Users\...\Desktop\UGC-Organized.zip"
IMAGE_EXTENSIONS  = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}
```

---

## API Key

Get a free key at [console.anthropic.com](https://console.anthropic.com). Image analysis costs ~$0.001 per image — $1 covers roughly 1,000 images.

---

## Categories

Edit the `CATEGORIES` block in either file to match your folder structure:

```python
# Format: "number": ("PREFIX-", "Subfolder Name")
CATEGORIES = {
    "1": ("MIKAYLA-",  "MIKAYLA"),
    "2": ("NOCTURNA-", "NOCTURNA"),
    ...
}
```

Files are named `PREFIX-description.jpg` and sorted into the matching subfolder.
