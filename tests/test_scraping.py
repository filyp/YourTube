import networkx as nx
from time import time

from yourtube.scraping import scrape_from_list, get_content, get_title
import re

id_ = "dQw4w9WgXcQ"
G = nx.DiGraph()


def test_test():
    content = get_content(id_)

    candidates = re.findall(
        r'{"iconType":"LIKE"},"defaultText":{"accessibility":{"accessibilityData":{"label":"(.*?)"',
        content.text,
    )
    candidates = set(candidates)
    assert len(candidates) <= 1
    if candidates:
        like_string = candidates.pop()
    else:
        # likes are probably disabled
        return None
    print(like_string)
    like_string = like_string.replace("\xa0", "")
    print(like_string)
    like_count = re.findall(r"[0-9]+", like_string)
    print(like_count)


def test_scraping():
    scrape_from_list([id_], G, non_verbose=True)


def test_scraping_title():
    assert (
        G.nodes[id_]["title"]
        == "Rick Astley - Never Gonna Give You Up (Official Music Video)"
    )


def test_scraping_view_count():
    assert G.nodes[id_]["view_count"] > 1001659175


def test_scraping_like_count():
    assert G.nodes[id_]["like_count"] > 10792474


def test_scraping_channel_id():
    assert G.nodes[id_]["channel_id"] == "UCuAXFkgsw1L7xaCfnd5JJOw"


def test_scraping_time_scraped():
    assert time() - 3600 < G.nodes[id_]["time_scraped"] < time()


def test_title_special_chars():
    content = get_content("gmxSGVQEXuc")
    title = get_title(content)
    assert title == """test"&ŒœŠšŸˆ˜   –—‘’‚“”„†‡‰‹›€~!@#$%^&*()_+[]{};'\\:"|,./?"""
