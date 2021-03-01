import webbrowser

from libs.videoLibrary import VideoLibrary
from libs.roku import Roku
from libs.helpers import *

# Read program config
config = read_config_file()

# Create Video Library instance
vl = VideoLibrary("./shows.csv")

# Create Roku Instance
roku = Roku(config.get("ip"))

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
        try:
            roku.play_on_roku()
            input("Press Enter To Roll Another Random Show")
        except:
            print(
                "Error connecting to Roku ... configured IP might not longer be right"
            )

    elif choice == "2":
        webbrowser.open(vl.show_url.strip(), new=1)

    elif choice == "3":
        play_mode = change_category()

    elif choice == "4":
        search_reelgood(vl.show)

    elif choice == "5":
        vl.print_db()

    elif choice == "9":
        exit(0)
