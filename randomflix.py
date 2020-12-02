import webbrowser

from libs.videoLibrary import VideoLibrary
from libs.roku import Roku
from libs.helpers import *


# Read program config
config = read_config_file()

# Create Video Library instance
video_library = VideoLibrary("./shows.csv")

# Create Roku Instance
roku = Roku(config.get("ip"))

# Parse library and sort into dictionaries by category
watched, background, new = video_library.load()

while True:
    # Get Random Show
    filtered_list, show, show_url = video_library.get_show(int(config.get("mode")), watched, background, new)

    # Parse Show URL for streaming service info
    show_id, service = video_library.get_streaming_service_info(show_url)

    # Build endpoint for Roku Universal Search
    endpoint = roku.build_roku_search_endpoint(show_name=show, service=service, ip=config.get("ip"))

    # Show what's playing
    video_library.get_whats_playing(show, show_url, endpoint, service)

    # Generate cli message
    CLI_MESSAGE = f'''
            Random Mode: {config.get("mode")}

            1) Play current choice on Roku
            2) Play current choice on local device for casting
            3) Change Category
            
            9) Exit

            Type your choice or press enter to roll another show '''

    choice = input(CLI_MESSAGE).lower()

    if choice == "1":
        try:
            roku.play_on_roku()
            input("Press Enter To Roll Another Random Show")
        except:
            print("Error connecting to Roku ... configured IP might not longer be right")

    elif choice == "2":
        webbrowser.open(show_url.strip(), new=1)

    elif choice == "3":
        category = '''
                    1 = Watched Mode 
                    2 = Background Mode 
                    3 = Active Mode 
                    4 = Full Random

                    Enter your choice: '''

        config["mode"] = int(input(category))

    elif choice == "9":
        exit(0)
