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

    #------------------Get IDs by index--------------------------

    def _validate_id(self, link_id, tag_type="a"):
        """Returns the link_id and found tag if it's found, None otherwise."""

        tag = self.soup.find(tag_type, {"id": link_id})
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
            return self._validate_id(link_format.format(index))
        else:
            return self._validate_id(link_format.format(index))[0]

    def course_id_at_index(self, index):
        """
        Returns the id of the course at the specified index on the page.
        None if the course doesn't exist.
        """

        # General format of all course links
        link_format = "CRSE_TITLE${0}"

        return self._validate_id(link_format.format(index))[0]

    def section_id_at_index(self, index, return_tag=False):
        """
        Returns the id of the section at the specified index on the page.
        None if it doesn't exist.
        """

        # General format of all section links
        link_format = "CLASS_SECTION${0}"

        if return_tag:
            return self._validate_id(link_format.format(index))
        else:
            return self._validate_id(link_format.format(index))[0]

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

    def num_sections(self):
        """Returns the number of sections on the page"""
        links = self.soup.find_all(id=re.compile("CLASS_SECTION\$[0-9]+"))
        # TODO if needed: Check if ID numbers are continuous
        return len(links)

    #-------------------------General-------------------------------

    def _clean_html(self, text):
        return text.replace('&nbsp;',' ').strip()

    #----------------------Subject info-----------------------------

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


    #-----------------------Course info-----------------------------

    def course_attrs(self):
        """Parses the course attributes out of the page

        Return format:

        {
            'basic':{
                'title': course title,
                'number': course number,
                'description: course description,
            }
            'extra':{
                # All keys in `KEYMAP` are valid in here (direct mapping)
                # course_components is a special case
                'course_components':{
                    # Example
                    'Lecture': 'Required',
                }
                "CEAB":{
                    # Example
                    'Math': '30',
                }
            }
        }
        """

        TITLE_CLASS = "PALEVEL0SECONDARY"
        INFO_TABLE_CLASS = "SSSGROUPBOXLTBLUEWBO"
        INFO_BOX_CLASS = "PSGROUPBOXNBO"
        INFO_BOX_HEADER_CLASS = "SSSGROUPBOXLTBLUE"
        DESCRIPTION_CLASS = "PSLONGEDITBOX"

        EDITBOX_LABEL_CLASS = "PSEDITBOXLABEL"
        EDITBOX_DATA_CLASS = "PSEDITBOX_DISPONLY"
        DROPDOWN_LABEL_CLASS = "PSDROPDOWNLABEL"
        DROPDOWN_DATA_CLASS = "PSDROPDOWNLIST_DISPONLY"

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

        ret = {
            'extra':{
                'CEAB':{}
            }
        }

        # Get the title and number
        title = self.soup.find("span", {"class": TITLE_CLASS})
        if not title:
            raise Exception("Could not find the course title to parse")

        temp = self._clean_html(title.string)
        m = re.search('^([\S]+)\s+([\S]+)\s+-\s+(.*)$', temp)
        if not m:
            raise Exception("Title found ({0}) didn't match regular expression".format(temp))

        ret['basic'] = {
            'title' : m.group(3),
            'number' : m.group(2),
            'description' : ""
        }

        # Blue table with info, enrollment, and description
        info_table = self.soup.find("table", {"class": INFO_TABLE_CLASS})

        # Look through inner tables
        info_boxes = self.soup.find_all("table", {"class": INFO_BOX_CLASS})
        for table in info_boxes:

            # Get the table type
            temp = table.find("td", {"class": INFO_BOX_HEADER_CLASS})
            if not temp or not temp.string:
                # Nothing there
                continue

            box_title = temp.string

            # Process the description box
            if box_title == DESCRIPTION:
                desc_list = table.find("span", {"class": DESCRIPTION_CLASS}).contents
                if desc_list:
                    # If not x.string, it means it's a <br/> Tag
                    ret['basic']['description'] = "\n".join([x for x in desc_list if x.string])

            # Process the course details and enrollment info
            elif box_title in (COURSE_DETAIL, ENROLL_INFO):

                # Labels and values for "Add/Drop Consent" (enroll), "Career" (course), and "Grading Basis" (course)
                labels = table.find_all("label", {"class": DROPDOWN_LABEL_CLASS})
                data = table.find_all("span", {"class": DROPDOWN_DATA_CLASS})

                if box_title == ENROLL_INFO:
                    # Labels and values for "Typically Offered", "Enrollment Requirement",
                    labels += table.find_all("label", {"class": EDITBOX_LABEL_CLASS})
                    data += table.find_all("span", {"class": EDITBOX_DATA_CLASS})

                # Add all the type -> value mappings to the ret dict
                for x in range(0, len(labels)):
                    if labels[x].string in KEYMAP:
                        ret['extra'][KEYMAP[labels[x].string]] = data[x].get_text()

                # Special case for course detail, "Units" and "Course Components"
                if box_title == COURSE_DETAIL:
                    # Units and course components
                    labels = table.find_all("label", {"class": EDITBOX_LABEL_CLASS})
                    data = table.find_all("span", {"class": EDITBOX_DATA_CLASS})
                    for x in range(0, len(labels)):
                        if labels[x].string == COURSE_COMPS:
                            # Last datafield, has multiple type -> value mappings
                            comp_map = {}
                            for i in range(x, len(data), 2):
                                comp_map[data[i].string] = data[i+1].get_text()

                            ret['extra'][KEYMAP[labels[x].string]] = comp_map
                            break
                        elif labels[x].string in KEYMAP:
                            ret['extra'][KEYMAP[labels[x].string]] = data[x].get_text()

            # Process the CEAB information
            elif box_title == CEAB:

                labels = table.find_all("label", {"class": EDITBOX_LABEL_CLASS})
                data = table.find_all("span", {"class": EDITBOX_DATA_CLASS})

                for x in range(0, len(labels)):
                    try:
                        # Clean up the data
                        temp = int(self._clean_html(data[x].string))
                    except (TypeError, ValueError) as e:
                        temp = 0

                    # Add the data to the dict if it exists
                    if labels[x].string:
                        # Remove the last character of the label to remove the ":"
                        ret['extra']['CEAB'][labels[x].string[:-1]] = temp

            else:
                raise Exception('Encountered unexpected info_box with title: "{0}"'.format(box_title))

        return ret

    #---------------------------Term info-----------------------------

    def all_terms(self):
        """
        Returns a list of dicts containing term data in the current course.
        Returns an empty list if the class isn't scheduled
        """

        DROPDOWN_ID = "DERIVED_SAA_CRS_TERM_ALT"

        ret = []
        term_sel = self.soup.find("select", id=DROPDOWN_ID)

        # Check if class is scheduled
        if term_sel:
            for x in term_sel.find_all("option"):
                m = re.search('^([^\s]+) (.+)$', x.string)
                if m:
                    ret.append(dict(solus_id=x['value'], year=m.group(1), season=m.group(2)))

        return ret


    #----------------------------------Section info------------------------------------

    def section_at_index(self, index):
        """
        Returns the `class_num`, `solus_id`, and `type` of the section
        at the specified index on the page
        None if it doesn't exist
        """

        # Get the tag at the index
        link_id, tag = self.section_id_at_index(index, return_tag=True)
        if not tag:
            return None

        # Extract the subject title and abbreviation
        m = re.search('(\S+)-(\S+)\s+\((\S+)\)', tag.string)
        if not m:
            logging.debug("Couldn't extract section information from the page")
            return None

        return dict(class_num=m.group(3), solus_id=m.group(1), type=m.group(2))

    def section_attrs_at_index(self, index):
        """
        Returns a list containing class information for the specified section index on the page.

        Used for shallow scrapes.

        Return format:
        [
            {
                'day_of_week': 1-7, starting with monday
                'start_time': datetime object
                'end_time': datetime object
                'location': room
                'instructors': [instructor names]
                'term_start': datetime object
                'term_end': datetime object
            },
        ]
        """

        # Map the strings to numeric days
        DAY_MAP = {
            "mo": 1,
            "tu": 2,
            "we": 3,
            "th": 4,
            "fr": 5,
            "sa": 6,
            "su": 7
        }

        TABLE_ID = "CLASS_MTGPAT$scroll${0}"
        CELL_CLASS = "PSEDITBOX_DISPONLY"
        INSTRUCTOR_CELL_CLASS = "PSLONGEDITBOX"

        NON_INSTRUCTORS = ("TBA", "Staff")

        data_table = self._validate_id(TABLE_ID.format(index), tag_type="table")[1]
        if not data_table:
            raise Exception("Invalid section index passed to `section_info_at_index`")

        # Get the needed cells
        cells = data_table.find_all("span", {"class": CELL_CLASS})
        inst_cells = data_table.find_all("span", {"class": INSTRUCTOR_CELL_CLASS})

        # Deal with bad formatting
        values = [self._clean_html(x.string) for x in cells]

        # Iterate over all the classes
        ret = []
        for x in range(0, len(values), 5):

            # Instructors
            temp_inst = inst_cells[x//5].string
            instructors = []
            if temp_inst and temp_inst not in NON_INSTRUCTORS:
                lis = re.sub(r'\s+', ' ', temp_inst).split(",")
                for i in range(0, len(lis), 2):
                    last_name = lis[i].strip()
                    other_names = lis[i+1].strip()
                    instructors.append("{0}, {1}".format(last_name, other_names))

            # Location
            location = values[x+3]

            # Class start/end times
            m = re.search("(\d+:\d+[AP]M)", values[x+1])
            start_time = datetime.strptime(m.group(1), "%I:%M%p") if m else None
            m = re.search("(\d+:\d+[AP]M)", values[x+2])
            end_time = datetime.strptime(m.group(1), "%I:%M%p") if m else None

            # Class start/end dates
            m = re.search('^([\S]+)\s*-\s*([\S]+)$', values[x+4])
            term_start = datetime.strptime(m.group(1), "%Y/%m/%d") if m else None
            term_end = datetime.strptime(m.group(2), "%Y/%m/%d") if m else None

            # Loop through all days
            all_days = values[x+0].lower()
            while len(all_days) > 0:
                day_abbr = all_days[-2:]
                all_days = all_days[:-2]

                if day_abbr in DAY_MAP:
                    ret.append({
                        'day_of_week': DAY_MAP[day_abbr],
                        'start_time': start_time,
                        'end_time': end_time,
                        'location': location,
                        'instructors': instructors,
                        'term_start': term_start,
                        'term_end': term_end
                    })

        return ret

    def section_attrs(self):
        """
        Parses out the section data from the section page. Used for deep scrapes
        Information availible on the course page (such as class times) is not recorded.

        For best results, update the information from the course page with this information

        Return format:

        {
            'details':{
                'status': open/closed,
                'session': session,
                'location': course location,
                'campus': course campus
            },
            'availability':{
                'class_max': spaces in class,
                'class_curr': number enrolled,
                'wait_max': spaces on wait list,
                'wait_curr': number waiting
            }
        }
        """

        TABLE_CLASS = "PSGROUPBOXWBO"
        TABLE_HEADER_CLASS = "PAGROUPBOXLABELLEVEL1"
        EDITBOX_LABEL_CLASS = "PSEDITBOXLABEL"
        EDITBOX_DATA_CLASS = "PSEDITBOX_DISPONLY"

        DETAIL_LABEL = "Class Details"
        AVAILABILITY_LABEL = "Class Availability"

        ret = {
            'details': {},
            'availability': {}
        }

        # Iterate over all tables (only need 2)
        tables = self.soup.find_all("table", {"class": TABLE_CLASS})
        for table in tables:
            temp = table.find("td", {"class": TABLE_HEADER_CLASS})
            if not temp or not temp.string:
                # Nothing there
                continue

            elif temp.string == DETAIL_LABEL:
                labels = table.find_all("label", {"class": EDITBOX_LABEL_CLASS})
                data = table.find_all("span", {"class": EDITBOX_DATA_CLASS})
                num_components = len(data) - len(labels)

                # Store class attributes
                ret['details']['status'] = data[0].string
                ret['details']['session'] = data[2].string
                ret['details']['location'] = data[8 + num_components].string
                ret['details']['campus'] = data[9 + num_components].string

            elif temp.string == AVAILABILITY_LABEL:
                data = table.find_all("span", {"class": EDITBOX_DATA_CLASS})

                # Store enrollment information
                ret['availability']['class_max'] = int(data[0].string)
                ret['availability']['wait_max'] = int(data[1].string)
                ret['availability']['class_curr'] = int(data[2].string)
                ret['availability']['wait_curr'] = int(data[3].string)

        return ret
