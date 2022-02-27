import functools
import logging
import random
from time import time

import matplotlib.pyplot as plt
import numpy as np
import panel as pn
import param
from neo4j import GraphDatabase

from yourtube.file_operations import load_graph_from_neo4j
from yourtube.html_components import (
    MaterialButton,
    MaterialSwitch,
    VideoGrid,
    required_modules,
)
from yourtube.recommendation import Engine

logger = logging.getLogger("yourtube")
logger.setLevel(logging.DEBUG)

plt.style.use("dark_background")

# pn.extension doesn't support loading
pn.extension(
    # js_files={
    #     'mdc': 'https://unpkg.com/material-components-web@latest/dist/material-components-web.min.js',
    #     "vue": "https://cdn.jsdelivr.net/npm/vue@2.x/dist/vue.js",
    #     "vuetify": "https://cdn.jsdelivr.net/npm/vuetify@2.x/dist/vuetify.js",
    # },
    # css_files=[
    #     'https://unpkg.com/material-components-web@latest/dist/material-components-web.min.css',
    #     "https://fonts.googleapis.com/icon?family=Material+Icons",
    #     "https://cdn.jsdelivr.net/npm/@mdi/font@6.x/css/materialdesignicons.min.css",
    #     "https://cdn.jsdelivr.net/npm/vuetify@2.x/dist/vuetify.min.css",
    #     "https://fonts.googleapis.com/css?family=Roboto:100,300,400,500,700,900",
    # ],
)
# pn.extension(template='vanilla')
# pn.extension(template='material', theme='dark')
# pn.extension('ipywidgets')


class UI:
    info_template = '<div id="message_output" style="width:400px;">{}</div>'

    def __init__(
        self,
        engine,
        parameters,
    ):

        self.engine = engine
        self.num_of_groups = parameters.num_of_groups
        self.videos_in_group = parameters.videos_in_group
        self.column_width = parameters.column_width

        self.grid_gap = 20
        self.row_height = self.column_width * 1.0

        self.image_output = pn.pane.PNG()
        self.message_output = pn.pane.HTML("")

        self.exploration_slider = pn.widgets.FloatSlider(
            name="Exploration", start=0, end=1, step=0.01, value=0.1
        )

        # define UI controls
        go_back_button = MaterialButton(
            label="Go back",
            style="width: 110px",
        )
        go_back_button.on_click = self.go_back

        self.hide_watched_checkbox = MaterialSwitch(initial_value=False, width=40)
        self.hide_watched_checkbox.on_event("switch_id", "click", self.update_displayed_videos)

        refresh_button = MaterialButton(
            label="Refresh",
            style="width: 110px",
        )
        refresh_button.on_click = self.update_displayed_videos

        top = pn.Row(
            go_back_button,
            pn.Spacer(width=20),
            self.hide_watched_checkbox,
            pn.pane.HTML("Hide watched videos"),
            self.exploration_slider,
            refresh_button,
            required_modules,
        )

        # conscruct group choice buttons
        button_height = self.column_width * 9 // 16
        style = f"height: {button_height}px; width: 60px"
        label = "➤"
        button_gap = int(self.row_height - button_height)
        self.choice_buttons = []
        button_box = pn.Column()
        for i in range(self.num_of_groups):
            button = MaterialButton(label=label, style=style)
            # bind this button to its column choice
            button.on_click = functools.partial(self.choose_column, i=i)

            self.choice_buttons.append(button)
            # construct button box
            button_box.append(button)
            button_box.append(pn.Spacer(height=button_gap))
        # pop the last spacer
        button_box.pop(-1)

        num_of_columns = self.videos_in_group
        self.video_wall = VideoGrid(
            self.num_of_groups * self.videos_in_group,
            num_of_columns,
            self.column_width,
            self.row_height,
            self.grid_gap,
        )

        self.whole_output = pn.Column(
            self.image_output,
            top,
            self.message_output,
            pn.Spacer(height=5),
            # adding spacer with a width 0 gives a correct gap for some reason
            pn.Row(button_box, pn.Spacer(width=0), self.video_wall),
        )

        if parameters.show_dendrogram:
            # image can be None
            if self.engine.dendrogram_img is None:
                print("cannot display image: no image in cache")
            else:
                self.image_output.object = self.engine.dendrogram_img

        self.update_displayed_videos()

    def get_recommendation_parameters(self):
        return dict(
            hide_watched=self.hide_watched_checkbox.value,
            exploration=self.exploration_slider.value,
        )
    
    # def deactivate(self):
    #     top = self.whole_output[1]
    #     go_back_button = top[0]
    #     refresh_button = top[5]
    #     button_box = self.whole_output[-1][0]
    #     go_back_button.on_click = lambda _event: None
    #     self.hide_watched_checkbox.on_event("switch_id", "click", lambda _w, _e, _d: None)
    #     refresh_button.on_click = lambda _event: None
    #     for button in button_box[::2]:
    #         button.on_click = lambda _event: None


    def display_video_grid(self):
        ids = self.engine.get_video_ids(self.get_recommendation_parameters())
        ids = np.array(ids).flatten()

        texts = []
        for i, id_ in enumerate(ids):
            if id_ == "" or self.engine.is_video_down(id_):
                # it's "" if its cluster turned out empty after filtering
                # it can also be down
                ids[i] = "RqJVa0fl01w"  # confused Travolta
                texts.append("-")
                continue
            # logger.debug(id_)
            title = self.engine.get_video_title(id_)
            # TODO refine and show video info
            # rank = self.recommender.node_ranks.get(id_)
            # likes_to_views = liked_to_views_ratio(self.G, id_)
            # likes_to_views = int(likes_to_views * 1000)
            # info = f"rank: {rank}   l/v: {likes_to_views}"
            # text = f"{info}<br>{title}"
            text = title
            texts.append(text)

        self.video_wall.ids = list(ids)
        self.video_wall.texts = texts
        self.video_wall.update()
        print(texts)

    def choose_column(self, _change, i):
        exit_code = self.engine.choose_column(i)
        self.message_output.object = self.info_template.format(self.engine.get_branch_id())

        if exit_code == -1:
            self.message_output.object = self.info_template.format("already on the lowest cluster")
            return

        self.update_displayed_videos()

    def go_back(self, _event):
        exit_code = self.engine.go_back()
        self.message_output.object = self.info_template.format(self.engine.get_branch_id())

        if exit_code == -1:
            self.message_output.object = self.info_template.format("already on the highest cluster")
            return

        self.update_displayed_videos()

    def update_displayed_videos(self, _widget=None, _event=None, _data=None):
        self.display_video_grid()
        self.engine.fetch_videos(self.get_recommendation_parameters())


