try:
    import cairosvg
    print("cairosvg imported!")
except Exception as e:
    import traceback
    traceback.print_exc()
