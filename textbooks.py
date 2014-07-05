import requests
import re
import os
import json
from writer import out_path
from config import OUTPUT_DIR
from bs4 import BeautifulSoup

def write_textbook(subject, course, textbook):
    out = out_path('textbooks')

    isbn = textbook['isbn_13'] or textbook['isbn_10']
    filename = os.path.join(out, '{}.json'.format(isbn))

    course_id = '{} {}'.format(subject, course)

    if os.path.isfile(filename):
        # The file already exists, add this course
        with open(filename, 'r+t') as f:
            oldtextbook = json.loads(f.read())
            oldtextbook['courses'].append(course_id)
            f.seek(0)
            f.write(json.dumps(oldtextbook, indent=4, sort_keys=True))
    else:
        with open(os.path.join(out, '{}.json'.format(isbn)), 'w') as f:
            textbook['courses'] = [course_id]
            f.write(json.dumps(textbook, indent=4, sort_keys=True))

class TextbookScraper(object):

    def __init__(self, config):
        self.config = config

    def num_available(self, s):
        if s:
            m = re.search(r"\((\d+)", s)
            return int(m.group(1)) if m else 0
        else:
            return 0

    def price(self, s):
        if s:
            m = re.search(r"(\$\d+\.\d{2})", s)
            return m.group(1) if m else None
        else:
            return None

    def scrape(self):

        print("Starting textbook scrape")

        print("Getting a list of courses")
        r = requests.get("http://www.campusbookstore.com/Textbooks/Booklists/")

        print("Got list...")

        b = BeautifulSoup(r.text)
        content = b.find("div", {"class":"thecontent"})
        links  = content.find_all("a")

        temp = []

        for link in links:
            if "campusbookstore.com/Textbooks/Course/" in link.attrs.get("href", ""):
                m = re.search("^(\D+)(\d+).*$", link.string)
                # Only parse letters in config
                if m and m.group(1)[1].upper() in self.config['letters']:
                    temp.append((m.group(1), m.group(2), link.attrs["href"]))

        print("Parsing courses")
        for subject, course, link in temp:

            print('Book for {} {}'.format(subject, course))

            response = requests.get(link)
            b = BeautifulSoup(response.text)

            # Looking at the page source, 49 books seems to be the limit (numbers padded the 2 digits)
            for i in range (0, 99, 2):

                book_id = "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_ModeFull".format(i)

                book = b.find("div", {"id": book_id})
                if not book:
                    break

                temp = book.find("table").find("table").find_all("td")[1]

                textbook_attrs = {"listing_url": link + "#" + book_id}

                # Title
                title = temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_BookTitle".format(i)}).string
                textbook_attrs["title"] = title

                # Authors
                authors = temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_BookAuthor".format(i)}).string
                if authors and authors[:4] == " by ":
                    textbook_attrs["authors"] = authors[4:]

                # Required
                required = temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_StatusLabel".format(i)}).string
                if required and "REQUIRED" in required.upper():
                    textbook_attrs["required"] = True

                # ISBN 13
                isbn_13 = temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_ISBN13Label".format(i)}).string
                if isbn_13 and "[N/A]" in isbn_13:
                    textbook_attrs["isbn_13"] = None
                else:
                    textbook_attrs["isbn_13"] = isbn_13

                # ISBN 10
                isbn_10 = temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_ISBN10Label".format(i)}).string
                if isbn_10 and "[N/A]" in isbn_10:
                    textbook_attrs["isbn_10"] = None
                else:
                    textbook_attrs["isbn_10"] = isbn_10

                # New data
                new_price = self.price(temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_NewPriceLabel".format(i)}).string)
                new_available = self.num_available(temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_NewAvailabilityLabel".format(i)}).string)
                if new_price:
                    textbook_attrs["new_price"] = new_price
                if new_available:
                    textbook_attrs["new_available"] = new_available

                # Used data
                used_price = self.price(temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_UsedPriceLabel".format(i)}).string)
                used_available = self.num_available(temp.find("span", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_UsedAvailabilityLabel".format(i)}).string)
                if used_price:
                    textbook_attrs["used_price"] = used_price
                if used_available:
                    textbook_attrs["used_available"] = used_available

                # Classifieds info
                classified_info = temp.find("a", {"id": "ctl00_ContentBody_ctl00_CourseBooksRepeater_ctl{:02d}_test_ClassifiedsLabel".format(i)}).string
                if classified_info:
                    textbook_attrs["classified_info"] = classified_info

                # Add the textbook
                if textbook_attrs["isbn_10"] or textbook_attrs["isbn_13"]:

                    write_textbook(subject, course, textbook_attrs)
                    try:
                        print("----Parsed book: {title} by {authors} ({isbn_13})".format(**textbook_attrs))
                    except:
                        print("----Parsed book.")


if __name__ == '__main__':
    config = dict(
        letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    )
    scraper = TextbookScraper(config)
    scraper.scrape()
