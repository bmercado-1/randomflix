from csv import DictReader
from libs.helpers import strikeout
import random


class VideoLibrary:
    """
    Ingests a CSV list of shows on instantiation and provides functionality to
    pull random shows from the list for particular category to play
    """

    categorised_show_list: dict
    service: str
    show: str
    showId: str

    def __init__(self, show_list):
        self.show_list = DictReader(open(show_list, mode="r"))
        self.all = {}
        self.watched = {}
        self.background = {}
        self.new = {}
        self.show_url = ""

        # Ingest show list and break it down by category on init
        for line in self.show_list:
            if line.get("Name").startswith("#") | line.get("Name").startswith("\n"):
                continue

            else:
                self.all.update(
                    ({line.get("Name").strip(): line.get("Show-URL").strip()})
                )

                if line.get("Category").strip() == "1":
                    self.watched.update(
                        {line.get("Name").strip(): line.get("Show-URL").strip()}
                    )

                elif line.get("Category").strip() == "2":
                    self.background.update(
                        {line.get("Name").strip(): line.get("Show-URL").strip()}
                    )

                elif line.get("Category").strip() == "3":
                    self.new.update(
                        {line.get("Name").strip(): line.get("Show-URL").strip()}
                    )

    def get_show(self, watch_mode):
        """
        For a given watchmode, grab a random show from the category
        and set the show and show url class attributes
        """

        if watch_mode == 1:
            self.categorised_show_list = self.watched
            self.show = random.choice(list(self.categorised_show_list.keys()))
            self.show_url = self.categorised_show_list.get(self.show)

        elif watch_mode == 2:
            self.categorised_show_list = {**self.watched, **self.background}
            self.show = random.choice(list(self.categorised_show_list.keys()))
            self.show_url = self.categorised_show_list.get(self.show)

        elif watch_mode == 3:
            self.categorised_show_list = self.new
            self.show = random.choice(list(self.new.keys()))
            self.show_url = self.new.get(self.show)

        elif watch_mode == 4:
            self.categorised_show_list = {**self.watched, **self.background, **self.new}
            self.show = random.choice(list(self.categorised_show_list.keys()))
            self.show_url = self.categorised_show_list.get(self.show)

        else:
            # self.categorised_show_list = {"How I Met Your Mother": "https://www.hulu.com/series/how-i-met-your-mother-bc68ac79-3ace-4427-9ec0-5ee6f314d194"}
            self.categorised_show_list = {
                "Avatar: The Last Airbender": "https://www.netflix.com/title/70142405"
            }
            # self.categorised_show_list = {"Battlestar Galactica", "https://www.amazon.com/gp/video/detail/B000UU2YKE"}
            self.show = random.choice(list(self.categorised_show_list.keys()))
            self.show_url = self.categorised_show_list.get(self.show)

        # Breakdown URL to grab streaming service and show ID in said service
        self.showId = self.show_url.split("/")[-1]
        self.service = self.show_url.split(".")[1]

    def get_whats_playing(self):
        whats_playing = (
            "\n"
            "Show: \n"
            f"{self.show}\n\n"
            "Service: \n"
            f"{self.service.capitalize()}"
        )
        return whats_playing

    # def print(self):
    #     for line in self.show_list:
    #         if line.get('Name').startswith('#'):
    #             print(strikeout(f"Name: {line.get('Name')}"))
    #         else:
    #             print(f"Name: {line.get('Name')}")
    #
    # def get_categories(self):
    #     return list(set([line.get("Category").strip() for line in self.show_list]))
