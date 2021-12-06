from json import dump, load
from pathlib import Path
import webbrowser

from libs import *
from libs.videoLibrary import VideoLibrary
from libs.roku import Roku
from gdrive.gdrive import get_shows_csv


def main():
    # Argument Parser
    define_args()

    # Read program config
    config = read_config_file()

    # Create Video Library instance
    show_file = Path("shows.csv")
    if show_file.exists():
        vl = VideoLibrary("./shows.csv")
    else:
        choice = input("Enter G to try downloading shows.csv from Google Drive: \n")
        if choice == "G":
            get_shows_csv()
            vl = VideoLibrary("./shows.csv")
        else:
            raise Exception("No shows.csv in root dir.")

    # Create Roku Instance
    roku = Roku(config.get("ip"))

    # Set play mode from config
    play_mode = config.get("mode")

    while True:
        # Get Random Show
        vl.get_show(int(play_mode))

        # Build endpoint for Roku Universal Search
        endpoint = roku.build_roku_search_endpoint(show_name=vl.show, service=vl.service, ip=config.get("ip"))

        # Show what's playing
        print(vl.get_whats_playing())

        # Generate cli message
        choice = input(CLI_MESSAGE.format(mode=play_mode)).lower()

        if choice == "1":
            webbrowser.open(vl.show_url.strip(), new=1)
            choice = input("\nPress Enter To Roll Another Random Show or x to Open Show on Reelgood: ")

            if choice.lower() == 'x':
                search_reelgood(vl.show)

        elif choice == "2":
            try:
                roku.play_on_roku(endpoint)
                input("Press Enter To Roll Another Random Show")
            except:
                print(
                    "Error connecting to Roku ... configured IP might not longer be right"
                )

        elif choice == "3":
            search_reelgood(vl.show)

        elif choice == "4":
            play_mode = change_category()

        elif choice == "5":
            vl.print_db()

        elif choice == "6":
            get_shows_csv()

        elif choice == "9":
            exit(0)


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


def search_reelgood(show: str):
    """
    Searches Reelgood for the current show on deck
    :param show: str Show name as a string
    """
    webbrowser.open(f"https://reelgood.com/search?q={show}", new=1)


def change_category():
    """
    Changes the currently loaded show category
    :return: New show category (int)
    """
    category = """
                1 = Watched Mode 
                2 = Background Mode 
                3 = Active Mode 
                4 = Full Random

                Enter your choice: """

    return int(input(category))


if __name__ == '__main__':
    main()
