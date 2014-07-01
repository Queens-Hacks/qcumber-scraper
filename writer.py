import logging
import json
import os
from os import path

from config import OUTPUT_DIR

def json_datetime_dump(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError('Object of type %s with value of %s is not JSON serializable' % (type(obj), repr(obj)))

def out_path(dirname):
    """
    Ensure that the output directory exists.
    Returns False if no output directory is specified
    """

    if not OUTPUT_DIR:
        return False

    out = os.path.join(OUTPUT_DIR, dirname)
    try:
        os.makedirs(out)
    except:
        pass

    return out

def write_course(course):
    out = out_path('courses')

    # Merge the basic and extra information into a single dict
    # I should probably just do this at a lower level, but this works too
    merged_course = course['basic'].copy()
    merged_course.update(course['extra'])

    filename = '{subject} {number}.json'.format(**merged_course)
    with open(os.path.join(out, filename), 'w') as f:
        f.write(json.dumps(course, indent=4, default=json_datetime_dump))

def write_subject(subject):
    out = out_path('subjects')

    filename = '{abbreviation}.json'.format(**subject)
    with open(os.path.join(out, filename), 'w') as f:
        f.write(json.dumps(subject, indent=4, default=json_datetime_dump))

def write_section(section):
    out = out_path('sections')
    
    merged_section = section['basic']

    filename = '{year} {season} {subject} {course} ({solus_id}).json'.format(**merged_section)
    with open(os.path.join(out, filename), 'w') as f:
        f.write(json.dumps(section, indent=4, default=json_datetime_dump))
