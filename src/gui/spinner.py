import customtkinter as ctk
import tkinter as tk
import math

class LoadingSpinner(ctk.CTkFrame):
    def __init__(self, master, size=30, color="#7C3AED", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.size = size
        self.color = color
        self.angle = 0
        self.is_spinning = False
        
        # Resolve color. Canvas doesn't support "transparent".
        bg_color = self._apply_appearance_mode(self._fg_color)
        if bg_color == "transparent":
            # Fallback to the likely background color of the app
            # SetupWizard uses #0F0E13, but let's try to be generic or default to that
            bg_color = "#0F0E13" 

        self.canvas = tk.Canvas(
            self, 
            width=size, 
            height=size, 
            bg=bg_color, 
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Make canvas background transparent-ish (matches parent if provided)
        # Note: True transparency in Tkinter isn't perfect, but matching bg helps.
        
        self.arc = self.canvas.create_arc(
            2, 2, size-2, size-2,
            start=0, extent=100, 
            outline=color, width=3, style="arc"
        )

    def start(self):
        if not self.is_spinning:
            self.is_spinning = True
            self.animate()

    def stop(self):
        self.is_spinning = False

    def animate(self):
        if not self.is_spinning:
            return
        
        self.angle = (self.angle + 10) % 360
        self.canvas.itemconfigure(self.arc, start=self.angle)
        self.after(20, self.animate)
        
    def configure(self, **kwargs):
        if "fg_color" in kwargs:
            bg = self._apply_appearance_mode(kwargs["fg_color"])
            self.canvas.configure(bg=bg)
        super().configure(**kwargs)
