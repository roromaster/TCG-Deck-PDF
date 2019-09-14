#!/usr/bin/env python3
# coding: utf-8

import tempfile
import os
from multiprocessing import Pool
import glob
import urllib.request
import subprocess
import html.parser
from selenium import webdriver
from functools import partial
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time
from PIL import Image, ImageDraw, ImageFont
import textwrap
from fake_useragent import UserAgent



# TODO: accept as parameter
URL_EXAMPLE = "http://www.keyforgegame.com/deck-details/b5eab6c5-b5c6-49d2-93bd-b807377de1ba"


# TODO: Select Expansion from Deck list
CARDS_PATH = "./cards/fr/Age of Ascension"
#CARDS_PATH = "./cards/fr/Call of the Archons"


CONVERT_PATH = '/usr/local/bin/convert'
OUTPUT_FILE =  "./result.pdf"
JPEG_QUALITY = "94"


FILE_PATTERN = "[0-9][0-9][0-9]*"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64;)"

DECK_NAME = "result.pdf"

FILE_TO_CLEAN = []

class HTMLParser(html.parser.HTMLParser):
    def __init__(self):
        super(HTMLParser, self).__init__()
        self.cards = []
        self.deckname = ""
        self.in_deckname = False
        self.in_expansion = False
        self.expansion = ""

    def handle_starttag(self, tag, attrs):
        NUMBER_CLASS = "card-table__deck-card-number"
        self.in_card_number_span = (
            (tag == 'span') and
            ("class", NUMBER_CLASS) in attrs
        )
        NUMBER_CLASS = "deck-details__deck-name keyforge-heading-1"
        self.in_deckname = (
            (tag == 'h1') and
            ("class", NUMBER_CLASS) in attrs
        )
        NUMBER_CLASS = "deck-details__deck-expansion"
        self.in_expansion = (
            (tag == 'div') and
            ("class", NUMBER_CLASS) in attrs
        )


    def handle_endtag(self, tag):
        if self.in_card_number_span and tag == 'span':
            self.in_card_number_span = False
        if self.in_deckname and tag == 'h1':
            self.in_deckname = False
        if self.in_expansion and tag == 'div':
            self.in_expansion = False


    def handle_data(self, data):
        if self.in_card_number_span:
            self.cards.append(int(data))

        if self.in_deckname:
            self.deckname = data

        if self.in_expansion:
            self.expansion = data




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
    global OUTPUT_FILE
    global DECK_NAME
    parser = HTMLParser()
    parser.feed(text)
    OUTPUT_FILE = parser.deckname + ".pdf"
    DECK_NAME = parser.deckname
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
                "(", print_deckName(cs[0],fname + '0'), print_deckName(cs[1],fname + '1'), print_deckName(cs[2],fname + '2'), "+append", ")",
                "(", print_deckName(cs[3],fname + '3'), print_deckName(cs[4],fname + '4'), print_deckName(cs[5],fname + '5'), "+append", ")",
                "(", print_deckName(cs[6],fname + '6'), print_deckName(cs[7],fname + '7'), print_deckName(cs[8],fname + '8'), "+append", ")",
                "-append",
            ")",
            "+repage",
        ")",
        "-quality", JPEG_QUALITY,
        "-bordercolor", "white",
        "-border", "30",
        fname
    ])
    global FILE_TO_CLEAN
    for elmt in FILE_TO_CLEAN:
        print("Deleting: " + elmt)
        rm(elmt)
    FILE_TO_CLEAN = []
    return fname


def build_pdf(card_list):
    assert len(card_list) == 72, "Deck should consist of 36 cards"
    print(card_list)
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

def print_deckName(card, index):
    para = textwrap.wrap(DECK_NAME, width=30)
    global FILE_TO_CLEAN

    if 'keyforge_back_name.png' in card:
        return card

    MAX_W, MAX_H = 50, 50
    # create Image object with the input image
    image = Image.open(card)
    name = index +'.png'

    # initialise the drawing context with
    # the image object as background
    draw = ImageDraw.Draw(image)
    color = 'rgb(255, 255, 255)' # white color
    font = ImageFont.truetype('Geneva.dfont', size=10)

    current_h, pad = 385, 0
    for line in para:
        w, h = draw.textsize(line, font=font)
        draw.text((133, current_h), line,fill=color, font=font)
        current_h += h + pad
    image.save(name)
    FILE_TO_CLEAN.append(name)

    return name


def build_cardback():
    para = textwrap.wrap(DECK_NAME, width=30)

    MAX_W, MAX_H = 300, 50
    # create Image object with the input image
    image = Image.open('./keyforge_back.png')

    # initialise the drawing context with
    # the image object as background
    draw = ImageDraw.Draw(image)
    color = 'rgb(255, 255, 255)' # white color
    font = ImageFont.truetype('Geneva.dfont', size=12)

    current_h, pad = 388, 0
    for line in para:
        w, h = draw.textsize(line, font=font)
        draw.text(((MAX_W - w) / 2, current_h), line,fill=color, font=font)
        current_h += h + pad

    # save the edited image

    image.save('keyforge_back_name.png')

def main():
    # TODO: add logging
    global FILE_TO_CLEAN
    image_map = load_image_map()

    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1200x600')
    ua = UserAgent()
    userAgent = ua.safari
    print(userAgent)
    options.add_argument(f'user-agent={userAgent}')
    driver = webdriver.Chrome(chrome_options=options)


    driver.get(URL_EXAMPLE)
#    html = get_deck_page(URL_EXAMPLE)
    html = driver.page_source
    deck = get_card_list(html)
    deck_images = list(map(lambda it: image_map[it], deck))

    build_cardback()
    back = "./keyforge_back_name.png"
    index = 9
    for i in range(4):
        for j in range(9):
            deck_images.insert(index,back)
        index = index + 2*9

    build_pdf(deck_images)


if __name__ == "__main__":
    main()
