import customtkinter as ctk

ctk.set_appearance_mode("Light")

app = ctk.CTk()
app.geometry("400x300")

def toggle():
    if ctk.get_appearance_mode() == "Dark":
        ctk.set_appearance_mode("Light")
    else:
        ctk.set_appearance_mode("Dark")

btn = ctk.CTkButton(app, text="Toggle Theme", command=toggle)
btn.pack(pady=20)

app.mainloop()
