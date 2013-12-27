import logging
import ssl
import bs4
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager

from parser import SolusParser


class SSLAdapter(HTTPAdapter):
    '''An HTTPS Transport Adapter that uses an arbitrary SSL version.
    http://lukasa.co.uk/2013/01/Choosing_SSL_Version_In_Requests/
    '''
    def __init__(self, ssl_version=None, **kwargs):
        self.ssl_version = ssl_version
        super(SSLAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=self.ssl_version)


class SolusSession(object):
    """Represents a solus browsing session"""

    login_url = "https://my.queensu.ca"
    continue_url = "SAML2/Redirect/SSO"
    course_catalog_url = "https://saself.ps.queensu.ca/psc/saself/EMPLOYEE/HRMS/c/SA_LEARNER_SERVICES.SSS_BROWSE_CATLG_P.GBL"

    def __init__(self, user=None, password=None):
        self.session = requests.session()

        # Use SSL version 1
        self.session.mount('https://', SSLAdapter(ssl_version=ssl.PROTOCOL_TLSv1))

        # Parser
        self._parser = SolusParser()
        self._update_parser = False

        # Response data
        self.latest_response = None
        self.latest_text = None

        # Recover from errors
        self.recovery_state = -1 #State of recovery ( < 0 is not recovering, otherwise the current recovery level)
        self.recovery_stack = [None, None, None, None, None] #letter, subj subject, course, term, section

        # Authenticate and navigate to course catalog
        logging.info("Logging in...")
        self.login(user, password)

        logging.info("Navigating to course catalog...")
        self.go_to_course_catalog()

        # Should now be on the course catalog page. If not, something went wrong
        if self.latest_response.url != self.course_catalog_url:
            # SOLUS Doesn't like requests v2.1.0 (getting error 999, unsupported OS)
            # Seems to be a quirk of it. The headers don't matter (even user-agent)
            # Sticking with v2.0.1 until the issue is resolved
            raise EnvironmentError("Authenticated, but couldn't access the SOLUS course catalog.")

    @property
    def parser(self):
        """Updates the parser with new HTML (if needed) and returns it"""
        if self._update_parser:
            self._parser.update_html(self.latest_text)
            self._update_parser = False
        return self._parser

    def login(self, user, password):
        """Logs into the site"""

        # Load the access page to set all the cookies and get redirected
        self._get(self.login_url)

        # Login procedure is different when JS is disabled
        payload = {
           'j_username': user,
           'j_password': password,
           'IDButton': '%C2%A0Log+In%C2%A0',
        }
        self._post(self.latest_response.url, data=payload)

        # Check for the continue page
        if self.continue_url in self.latest_response.url:
            self.do_continue_page()

        # Should now be authenticated and on the my.queensu.ca page, submit a request for the URL in the 'SOLUS' button
        link = self.parser.login_solus_link()
        if not link:
            # Not on the right page
            raise EnvironmentError("Could not authenticate with the Queen's SSO system. The login credentials provided may have been incorrect.")

        logging.info("Sucessfully authenticated.")
        # Have to actually use this link to access SOLUS initially otherwise it asks for login again
        self._get(link)

        # The request could (seems 50/50 from browser tests) bring up another continue page
        if self.continue_url in self.latest_response.url:
            self.do_continue_page()

        # Should now be logged in and on the student center page

    def do_continue_page(self):
        """
        The SSO system returns a specific page only if JS is disabled
        It has you click a Continue button which submits a form with some hidden values
        """
        data = self.parser.login_continue_page()
        if not data:
            return
        self._post(data["url"], data=data["payload"])

    def go_to_course_catalog(self):
        self._catalog_post("")
        self.select_alphanum("A")

    # ----------------------------- Alphanums ------------------------------------ #

    def select_alphanum(self, alphanum):
        """Navigates to a letter/number"""
        if self.recovery_state < 0:
            self.recovery_stack[0] = alphanum

        self._catalog_post('DERIVED_SSS_BCC_SSR_ALPHANUM_{0}'.format(alphanum.upper()))

    # ----------------------------- Subjects ------------------------------------- #

    def dropdown_subject(self, subject_index):
        """Opens the dropdown menu for a subject"""
        if self.recovery_state < 0:
            self.recovery_stack[1] = subject_index

        action = self.parser.subject_id_at_index(subject_index)
        if not action:
            raise Exception("Tried to drop down an invalid subject index")

        self._catalog_post(action)

    def rollup_subject(self, subject_index):
        """Closes the dropdown menu for a subject"""
        if self.recovery_state < 0:
            self.recovery_stack[1] = None

        action = self.parser.subject_id_at_index(subject_index)
        if not action:
            raise Exception("Tried to roll up an invalid subject index")

        self._catalog_post(action)

    # ----------------------------- Courses ------------------------------------- #

    def open_course(self, course_index):
        """Opens a course page by following the course link with the supplied index"""
        if self.recovery_state < 0:
            self.recovery_stack[2] = course_index

        action = self.parser.course_id_at_index(course_index)
        if not action:
            raise Exception("Tried to open a course with an invalid index")

        self._catalog_post(action)

    def return_from_course(self):
        """Navigates back from course to subject"""
        self.recovery_stack[3] = None
        self.recovery_stack[2] = None
        self._catalog_post('DERIVED_SAA_CRS_RETURN_PB')

    # -----------------------------Sections ------------------------------------- #

    def show_sections(self):
        """
        Clicks on the 'View class sections' button on the course page if it exists
        """
        if self.parser._validate_id('DERIVED_SAA_CRS_SSR_PB_GO'):
            self._catalog_post('DERIVED_SAA_CRS_SSR_PB_GO')

    def switch_to_term(self, solus_id):
        """Shows the sections for the term with the specified solus_id"""
        if self.recovery_state < 0:
            self.recovery_stack[3] = solus_id
        self._catalog_post(action='DERIVED_SAA_CRS_SSR_PB_GO$98$', extras={'DERIVED_SAA_CRS_TERM_ALT': solus_id})

    def view_all_sections(self):
        """Presses the "view all sections" link on the course page if needed"""
        if self.parser._validate_id('CLASS_TBL_VW5$fviewall$0'):
            self._catalog_post('CLASS_TBL_VW5$fviewall$0')

    def visit_section_page(self, section_index):
        """
        Opens the dedicated page for the provided section.
        Used for deep scrapes
        """
        if self.recovery_state < 0:
            self.recovery_stack[4] = section_index

        action = self.parser.section_id_at_index(section_index)
        if not action:
            raise Exception("Tried to open a section with an invalid index")

        self._catalog_post(action)

    def return_from_section(self):
        """
        Navigates back from section to course.
        Used for deep scrapes
        """
        self.recovery_stack[4] = None
        self._catalog_post('CLASS_SRCH_WRK2_SSR_PB_CLOSE')


    # -----------------------------General Purpose------------------------------------- #

    def _get(self, url, **kwargs):
        self.latest_response = self.session.get(url, **kwargs)
        self._update_attrs()

    def _post(self, url, **kwargs):
        self.latest_response = self.session.post(url, **kwargs)
        self._update_attrs()

    def _update_attrs(self):
        self.latest_text = self.latest_response.text

        # The parser requires an update
        self._update_parser = True

    def _catalog_post(self, action, extras={}):
        """Submits a post request to the site"""
        extras['ICAction'] = action
        self._post(self.course_catalog_url, data=extras)

        #import random
        # TODO: Improve this, could easily give false positives
        if "Data Integrity Error" in self.latest_text:
            self._recover(action, extras)

        # TESTING - Fake a DIE using random number generator
        #elif action != "" and random.random() < 0.1:
        #    self._catalog_post("")
        #    self._recover(action, extras)

    def _recover(self, action, extras={}):
        """Attempts to recover the scraper state after encountering an error"""

        # Don't recurse, retry
        if self.recovery_state >= 0:
            logging.warning("Error while recovering, retrying")
            self.recovery_state = 0
            return

        # Number of non-null elements in the recovery stack
        num_states = len(filter(None, self.recovery_stack))

        # Start recovery process
        logging.warning("Encounted SOLUS Data Integrety Error, attempting to recover")
        self.recovery_state = 0

        while self.recovery_state < num_states:

            # Has to be done before the recovery operations
            self.recovery_state += 1

            # State numbers are OBO due to previous increment
            if self.recovery_state == 1:
                logging.info("--Selecting letter {0}".format(self.recovery_stack[0]))
                self.select_alphanum(self.recovery_stack[0])
            elif self.recovery_state == 2:
                logging.info("----Selecting subject {0}".format(self.recovery_stack[1]))
                self.dropdown_subject(self.recovery_stack[1])
            elif self.recovery_state == 3:
                logging.info("------Selecting course number {0}".format(self.recovery_stack[2]))
                self.open_course(self.recovery_stack[2])
                self.show_sections()
            elif self.recovery_state == 4:
                logging.info("--------Selecting term {0}".format(self.recovery_stack[3]))
                self.switch_to_term(self.recovery_stack[3])
            elif self.recovery_state == 5:
                logging.info("----------Selecting section {0}".format(self.recovery_stack[4]))
                self.visit_section_page(self.recovery_stack[4])

        # Finished recovering
        self.recovery_state = -1
        logging.info("Recovered, retrying original request")

        self._catalog_post(action, extras)
