from __future__ import unicode_literals
import logging
import writer

class SolusScraper(object):
    """The class that coordinates the actual scraping"""

    def __init__(self, session, job):
        """Store the session to use and the scrape job to perform"""

        self.session = session
        self.job = job

    def start(self):
        """Starts running the scrape outlined in the job"""

        logging.info("Starting job: {0}".format(self.job))

        try:
            self.scrape_letters()
        except Exception as e:
            self.session.parser.dump_html()
            raise

    def scrape_letters(self):
        """Scrape all the letters"""

        for letter in self.job["letters"]:

            # Go to the letter
            self.session.select_alphanum(letter)

            self.scrape_subjects()

    def scrape_subjects(self):
        """Scrape all the subjects"""

        # Neatness
        start = self.job["subject_start"]
        end = self.job["subject_end"]
        step = self.job["subject_step"]

        # Get a list of all subjects to iterate over
        all_subjects = self.session.parser.all_subjects(start=start, end=end, step=step)

        # Iterate over all subjects
        for subject in all_subjects:

            logging.info("--Subject: {abbreviation} - {title}".format(**subject))

            writer.write_subject(subject)

            self.session.dropdown_subject(subject["_unique"])

            self.scrape_courses(subject)

            self.session.rollup_subject(subject["_unique"])

    def scrape_courses(self, subject):
        """Scrape courses"""

        # Neatness
        start = self.job["course_start"]
        end = self.job["course_end"]

        # Get a list of all courses to iterate over
        all_courses = self.session.parser.all_courses(start=start, end=end)

        # Iterate over all courses
        for course in all_courses:
            self.session.open_course(course["_unique"])

            course_attrs = self.session.parser.course_attrs()
            course_attrs['basic']['subject'] = subject['abbreviation']

            logging.info("----Course: {number} - {title}".format(**course_attrs['basic']))
            logging.debug("COURSE DATA DUMP: {0}".format(course_attrs['extra']))
            writer.write_course(course_attrs)

            self.session.show_sections()

            self.scrape_terms(course_attrs)

            self.session.return_from_course()

    def scrape_terms(self, course):
        """Scrape terms"""

        # Get all terms on the page and iterate over them
        all_terms = self.session.parser.all_terms()
        for term in all_terms:
            logging.info("------Term: {year} - {season}".format(**term))
            self.session.switch_to_term(term["_unique"])

            self.session.view_all_sections()
            self.scrape_sections(course, term)

    def scrape_sections(self, course, term):
        """Scrape sections"""

        # Grab all the basic data
        all_sections = self.session.parser.all_section_data()


        if logging.getLogger().isEnabledFor(logging.INFO):
            for section in all_sections:
                logging.info("--------Section: {class_num}-{type} ({solus_id}) -- {status}".format(**section["basic"]))
                if not self.job["deep"]:
                    logging.debug("SECTION CLASS DATA: {0}".format(section["classes"]))

        # Deep scrape, go to the section page and add the data there
        if self.job["deep"]:
            for i in range(len(all_sections)):
                self.session.visit_section_page(all_sections[i]["_unique"])

                # Add the new information to the all_sections dict
                new_data = self.session.parser.section_deep_attrs()
                all_sections[i].update(new_data)

                self.session.return_from_section()

                logging.debug("SECTION DEEP DATA DUMP: {0}".format(all_sections[i]))

        for section in all_sections:
            section['basic']['course'] = course['basic']['number']
            section['basic']['subject'] = course['basic']['subject']
            section['basic']['year'] = term['year']
            section['basic']['season'] = term['season']

            writer.write_section(section)