#######################################################################################

driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "yourtube"))

start_time = time()
G = load_graph_from_neo4j(driver, user="default")
logger.info(f"loading graph took: {time() - start_time:.3f} seconds")


class Parameters(param.Parameterized):
    seed = param.Integer()
    clustering_balance_a = param.Number(1.5, bounds=(1, 2.5), step=0.1)
    clustering_balance_b = param.Number(1, bounds=(1, 2.5), step=0.1)
    num_of_groups = param.Integer(3, bounds=(2, 10), step=1)
    videos_in_group = param.Integer(5, bounds=(1, 10), step=1)
    show_dendrogram = param.Boolean(False)
    column_width = param.Integer(260, bounds=(100, 500), step=10)


parameters = Parameters(seed=random.randint(1, 1000000))

# # only sane templates are FastListTemplate and VanillaTemplate and MaterialTemplate
template = pn.template.MaterialTemplate(title="YourTube", theme=pn.template.DarkTheme)

engine = Engine(G, driver, parameters)
ui = UI(engine, parameters)
engine.display_callback = ui.display_video_grid
ui_wrapper = pn.Row(ui.whole_output)
template.main.append(ui_wrapper)


def refresh(_event):
    # it looks that it needs to be global, so that ui gets dereferenced, and can disappear
    # otherwise it is still bound to the new panel buttons, probably due to some panel quirk
    # and this causes each click to be executed double
    global ui, engine
    logger.info("refreshed")
    template.main[0][0] = pn.Spacer()

    engine = Engine(G, driver, parameters)
    ui = UI(engine, parameters)
    engine.display_callback = ui.display_video_grid

    template.main[0][0] = ui.whole_output


refresh_button = pn.widgets.Button(name="Refresh")
refresh_button.on_click(refresh)

template.sidebar.append(parameters)
template.sidebar.append(refresh_button)
template.servable()
