from pathlib import Path

import cherrypy

from libs import *
from libs.videoLibrary import VideoLibrary


class RandomFlixWeb(object):
    vl = VideoLibrary("./shows.csv")
    play_mode = "1"

    @cherrypy.expose
    def index(self):
        self.vl.get_show(int(self.play_mode))

        output = f"""
            <html>
                <head>
                    <title>RandomFlix</title>
                </head>
            
                <body>
                    <header>
                        <h1>RandomFlix Web</h1>
                    </header>
                    This is a test version of Randomflix<br>
                    Play Mode: {self.play_mode}<br>
                    Show: {self.vl.show}<br>
                    Service: {self.vl.service.capitalize()}<br>
                    URL: <a href='{self.vl.show_url}'>{self.vl.show_url}</a><br><br>
            
                    <form method="get" action="set_category">
                      <input type="text" value="" name="category" />
                      <button type="submit">Change Category</button>
                    </form>
                </body>
            </html>
            """

        # return f"<a href='{self.vl.show_url}'>{self.vl.show} - {self.vl.service}</a>"

        return output

    @cherrypy.expose
    def set_category(self, category: str):
        self.play_mode = category

        output = f"""
            <html>
                <body>
                    Category changed to {self.play_mode}<br><br>
                    <a href="http://127.0.0.1:8080/">Return Home</a>
                </body>
            </html>
        """

        return output


if __name__ == '__main__':
    cherrypy.quickstart(RandomFlixWeb(), '/')