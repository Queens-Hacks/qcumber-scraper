#!/usr/bin/env python

from __future__ import unicode_literals
import logging
import sys
import os
import json

import yaml

# Add the parent directory (with all the code) to the path
sys.path.insert(1, os.path.join(sys.path[0], ".."))
from parser import SolusParser

def str_unless_none(obj):
    """Convert an object to a string unless it's None"""
    if obj is not None:
        return str(obj)
    return obj

def iterkeyvalue(obj):
    """Make it easy to iterate over dicts, lists, and strings"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str_unless_none(k), v
    elif isinstance (obj, list):
        for x in obj:
            yield str_unless_none(x), None
    else:
        yield str_unless_none(obj), None

def buildpath(path, new_obj):
    return "{}_{}".format(path, new_obj.replace(" ", "-"))

class TestRunner(object):
    """Ensures that parsing the HTML files generates the same cached JSON"""

    def __init__(self, config_file, input_dir):
        """Initialize the test runner"""

        # Load the config
        self.load_config(config_file)

        # Setup the input dir
        self.input_dir = input_dir

        # Parser
        self._parser = SolusParser(souplib='lxml', testing_mode=True)
        self._update_parser = False

        # Response data
        self.latest_response = None
        self.latest_text = None

    def load_config(self, config_file):
        """Load the config file"""
        try:
            with open(config_file) as f:
                self.config = yaml.load(f.read())
        except EnvironmentError as e:
            logging.critical("Couldn't load config file '{}'".format(config_file))
            raise

    def load_html(self, path):
        basename = os.path.join(self.input_dir, path)
        with open(basename + ".html", 'r') as f:
            return f.read()

    def load_json(self, path):
        basename = os.path.join(self.input_dir, path)
        with open(basename + ".json", 'r') as f:
            return json.load(f)

    @property
    def parser(self):
        """Updates the parser with new HTML (if needed) and returns it"""
        if self._update_parser:
            self._parser.update_html(self.latest_text)
            self._update_parser = False
        return self._parser

    def start(self):
        logging.info("Starting test")

        self.check_alphanums()

    # ----------------------------- Alphanums ------------------------------------ #

    def check_alphanums(self):

        # Seed the parser with the initial state
        self.parser.update_html(self.load_html("_"))

        all_alphanums = list(self.parser.all_alphanums())

        if all_alphanums != self.load_json("_"):
            logging.error("Alphanums didn't match")
        else:
            logging.info ("Alphanums match!")


        for alphanum, subjects in iterkeyvalue(self.config):

            if alphanum not in all_alphanums:
                logging.warning("Couldn't find alphanum {} specified in config file".format(alphanum))
                continue

            if not self.parser.alphanum_action(alphanum):
                logging.error("Error finding link for alphanum: {}".format(alphanum))
            self.parser.update_html(self.load_html(alphanum))

            self.check_subjects(subjects, alphanum)


    # ----------------------------- Subjects ------------------------------------- #

    def check_subjects(self, subjects, path):

        # Get a list of all subjects to iterate over
        parsed_subjects = self.parser.all_subjects()
        all_subjects = {x["abbreviation"]: x for x in parsed_subjects}

        # Check subjects
        if parsed_subjects != self.load_json(path):
            logging.error("Subjects for {} didn't match".format(path))
        else:
            logging.info("Subjects for {} matched!".format(path))

        # Iterate over all subjects
        for subject, courses in iterkeyvalue(subjects):

            curr_subject = all_subjects.get(subject)
            if curr_subject is None:
                if subject is not None:
                    logging.warning("Couldn't find subject {} specified in config file".format(subject))
                continue

            unique = curr_subject["_unique"]
            subject_path = buildpath(path, subject)

            # Check dropdown exists
            if not self.parser.subject_action(unique):
                logging.error("Couldn't find subject '{abbreviation} - {title} dropdown'".format(**curr_subject))
            self.parser.update_html(self.load_html(subject_path))

            # Check courses
            self.check_courses(courses, subject_path)

            # Check rollup exists
            if not self.parser.subject_action(unique):
                logging.error("Couldn't find subject '{abbreviation} - {title} rollup'".format(**curr_subject))
            self.parser.update_html(self.load_html(path))

    def check_courses(self, courses, path):

        # Get a list of all courses to iterate over
        parsed_courses = self.parser.all_courses()
        all_courses = {x["code"]: x for x in parsed_courses}

        # Check courses
        if parsed_courses != self.load_json(path):
            logging.error("Courses for {} didn't match".format(path))
        else:
            logging.info("Courses for {} matched!".format(path))

        # Iterate over all courses
        for course, terms in iterkeyvalue(courses):

            curr_course = all_courses.get(course)
            if curr_course is None:
                if course is not None:
                    logging.warning("Couldn't find course {} specified in config file".format(course))
                continue

            course_path = buildpath(path, course)
            section_path = buildpath(course_path, "sections")
            unique = curr_course["_unique"]

            # Check course exists
            if not self.parser.course_action(unique):
                logging.warning("Couldn't find course '{number} - {title}'".format(**course_attrs['basic']))
            self.parser.update_html(self.load_html(course_path))

            # Check course attrs are correct
            course_attrs = self.parser.course_attrs()
            if course_attrs != self.load_json(course_path):
                logging.error("Course attrs for {} didn't match".format(course_path))
            else:
                logging.info("Course attrs for {} matched!".format(course_path))

            # Check 'view sections' exists
            if not self.parser.show_sections_action():
                # TODO: This can occur when there are actually no sections to view
                logging.warning("Couldn't find the 'view class sections' button for '{}'".format(course_path))
            self.parser.update_html(self.load_html(section_path))

            # Check terms
            self.check_terms(terms, section_path)

            # No need to check returning from course - it's a static button
            self.parser.update_html(self.load_html(path))


    def check_terms(self, terms, path):

        # Get all terms on the page and iterate over them
        parsed_terms = self.parser.all_terms()
        all_terms = {"{year} {season}".format(**x): x for x in parsed_terms}

        # Check terms
        if parsed_terms != self.load_json(path):
            logging.error("Terms for {} didn't match".format(path))
        else:
            logging.info("Terms for {} matched!".format(path))

        # Iterate over all terms
        for term, sections in iterkeyvalue(terms):
            curr_term = all_terms.get(term)
            if curr_term is None:
                if term is not None:
                    logging.warning("Couldn't find term {} specified in config file".format(term))
                continue

            unique = curr_term["_unique"]
            term_path = buildpath(path, term)

            # Check term exists
            if not self.parser.term_value(unique):
                logging.warning("Couldn't find term '{year} - {season}'".format(**curr_term))

            self.parser.update_html(self.load_html(term_path))

            # Check sections in term
            self.check_sections(sections, term_path)

            # No need to check returning from term
            self.parser.update_html(self.load_html(path))

    def check_sections(self, sections, path):

        # Grab all the basic data
        parsed_sections = self.parser.all_section_data()
        all_sections = {x["basic"]["solus_id"]: x for x in parsed_sections}

        # Check terms
        if parsed_sections != self.load_json(path):
            # TODO: This can fail because of the representation of the datetimes in JSON
            logging.error("Section data for {} didn't match".format(path))
        else:
            logging.info("Section data for {} matched!".format(path))

        # Don't really need the `iterkeyvalue` but it makes the config
        # parsing a litte more lax so whatever
        for section, _ in iterkeyvalue(sections):

            curr_section = all_sections.get(section)
            if curr_section is None:
                if section is not None:
                    logging.warning("Couldn't find section {} specified in config file".format(section))
                continue

            unique = curr_section['_unique']
            section_path = buildpath(path, section)

            # Check section exists
            if not self.parser.section_action(unique):
                logging.error("Couldn't find section '{class_num}-{type} ({solus_id}) -- {status}'".format(**curr_section["basic"]))
            self.parser.update_html(self.load_html(section_path))

            # Check deep scrape attrs are correct
            section_attrs = self.parser.section_deep_attrs()
            if section_attrs != self.load_json(section_path):
                logging.error("Section attrs for {} didn't match".format(section_path))
            else:
                logging.info("Section attrs for {} matched!".format(section_path))

            # No need to check returning from section - it's a static button
            self.parser.update_html(self.load_html(path))

def _init_logging():

    root_logger = logging.getLogger()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s][%(processName)s]: %(message)s"))
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)
    root_logger.setLevel(logging.WARNING)

if __name__ == "__main__":

    _init_logging()
    TestRunner("testconfig.yaml", "out").start()
