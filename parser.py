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
        m = re.search("^([^-]*) - (.*)$", self._clean_html(tag.get_text()))
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
        links = self.soup.find_all(id=re.compile("DERIVED_SSS_BCC_GROUP_BOX_1\$84\$\$[0-9]+"))
        # TODO if needed: Check if ID numbers are continuous
        return len(links)

    def num_courses(self):
        """Returns the number of courses on the page"""
        links = self.soup.find_all(id=re.compile("CRSE_TITLE\$[0-9]+"))
        # TODO if needed: Check if ID numbers are continuous
        return len(links)

    #-------------------------General-------------------------------

    def _clean_html(self, text):
        return text.replace('&nbsp;',' ').strip()

    #-----------------------Course info-----------------------------

    def course_info(self):
        """Parses the course attributes out of the page"""

        TITLE_CSS_CLASS = "PALEVEL0SECONDARY"
        INFO_TABLE_CSS_CLASS = "SSSGROUPBOXLTBLUEWBO"
        INFO_BOX_CSS_CLASS = "PSGROUPBOXNBO"
        INFO_BOX_HEADER_CSS_CLASS = "SSSGROUPBOXLTBLUE"
        DESCRIPTION_CSS_CLASS = "PSLONGEDITBOX"

        EDITBOX_LABEL = "PSEDITBOXLABEL"
        EDITBOX_DATA = "PSEDITBOX_DISPONLY"
        DROPDOWN_LABEL = "PSDROPDOWNLABEL"
        DROPDOWN_DATA = "PSDROPDOWNLIST_DISPONLY"

        DESCRIPTION = "Description"
        COURSE_DETAIL = "Course Detail"
        COURSE_COMPS = "Course Components"
        ENROLL_INFO = "Enrollment Information"
        CEAB = "CEAB Units"

        KEYMAP = {
                "Career": "career",
                "Typically Offered": "typically_offered",
                "Units": "units",
                "Grading Basis": "grading_basis",
                "Add Consent": "add_consent",
                "Drop Consent": "drop_consent",
                "Course Components": "course_components",
                "Enrollment Requirement": "enrollment_requirement",
        }

        attrs = {'extra': {"CEAB": {}}}

        # Get the title and number
        title = self.soup.find("span", {"class": TITLE_CSS_CLASS})
        if not title:
            raise Exception("Could not find the course title to parse")

        temp = self._clean_html(title.string)
        m = re.search('^([\S]+)\s+([\S]+)\s+-\s+(.*)$', temp)
        if not m:
            raise Exception("Title found ({0}) didn't match regular expression".format(temp))

        attrs['basic'] = {
            'title' : m.group(3),
            'number' : m.group(2),
            'description' : "",
        }

        # Blue table with info, enrollment, and description
        info_table = self.soup.find("table", {"class": INFO_TABLE_CSS_CLASS})

        # Look through inner tables
        info_boxes = self.soup.find_all("table", {"class": INFO_BOX_CSS_CLASS})
        for table in info_boxes:

            # Get the table type
            temp = table.find("td", {"class": INFO_BOX_HEADER_CSS_CLASS})
            if not temp or not temp.string:
                # Nothing there
                continue

            box_title = temp.string

            # Process the description box
            if box_title == DESCRIPTION:
                desc_list = table.find("span", {"class": DESCRIPTION_CSS_CLASS}).contents
                if desc_list:
                    # If not x.string, it means it's a <br/> Tag
                    attrs['basic']['description'] = "\n".join([x for x in desc_list if x.string])

            # Process the course details and enrollment info
            elif box_title in (COURSE_DETAIL, ENROLL_INFO):

                # Labels and values for "Add/Drop Consent" (enroll), "Career" (course), and "Grading Basis" (course)
                labels = table.find_all("label", {"class": DROPDOWN_LABEL})
                data = table.find_all("span", {"class": DROPDOWN_DATA})

                if box_title == ENROLL_INFO:
                    # Labels and values for "Typically Offered", "Enrollment Requirement",
                    labels += table.find_all("label", {"class": EDITBOX_LABEL})
                    data += table.find_all("span", {"class": EDITBOX_DATA})

                # Add all the type -> value mappings to the attrs dict
                for x in range(0, len(labels)):
                    if labels[x].string in KEYMAP:
                        attrs['extra'][KEYMAP[labels[x].string]] = data[x].get_text()

                # Special case for course detail, "Units" and "Course Components"
                if box_title == COURSE_DETAIL:
                    # Units and course components
                    labels = table.find_all("label", {"class": EDITBOX_LABEL})
                    data = table.find_all("span", {"class": EDITBOX_DATA})
                    for x in range(0, len(labels)):
                        if labels[x].string == COURSE_COMPS:
                            # Last datafield, has multiple type -> value mappings
                            comp_map = {}
                            for i in range(x, len(data), 2):
                                comp_map[data[i].string] = data[i+1].get_text()

                            attrs['extra'][KEYMAP[labels[x].string]] = comp_map
                            break
                        elif labels[x].string in KEYMAP:
                            attrs['extra'][KEYMAP[labels[x].string]] = data[x].get_text()

            # Process the CEAB information
            elif box_title == CEAB:

                labels = table.find_all("label", {"class": EDITBOX_LABEL})
                data = table.find_all("span", {"class": EDITBOX_DATA})

                for x in range(0, len(labels)):
                    # Clean up the data
                    temp = self._clean_html(data[x].string)

                    # Add the data to the dict if it exists
                    if labels[x].string and temp:
                        # Remove the last character of the label to remove the ":"
                        attrs['extra']['CEAB'][labels[x].string[:-1]] = temp

            else:
                raise Exception('Encountered unexpected info_box with title: "{0}"'.format(box_title))

        return attrs
