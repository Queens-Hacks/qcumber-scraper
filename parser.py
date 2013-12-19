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
            logging.warning("Not using {0} for parsing, using builtin parser instead".format(self._souplib))
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
            return None
        url = form.get("action")

        payload = {}
        for x in form.find_all("input", type="hidden"):
            payload[x.get("name")] = x.get("value")

        return dict(url=url, payload=payload)

    #------------------Get IDs/objects by index---------------------

    def _validate_link_id(self, link_id):
        """Returns the link_id and found tag if it's found, None otherwise."""

        tag = self.soup.find("a", {"id": link_id})
        if tag:
            # Found it on the page, valid id
            return link_id, tag

        # Link not on page, doesn't exist
        return None, None

    def subject_id_at_index(self, index, return_tag=False):
        """
        Returns the id of the subject at the index on the page.
        None if the subject doesn't exist.
        Returns the found tag as well as the id if `return_tag` is True.
        """
        # The general format of all the subject links
        link_format = "DERIVED_SSS_BCC_GROUP_BOX_1$84$${0}"

        if return_tag:
            return self._validate_link_id(link_format.format(index))
        else:
            return self._validate_link_id(link_format.format(index))[0]

    def subject_at_index(self, index):
        """
        Returns the title, abbreviation, and id of
        the subject at the specified index on the page
        """

        # Get the tag at the index
        link_id, tag = self.subject_id_at_index(index, return_tag=True)
        if not tag:
            return None

        # Extract the subject title and abbreviation
        m = re.search("^([^-]*) - (.*)$", tag.get_text().strip())
        if not m:
            logging.debug("Couldn't extract title and abbreviation from dropdown")
            return None

        subject_abbr = m.group(1)
        subject_title = m.group(2)

        return dict(title=subject_title, abbreviation=subject_abbr, action=link_id)

    def course_id_at_index(self, index):
        """
        Returns the id of the course at the specified index on the page.
        None if the course doesn't exist.
        """

        # General format of all course links
        link_format = "CRSE_TITLE${0}"

        return self._validate_link_id(link_format.format(index))[0]

    #---------------------------Counting------------------------

    def num_subjects(self):
        """Returns the number of subjects on the page"""
        cnt = 0
        while self.subject_id_at_index(cnt):
            cnt += 1
        return cnt

    def num_courses(self):
        """Returns the number of courses on the page"""
        cnt = 0
        while self.course_id_at_index(cnt):
            cnt += 1
        return cnt
