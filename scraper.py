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

            for subject_index in range(subject_start, subject_end, subject_step):
                data = self.session.parser.subject_at_index(subject_index)

                logging.info("Subject: {abbreviation} - {title}".format(**data))

                self.session.dropdown_subject(subject_index)

                num_courses = self.session.parser.num_courses()
                
                course_start = self.job["course_start"]
                course_end = self.job["course_end"]
                
                if course_end is None:
                    course_end = num_subjects

                for course_index in range(course_start, course_end):
                    # TODO: Scraping logic
                    pass

                self.session.rollup_subject(subject_index)
