from fontTools.ttLib import TTFont

def get_font_name(font_path):
    font = TTFont(font_path)
    for record in font['name'].names:
        if record.nameID == 1:
            if b'\x00' in record.string:
                name = record.string.decode('utf-16-be')
            else:
                name = record.string.decode('utf-8')
            return name
    return None

print(f"Hubot name: {get_font_name('Hubot-Sans-Regular.ttf')}")
