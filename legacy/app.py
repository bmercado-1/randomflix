from flask import Flask
from flask import render_template
from markupsafe import escape

from libs import *
from libs.videoLibrary import VideoLibrary

app = Flask(__name__)


vl = VideoLibrary("./shows.csv")
play_mode = "1"

@app.route('/')
def index():
    vl.get_show(int(play_mode))

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
                        Play Mode: {play_mode}<br>
                        Show: {vl.show}<br>
                        Service: {vl.service.capitalize()}<br>
                        URL: <a href='{vl.show_url}'>{vl.show_url}</a><br><br>

                        <form method="get" action="set_category">
                          <input type="text" value="" name="category" />
                          <button type="submit">Change Category</button>
                        </form>
                    </body>
                </html>
                """

    return output
@app.route('/set_category')
def set_category(category: str):
    play_mode = category

    output = f"""
        <html>
            <body>
                Category changed to {play_mode}<br><br>
                <a href="http://127.0.0.1:8080/">Return Home</a>
            </body>
        </html>
    """

    return output


if __name__ == '__main__':
    app.run()
