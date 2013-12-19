import re
import bs4
from datetime import datetime

class SolusParser(object):
    """Parses SOLUS's crappy HTML"""

    def __init__(self):
        self.soup = None
        self._souplib = 'lxml'

        # Prefer lxml, fall back to built in parser
        try:
            bs4.BeautifulSoup("", self._souplib)
        except bs4.FeatureNotFound as e:
            logging.warning("Not using {} for parsing, using builtin parser instead".format(self._souplib))
            self._souplib = "html.parser"

    def update_html(self, text):
        """Feed new data to the parser"""
        self.soup = bs4.BeautifulSoup(text, self._souplib)

    #-----------------------Logins----------------------------

    def login_solus_link(self):
        """Return the href of the SOLUS link"""
        link = self.soup.find("a", text="SOLUS")
        if not link:
            return None
        else:
            return link.get("href")

    def login_continue_page(self):
        """Return the url and payload to post from the continue page"""

        #Grab the RelayState, SAMLResponse, and POST url
        form = self.soup.find("form")
        if not form:
            # No form, nothing to be done
            return None, None
        url = form.get("action")

        payload = {}
        for x in form.find_all("input", type="hidden"):
            payload[x.get("name")] = x.get("value")

        return url, payload
