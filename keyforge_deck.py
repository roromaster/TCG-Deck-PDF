#!/usr/bin/env python3
# coding: utf-8

import tempfile
import os
from multiprocessing import Pool
import glob
import urllib.request
import subprocess
import html.parser
from functools import partial


# TODO: accept as parameter
URL_EXAMPLE = "https://www.keyforgegame.com/deck-details/4608a62e-71b4-4e61-8093-fff5bf402c76"


# TODO: Select Expansion from Deck list
CARDS_PATH = "./cards/fr/Age of Ascension"
#CARDS_PATH = "./cards/fr/Call of the Archons"


CONVERT_PATH = '/usr/local/bin/convert'
OUTPUT_FILE =  "./result.pdf"
JPEG_QUALITY = "94"


FILE_PATTERN = "[0-9][0-9][0-9]*"
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) ' +
    'AppleWebKit/537.36 (KHTML, like Gecko) ' +
    'Chrome/35.0.1916.47 Safari/537.36'
)


class HTMLParser(html.parser.HTMLParser):
    def __init__(self):
        super(HTMLParser, self).__init__()
        self.cards = []

    def handle_starttag(self, tag, attrs):
        NUMBER_CLASS = "card-table__deck-card-number"
        self.in_card_number_span = (
            (tag == 'span') and
            ("class", NUMBER_CLASS) in attrs
        )

    def handle_endtag(self, tag):
        if self.in_card_number_span and tag == 'span':
            self.in_card_number_span = False

    def handle_data(self, data):
        if self.in_card_number_span:
            self.cards.append(int(data))


def rm(fname):
    os.remove(fname)


def __run(*args):
    try:
        subprocess.check_output(args, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(e.output)
        raise


def convert(*params):
    __run(CONVERT_PATH, *params)


def load_image_map():
    images = {}
    for fname in glob.glob(os.path.join(CARDS_PATH, FILE_PATTERN)):
        fid = os.path.basename(fname)[:3]
        images[int(fid)] = fname
    return images


def get_deck_page(url):
    req = urllib.request.Request(
        url,
        data=None,
        headers={ 'User-Agent': USER_AGENT }
    )
    return urllib.request.urlopen(req).read().decode('utf-8')


def get_card_list(text):
    parser = HTMLParser()
    parser.feed(text)
    return parser.cards


def get_temp_fname(suffix=".png"):
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        return f.name


def build_page( page_cards):
    assert len(page_cards) == 9, "Page should contain 9 cards"

    A4_SIZE = "2480x3508"
    BORDERED_SIZE = "2274x3174-12-12"
    cs = page_cards
    fname = get_temp_fname(".jpg")
    convert(*[
        "(",
            "(",
                "(", cs[0], cs[1], cs[2], "+append", ")",
                "(", cs[3], cs[4], cs[5], "+append", ")",
                "(", cs[6], cs[7], cs[8], "+append", ")",
                "-append",
            ")",
            "+repage",
        ")",
        "-quality", JPEG_QUALITY,
        "-bordercolor", "white",
        "-border", "30",
        fname
    ])
    return fname


def build_pdf(card_list):
    assert len(card_list) == 72, "Deck should consist of 36 cards"
    fs = []
    # TODO: add card backs
    with Pool() as p:
        fs = list(p.map(
            partial(build_page),
            zip(*[iter(card_list)]*9)
        ))
    convert(*(fs  + [OUTPUT_FILE]))
    for f in fs:
        rm(f)


def main():
    # TODO: add logging
    image_map = load_image_map()
    html = get_deck_page(URL_EXAMPLE)
    deck = get_card_list(html)
    deck_images = list(map(lambda it: image_map[it], deck))

    #Let's add back of the cards now :)
    back = "./keyforge_back.png"
    index = 9
    for i in range(4):
        for j in range(9):
            deck_images.insert(index,back)
        index = index + 2*9

    build_pdf(deck_images)


if __name__ == "__main__":
    main()
