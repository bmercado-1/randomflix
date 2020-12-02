from csv import DictReader
from libs.helpers import strikeout
import random


class VideoLibrary:
    def __init__(self, show_list):
        self.show_list = DictReader(open(show_list, mode='r'))

    def print(self):
        for line in self.show_list:
            if line.get('Name').startswith('#'):
                print(strikeout(f"Name: {line.get('Name')}"))
            else:
                print(f"Name: {line.get('Name')}")
                
    def get_categories(self):
        return list(set([line.get("Category").strip() for line in self.show_list]))

    def load(self):
        watched, background, new = {}, {}, {}

        for line in self.show_list:
            if line.get("Name").startswith("#") | line.get("Name").startswith("\n"):
                continue

            else:
                if line.get("Category").strip() == "1":
                    watched.update({line.get('Name').strip(): line.get("Show-URL").strip()})

                elif line.get("Category").strip() == "2":
                    background.update({line.get('Name').strip(): line.get("Show-URL").strip()})

                elif line.get("Category").strip() == "3":
                    new.update({line.get('Name').strip(): line.get("Show-URL").strip()})

        return watched, background, new

    def get_show(self, watch_mode, watched_shows, background_shows, new_shows):
        # Break down random show URL into required components

        if watch_mode == 1:
            categorised_show_list = watched_shows
            show = random.choice(list(categorised_show_list.keys()))
            show_url = categorised_show_list.get(show)

        elif watch_mode == 2:
            categorised_show_list = {**watched_shows, **background_shows}
            show = random.choice(list(categorised_show_list.keys()))
            show_url = categorised_show_list.get(show)

        elif watch_mode == 3:
            categorised_show_list = new_shows
            show = random.choice(list(new_shows.keys()))
            show_url = new_shows.get(show)

        elif watch_mode == 4:
            categorised_show_list = {**watched_shows, **background_shows, **new_shows}
            show = random.choice(list(categorised_show_list.keys()))
            show_url = categorised_show_list.get(show)

        else:
            # categorised_show_list = {"How I Met Your Mother": "https://www.hulu.com/series/how-i-met-your-mother-bc68ac79-3ace-4427-9ec0-5ee6f314d194"}
            categorised_show_list = {"Avatar: The Last Airbender": "https://www.netflix.com/title/70142405"}
            # categorised_show_list = {"Battlestar Galactica", "https://www.amazon.com/gp/video/detail/B000UU2YKE"}
            show = random.choice(list(categorised_show_list.keys()))
            show_url = categorised_show_list.get(show)

        return categorised_show_list, show, show_url

    def get_streaming_service_info(self, url):
        # Build info from url
        showId = url.split("/")[-1]
        service = url.split(".")[1]
        return showId, service

    def get_whats_playing(self, show_name, url, endpoint, service):
        whats_playing = ("\n"
                         "Show: {}\n"
                         "Show URL: {}\n"
                         "HTTP Endpoint: {}\n"
                         "Service: {}\n"
                         .format(show_name, url, endpoint, service.capitalize()))
        print(whats_playing)
