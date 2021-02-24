import webbrowser
from tkinter import *
from tkinter import ttk

from libs.videoLibrary import VideoLibrary
from libs.helpers import *


# SETUP
config = read_config_file()
vl = VideoLibrary("./shows.csv")


# Event Handlers
def get_show():
    # Get Random Show
    vl.get_show(int(config.get("mode")))

    # Show what's playing
    lbl_whats_playing["text"] = vl.get_whats_playing()


def play_show_local():
    webbrowser.open(vl.show_url.strip(), new=1)


# GUI
window = Tk()
window.title("Randomflix")
window.geometry("200x200")
window.config(background="white")

frm_commands = Frame(master=window, background="white")
frm_commands.pack(side="bottom")

btn_roll_show = ttk.Button(master=frm_commands, text="Roll Show", command=get_show)
btn_roll_show.pack(side="left")

btn_play_local = ttk.Button(
    master=frm_commands, text="Local/Cast", command=play_show_local
)
btn_play_local.pack(side="right")

lbl_heading = Label(master=window, text="What's Playing")
lbl_heading.pack(side="top")

lbl_whats_playing = Label(master=window, text="Output")
lbl_whats_playing.pack(side="top")


window.mainloop()
