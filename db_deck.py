#!/usr/bin/env python3
# coding: utf-8

import tempfile
import os
from multiprocessing import Pool
import glob
import urllib
import urllib.request
import subprocess
import html.parser
import re
from functools import partial


# TODO: accept as parameter
URL_EXAMPLE = "https://www.cardgame.fr/dbs/decks/export/10980"

CARDS_PATH = "./cards/fr/Dragon Ball Card Game/"
CONVERT_PATH = '/usr/local/bin/convert'
OUTPUT_FILE =  "./result.pdf"
JPEG_QUALITY = "94"


FILE_PATTERN = "[0-9][0-9][0-9]*"
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) ' +
    'AppleWebKit/537.36 (KHTML, like Gecko) ' +
    'Chrome/35.0.1916.47 Safari/537.36'
)
DEFAULT_CROP_MARK_LENGTH = 24
DEFAULT_CROP_MARK_WIDTH = 2


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


def build_page(crop_marks_file, page_cards):
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


def build_page_original(crop_marks_file, page_cards):
    assert len(page_cards) == 9, "Page should contain 9 cards"

    A4_SIZE = "2480x3508"
    BORDERED_SIZE = "2274x3174-12-12"
    cs = page_cards
    fname = get_temp_fname(".jpg")
    convert(*[
        "-size", A4_SIZE, "xc:white",
        "(",
            "(",
                "(", cs[0], cs[1], cs[2], "+append", ")",
                "(", cs[3], cs[4], cs[5], "+append", ")",
                "(", cs[6], cs[7], cs[8], "+append", ")",
                "-append",
            ")",
            "(",
                "-clone", "0",
                "-set", "option:distort:viewport", BORDERED_SIZE,
                "-virtual-pixel", "mirror",
                "-distort", "SRT", "0,0 1,1 0",
            ")",
            "(", "-clone", "0", ")",
            "-delete", "0",
            "-gravity", "center",
            "-compose", "over",
            "-composite",
            "+repage",
        ")",
        "-gravity", "center",
        "-composite",
        "-quality", JPEG_QUALITY,
        fname
    ])
    return fname

def build_crop_marks(w, h):
    l = DEFAULT_CROP_MARK_LENGTH
    crop_file_name = get_temp_fname()
    convert(
        "(",
            "-size", f"{w}x{h}",
            "xc:none",
            "-fill", "red",
            "-strokewidth", str(DEFAULT_CROP_MARK_WIDTH),
            "-draw", (
                f"line 0,0 0,{l} " +
                f"line 0,0 {l},0 " +
                f"line 0,{h - 1} 0,{h - l} " +
                f"line 0,{h - 1} {l},{h - 1} " +
                f"line {w - 1},0 {w - 1},{l} " +
                f"line {w - 1},0 {w - l},0 " +
                f"line {w - 1},{h - 1} {w - l},{h - 1} " +
                f"line {w - 1},{h - 1} {w - 1},{h - l}"
            ),
        ")",
        "-duplicate", "2", "+append",
        "-duplicate", "2", "-append",
        "+repage",
        crop_file_name
    )
    return crop_file_name


def build_pdf(card_list):
    assert len(card_list) == 108, "Deck should consist of 54 cards"
    crop_marks_file = build_crop_marks(750, 1050)
    fs = []
    # TODO: add card backs
    with Pool() as p:
        fs = list(p.map(
            partial(build_page, crop_marks_file),
            zip(*[iter(card_list)]*9)
        ))
    convert(*(fs  + [OUTPUT_FILE]))
    for f in fs:
        rm(f)
    rm(crop_marks_file)


def main():
    html = get_deck_page(URL_EXAMPLE)
    #deck = get_card_list(html)
    lines = html.split('\n')
    leader = lines[1]
    card_list = lines[4:]
    regex = r"\(([^\)]+)\)" #Search for Card # ID

    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', USER_AGENT)]
    urllib.request.install_opener(opener)


    if not os.path.exists(CARDS_PATH): #if the folder doesn't exist, create it
        os.makedirs(CARDS_PATH)

    image_list = []

    #Let's process the leader cards
    leader_card_id = re.search(regex, leader)
    if leader_card_id:
        leader_card_id = leader_card_id.group(1)
        # Download if file does not exist
        if not(os.path.exists(CARDS_PATH + leader_card_id + "LF.png")):
            print("Downloading ... " + leader_card_id)
            url = "https://static.cardgame.fr/images/cards_medium/" + leader_card_id +"LF.png"
            filedata = urllib.request.urlretrieve(url,CARDS_PATH + leader_card_id + "LF.png")
            url = "https://static.cardgame.fr/images/cards_medium/" + leader_card_id +"LB.png"
            filedata = urllib.request.urlretrieve(url,CARDS_PATH + leader_card_id + "LB.png")
        else:
            print ("File " + leader_card_id + " allready there")
        image_list.append(CARDS_PATH + leader_card_id + "LF.png")
        image_list.append(CARDS_PATH + leader_card_id + "LB.png")





    for cards in card_list:
        if (cards):
            num = int(cards[0])
        result = re.search(regex, cards)
        if result:
            result = result.group(1)
            card_id = result
            # Download if file does not exist
            if not(os.path.exists(CARDS_PATH + card_id + ".png")):
                print("Downloading ... " + card_id)
                url = "https://static.cardgame.fr/images/cards_medium/" + result +".png"
                print(url)
                filedata = urllib.request.urlretrieve(url,CARDS_PATH + card_id + ".png")
            else:
                print ("File " + card_id + " allready there")

            result = "https://static.cardgame.fr/images/cards_medium/" + result +".png"
            for i in range(num):
                image_list.append(CARDS_PATH + card_id + ".png")
    #Let's add some blank card to fill in the gap.

    # We add blank image
    for i in range(2):
        image_list.append( "./blank.png")

    #Let's add back of the cards now :)
    back = "./DBS_Card_Back.jpg"
    index = 9
    for i in range(6):
        for j in range(9):
            image_list.insert(index,back)
        index = index + 2*9

    build_pdf(image_list)

if __name__ == "__main__":
    main()
