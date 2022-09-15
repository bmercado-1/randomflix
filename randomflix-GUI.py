import tkinter
from json import dump, load
from tkinter import *
from tkinter import ttk
import webbrowser

from libs import *
from libs.videoLibrary import VideoLibrary

def main():
    # SETUP
    config = read_config_file()
    vl = VideoLibrary("./shows.csv")

    # Set default play mode from config
    default_play_mode = config.get("mode")

    # Event Handlers
    def get_show():
        # Get Random Show
        play_mode = category_entered.get() if category_entered.get() else default_play_mode
        vl.get_show(int(play_mode))

        # Show what's playing
        lbl_whats_playing["text"] = vl.get_whats_playing() + f"\nCategory: {play_mode}"


    def play_show_local():
        webbrowser.open(vl.show_url.strip(), new=1)


    # Create GUI main window
    root = Tk()
    root.title("Randomflix")
    root.geometry("250x200")
    root.config(background="gray")

    frm_commands = Frame(master=root, relief=GROOVE, width=200, height=150, background="gray")
    frm_commands.pack(side="bottom")
    
    # Set Top Labels
    lbl_heading = Label(master=root, text="What's Playing")
    lbl_heading.pack(side="top")

    lbl_whats_playing = Label(master=root, text="")
    lbl_whats_playing.pack(side="top")

    # Create Text Entry box to set the show category
    category_entered = ttk.Entry(root, width=15)
    category_entered.pack(side="bottom")

    lbl_category = Label(master=root, text="Override Category")
    lbl_category.pack(side="bottom")

    # Create bottom buttons
    btn_roll_show = ttk.Button(master=frm_commands, text="Roll Show", command=get_show)
    btn_roll_show.pack(side="left")

    btn_play_local = ttk.Button(
        master=frm_commands, text="Play Show", command=play_show_local
    )
    btn_play_local.pack(side="right")

    # Start GUI
    root.mainloop()


def generate_default_config():
    """
    Resets program config to default settings
    :return: JSON file
    """

    config = {
        "mode": "2",
        "search": True,
        "ip": "192.168.1.163",
        "ip2": "192.168.1.197",
    }

    with open("./config.json", mode="w") as config_file:
        dump(config, config_file, indent=4)


def read_config_file():
    """
    Ingests config.json to generate program config at runtime
    :return:
    """
    try:
        with open("./config.json", mode="r") as config_file:
            config = load(config_file)
            return config

    except FileNotFoundError:
        print("Config File Does Not Exist! Generating Default")
        generate_default_config()


if __name__ == '__main__':
    main()
