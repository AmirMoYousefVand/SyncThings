import tkinter as tk
import customtkinter as ctk
import tkinter.font as tkfont

ctk.FontManager.load_font("Hubot-Sans-Regular.ttf")
ctk.FontManager.load_font("JetBrainsMono-Regular.ttf")

root = tk.Tk()
print("Loaded families:")
for family in tkfont.families():
    if "hubot" in family.lower() or "jetbrains" in family.lower():
        print("->", family)
root.destroy()
