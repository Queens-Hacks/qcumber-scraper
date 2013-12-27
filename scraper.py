import logging

class SolusScraper(object):
    """The class that coordinates the actual scraping"""

    def __init__(self, session, job):
        """Store the session to use and the scrape job to perform"""
        self.session = session
        self.job = job

    def start(self):
        """Starts running the scrape outlined in the job"""
        logging.info("Starting job: {0}".format(self.job))

        for letter in self.job["letters"]:
            # Go to the letter
            self.session.select_alphanum(letter)

            # Find the number of subjects (so we know how to iterate over them)
            num_subjects = self.session.parser.num_subjects()

            subject_start = self.job["subject_start"]
            subject_end = self.job["subject_end"]
            subject_step = self.job["subject_step"]

            if subject_end is None:
                subject_end = num_subjects
            else:
                subject_end = min(subject_end, num_subjects)

            for subject_index in range(subject_start, subject_end, subject_step):
                data = self.session.parser.subject_at_index(subject_index)

                logging.info("--Subject: {abbreviation} - {title}".format(**data))

                self.session.dropdown_subject(subject_index)

                num_courses = self.session.parser.num_courses()

                course_start = self.job["course_start"]
                course_end = self.job["course_end"]
                
                if course_end is None:
                    course_end = num_courses
                else:
                    course_end = min(course_end, num_courses)

                for course_index in range(course_start, course_end):
                    self.session.open_course(course_index)

                    course_attrs = self.session.parser.course_attrs()
                    logging.info("----Course: {number} - {title}".format(**course_attrs['basic']))
                    logging.debug("DATA DUMP: {0}".format(course_attrs['extra']))

                    self.session.show_sections()

                    terms = self.session.parser.all_terms()
                    for term in terms:
                        logging.info("------Term: {year} - {season}".format(**term))
                        self.session.switch_to_term(term['solus_id'])
                        self.session.view_all_sections()

                        num_sections = self.session.parser.num_sections()

                        for section_index in range(0, num_sections):
                            section_info = self.session.parser.section_at_index(section_index)
                            logging.info("--------Section: {class_num}-{type} ({solus_id})".format(**section_info))

                            section_attrs = {}
                            section_attrs['classes'] = self.session.parser.section_attrs_at_index(section_index)

                            if self.job["deep"]:
                                self.session.visit_section_page(section_index)

                                # Add the new information to the section_attrs dict
                                section_attrs.update(self.session.parser.section_attrs())
                                self.session.return_from_section()

                            logging.debug("DATA DUMP: {0}".format(section_attrs))

                    self.session.return_from_course()

                self.session.rollup_subject(subject_index)
