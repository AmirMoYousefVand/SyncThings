import os
import json
import hashlib
import base64
import io
import random
from PIL import Image, ImageDraw, ImageFont
from config import CONFIG_FILE

def load_profile(default_name):
    """Loads profile data from the config file."""
    profile_name = default_name
    avatar_path = None
    avatar_b64 = None
    mini_avatar_b64 = None
    theme = "Light"
    lang = "en"
    state = "zoomed"

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                profile_name = config.get("name", default_name)
                avatar_path = config.get("avatar", None)
                avatar_b64 = config.get("avatar_b64", None)
                mini_avatar_b64 = config.get("mini_avatar_b64", None)
                theme = config.get("theme", theme)
                lang = config.get("lang", lang)
                state = config.get("state", state)
        except Exception:
            pass

    if not avatar_b64 and not avatar_path:
        avatar_b64, mini_avatar_b64 = generate_random_avatar()
        save_profile(profile_name, avatar_path, avatar_b64, mini_avatar_b64, theme, lang, state)

    return profile_name, avatar_path, avatar_b64, theme, lang, state

def save_profile(profile_name, avatar_path, avatar_b64=None, mini_avatar_b64=None, theme="Light", lang="en", state="zoomed"):
    """Saves profile data to the config file."""
    if mini_avatar_b64 is None and os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                old_conf = json.load(f)
                mini_avatar_b64 = old_conf.get("mini_avatar_b64")
        except:
            pass

    # If avatar_b64 is provided but not mini_avatar, try to generate it
    if avatar_b64 and not mini_avatar_b64:
        try:
            img_data = base64.b64decode(avatar_b64)
            img = Image.open(io.BytesIO(img_data)).convert("RGBA")
            mini_img = img.resize((50, 50), Image.Resampling.LANCZOS)
            mini_out = io.BytesIO()
            mini_img.save(mini_out, format="PNG")
            mini_avatar_b64 = base64.b64encode(mini_out.getvalue()).decode('utf-8')
        except:
            pass

    config = {
        "name": profile_name, "avatar": avatar_path, "avatar_b64": avatar_b64, "mini_avatar_b64": mini_avatar_b64,
        "theme": theme, "lang": lang, "state": state
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving profile: {e}")

def get_mini_avatar_b64():
    """Gets the mini avatar from config."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get("mini_avatar_b64")
        except:
            pass
    return None

def generate_pixel_avatar(seed_string, size=200, grid_size=8):
    """Generates a random 8-bit style pixel art avatar."""
    random.seed(seed_string)

    # Generate random vibrant colors
    hue_base = random.random()
    bg_color = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
    primary_color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
    secondary_color = (max(0, primary_color[0]-40), max(0, primary_color[1]-40), max(0, primary_color[2]-40))

    img = Image.new('RGBA', (grid_size, grid_size), bg_color)
    pixels = img.load()

    # Generate symmetrical pixel art
    for x in range(grid_size // 2):
        for y in range(grid_size):
            val = random.random()
            if val > 0.6:
                color = primary_color
            elif val > 0.3:
                color = secondary_color
            else:
                color = (0,0,0,0) # transparent inner

            pixels[x, y] = color
            pixels[grid_size - 1 - x, y] = color # mirror

    # Scale up using Nearest Neighbor to keep it sharp
    img = img.resize((size, size), Image.Resampling.NEAREST)

    # Give it a nice circular background
    circle_bg = Image.new('RGBA', (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(circle_bg)
    draw.ellipse((0, 0, size, size), fill=bg_color)

    # Paste the pixel art in the middle (slightly smaller)
    padding = size // 6
    inner_size = size - (padding * 2)
    img_inner = img.resize((inner_size, inner_size), Image.Resampling.NEAREST)
    circle_bg.paste(img_inner, (padding, padding), img_inner)

    return circle_bg

def generate_random_avatar(main_size=200, mini_size=50):
    """Generates a random avatar. Returns main and mini base64 strings."""
    # Generate a random seed
    seed = str(random.random())
    main_img = generate_pixel_avatar(seed, main_size)
    mini_img = main_img.resize((mini_size, mini_size), Image.Resampling.LANCZOS)

    main_out = io.BytesIO()
    main_img.save(main_out, format="PNG")
    main_b64 = base64.b64encode(main_out.getvalue()).decode('utf-8')

    mini_out = io.BytesIO()
    mini_img.save(mini_out, format="PNG")
    mini_b64 = base64.b64encode(mini_out.getvalue()).decode('utf-8')

    return main_b64, mini_b64

def generate_default_avatar(name, size=100):
    """Generates a default avatar based on the user's name."""
    name_str = name if name else "?"
    hash_val = int(hashlib.md5(name_str.encode('utf-8')).hexdigest(), 16)
    colors = ["#F43F5E", "#F97316", "#EAB308", "#22C55E", "#14B8A6", "#0EA5E9", "#8B5CF6", "#D946EF"]
    bg_color = colors[hash_val % len(colors)]

    img = Image.new('RGB', (size, size), color=bg_color)
    draw = ImageDraw.Draw(img)

    first_letter = name_str[0]
    try:
        font = ImageFont.truetype("arial.ttf", int(size*0.4))
    except Exception:
        font = ImageFont.load_default()

    try:
        bbox = draw.textbbox((0, 0), first_letter, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        # Fallback for older PIL versions
        w, h = draw.textsize(first_letter, font=font)

    draw.text(((size-w)/2, (size-h)/2 - (size*0.05)), first_letter, fill="#FFFFFF", font=font)

    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size, size), fill=255)

    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask=mask)
    return output

def get_avatar_image(path, b64_data, name, size=100):
    """Gets the avatar image from a path, base64 data, or generates a default one."""
    if b64_data:
        try:
            img_data = base64.b64decode(b64_data)
            img = Image.open(io.BytesIO(img_data)).convert("RGBA").resize((size, size))
            return apply_circular_mask(img, size)
        except Exception:
            pass

    if path and os.path.exists(path):
        try:
            img = Image.open(path).convert("RGBA").resize((size, size))
            return apply_circular_mask(img, size)
        except Exception:
            pass

    return generate_default_avatar(name, size)

def apply_circular_mask(img, size):
    """Applies a circular mask to an image."""
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size, size), fill=255)
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask=mask)
    return output

def file_to_base64(file_path):
    """Converts a file to a base64 string."""
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        return None
