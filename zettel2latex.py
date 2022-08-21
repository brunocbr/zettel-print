#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# zettel2latex.py
#   by Bruno L. Conte <bruno@brunoc.com.br>, 2021

import re
from glob import glob
from collections import OrderedDict
import os, sys, getopt

KEY_CITEKEY = 'citekey'
KEY_LOCATION = 'loc'

ZETTEL_DIR = os.environ['PHI_ARCHIVE']

OPT = {
    'book-mode': True # If true, output notes in chapters (H1); intended for appending notes to one single file
    }

rx_dict = OrderedDict([
    ('ignore', re.compile(r'^(△|○)')),
    ('footnote', re.compile(r'\[\^(?P<fn_id>[a-zA-Z0-9_-]+)]')),
    ('parallel_texts', re.compile(r' *>\s{0,1}\[\[(?P<id_left>\d{3,})\]\]::\[\[(?P<id_right>\d{3,})\]\]')), # >[[dddd]]::[[dddd]]
    ('pandoc_cite_noauthor', re.compile(r'-@\[\[(?P<id>\d{3,})\]\]')),  # -@[[dddd]]
    ('pandoc_cite_inline', re.compile(r'@@\[\[(?P<id>\d{3,})\]\]')),    # @@[[dddd]]
    ('pandoc_cite', re.compile(r'@\[\[(?P<id>\d{3,})\]\]')),            #  @[[dddd]]
    ('no_ref', re.compile(r'-\[\[(?P<id>\d{3,})\]\]')),                 #  -[[dddd]]        do not add note
    ('quote', re.compile(r' *>\s{0,1}\[\[(?P<id>\d{3,})\]\]')),         #  >[[dddd]]        insert quote immediately
    ('add_ref', re.compile(r'\+\[\[(?P<id>\d{3,})\]\]')),               #  +[[dddd]]        insert note immediately
    ('link', re.compile(r'§\[\[(?P<id>\d{3,})\]\]')),                   #  §[[dddd]]        print reference to paragraph or text
    ('cross_ref_alt', re.compile(r'\[\[(?P<id>\d{3,})\]\]:')),          #   [[dddd]]:       hidden cross reference
    ('cross_ref', re.compile(r'\[\[(?P<id>\d{3,})\]\]')),            #   [[dddd]]        hidden cross reference
    ('yaml_end_div', re.compile(r'^\.\.\.$')),
    ('yaml_div', re.compile(r'^\-\-\-$')),
    ('md_heading_top', re.compile(r'^#{1,2}\s+')),
    ('md_heading_lower', re.compile(r'^#{3,}\s+')),
    ('hashtag', re.compile(r'#(?P<tag>[0-9A-Za-z./_&øφƒβπ]+)\b', re.UNICODE)),
    ('symtherefore', re.compile(r'∴', re.UNICODE)),
    ('symbecause', re.compile(r'∵', re.UNICODE)),
    ('symmindmap', re.compile(r'🧠', re.UNICODE)),
    ('symideaspace', re.compile(r'💡', re.UNICODE)),
    ('symforall', re.compile(r'∀', re.UNICODE)),
    ('symexists', re.compile(r'∃', re.UNICODE)),
    ('symrightarrow', re.compile(r'→', re.UNICODE)),
    ('symsupset', re.compile(r'⊃', re.UNICODE))
])


rx_first_word = re.compile(r'^\s*([a-zA-Z0-9\*_]+)')

fields_dict = {
    "citekey": re.compile(r'^' + KEY_CITEKEY + r':[ \t]*@{0,1}(?P<id>[A-Za-z\d:]+)\s*$'),
    "loc": re.compile(r'^' + KEY_LOCATION + r':[ \t]*(?P<id>[\S]+)\s*$'),
    'title': re.compile(r'^title:\s*\'(?P<id>.*)\'\s*$'),
    'id': re.compile(r'^id:\s*Φ{0,1}(?P<id>\d{3,})')
}

def _parse_line(line, thedict):
    for key, rx in thedict.items():
        match = rx.search(line)
        if match:
            return key, match, match.end()
    return None, None, None

def _z_get_filepath(zettel_id):
    """
    Get file path for a note
    """
    global zettel_dir, index_filename

    try:
        fn = glob(ZETTEL_DIR + "/" + zettel_id + "[ \.]*")[0]
    except:
        print("ERROR: file not found for zettel " + zettel_id)
    return fn

def _z_get_title_from_filepath(filepath):
    head, tail = os.path.split(filepath)
    title = tail.split('.')[-2:][0]
    rx = re.compile(r'\d{3,}\s+(?P<title>)')
    match = rx.search(filepath)
    if match:
        return match.group('title')
    else:
        return None


def _pandoc_citetext(zettel_id):
    """
    Get reference for pandoc-style citation
    """
    global fields_dict
    citekey = None
    loc = None
    filepath = _z_get_filepath(zettel_id)

    with open(filepath, 'r') as file_obj:
        lines = file_obj.read().splitlines()

    for line in lines:
        key, match, end = _parse_line(line, fields_dict)
        if key == "citekey":
            citekey = match.group('id')
        if key == "loc":
            loc = match.group('id')

    citetext = None
    if ((citekey and loc) and (loc != "0")):
        citetext = citekey + ", " + loc
    elif (citekey):
        citetext = citekey
    return citetext

def generate_header(metadata):
    data = ['---']
    for key, value in metadata.items():
        data.append(key + ":    " + value + '  ')
        if key == 'id':
            data.append('zettel_id: ' + value)
    data = data + ['...'] + ['']
    return data

def generate_chapter(metadata):
    data = ['# ' + metadata['title']] + [ '\\setzettel{' + metadata['id'] + '}' ] + ['']
    return data

def generate_marginnote_reference(metadata):
    try:
        loc = metadata['loc']
        if loc == "0":
            loc = None
    except:
        loc = None

    try:
        citekey = metadata['citekey']
    except:
        citekey = None

    if citekey:
        if loc:
            ref = '\\marginnote{\\fullcite[' + loc + ']{' + citekey + '}}'
        else:
            ref = '\\marginnote{\\fullcite{' + citekey + '}}'
    else:
        ref = ''
    return ref


def parse_zettel(zettel_id):

    insert_quotes = []
    metadata = {}
    data = []

    def parse_body_chunk(chunk):
        key, match, end = _parse_line(chunk, rx_dict)

        if (key is None):
            return chunk

        left_chunk = chunk[:end]

        if key == 'quote':
            link = match.group('id')
            # insert_quotes.append(link)
            # left_chunk = rx_dict[key].sub("", left_chunk)
            left_chunk = rx_dict[key].sub('\\\\zettelref{' + link + '}', left_chunk)
        if key == 'parallel_texts':
            left_link = match.group('id_left')
            right_link = match.group('id_right')
            # insert_quotes.append(left_link)
            # insert_quotes.append(right_link)
            # left_chunk = rx_dict[key].sub("", left_chunk)
            left_chunk = rx_dict[key].sub('\\\\zettelref{' + left_link + '} \\\\zettelref{' + right_link + '}', left_chunk)

        # normalize headings
        if key == 'md_heading_top':
            if OPT['book-mode']:
                left_chunk = rx_dict[key].sub('## ', left_chunk)
            else:
                left_chunk = rx_dict[key].sub('# ', left_chunk)
        if key == 'md_heading_lower':
            if OPT['book-mode']:
                left_chunk = rx_dict[key].sub('### ', left_chunk)
            else:
                left_chunk = rx_dict[key].sub('## ', left_chunk)

        if key in ['cross_ref', 'cross_ref_alt', 'link', 'add_ref', 'no_ref']:
            link = match.group('id')
            left_chunk = rx_dict[key].sub('\\\\zettelref{' + link + '}', left_chunk)

        if key == 'pandoc_cite_noauthor':
            link = match.group('id')
            left_chunk = rx_dict[key].sub('[-@' + _pandoc_citetext(link) + '] \\\\zettelref{' + link + '}', left_chunk)
        if key == 'pandoc_cite':
            link = match.group('id')
            left_chunk = rx_dict[key].sub('[@' + _pandoc_citetext(link) + '] \\\\zettelref{' + link + '}', left_chunk)
        if key == 'pandoc_cite_inline':
            link = match.group('id')
            left_chunk = rx_dict[key].sub('@' + _pandoc_citetext(link) + ' \\\\zettelref{' + link + '}', left_chunk)

        if key.startswith('sym'):
            if key in [ 'symforall', 'symexists', 'symrightarrow', 'symsupset' ]:
                left_chunk = rx_dict[key].sub('\\\\' + key + ' ', left_chunk)
            else:
                left_chunk = rx_dict[key].sub('\\\\' + key, left_chunk)

        if key == 'hashtag':
            tag = match.group('tag')
            left_chunk = rx_dict[key].sub('\\\\hashtag{' + tag + '}', left_chunk)

        if key == 'footnote':
            fn_id = match.group('fn_id')
            left_chunk = rx_dict[key].sub('[^fn-' + zettel_id + '-' + fn_id +']', left_chunk)

        return left_chunk + parse_body_chunk(chunk[end:])

    def parse_yaml_line(chunk):
        key, match, end = _parse_line(chunk, fields_dict)

        if (key):
            metadata[key] = match.group('id')

    yaml_divert = False
    got_content = False

    filepath = _z_get_filepath(zettel_id)
    metadata['title'] = _z_get_title_from_filepath(filepath)

    with open(filepath, 'r') as file_object:
        lines = file_object.read().splitlines()

    for line in lines:
        insert_quotes = []

        key, match, end = _parse_line(line, rx_dict)

        if yaml_divert:
            parse_yaml_line(line)
            yaml_divert = not key in [ 'yaml_end_div', 'yaml_div' ]
            if not yaml_divert:
                if OPT['book-mode']:
                    # no header
                    data = data + [''] + generate_chapter(metadata)
                else:
                    # rewrite yaml header
                    data = data + generate_header(metadata)
            continue

        if key == 'yaml_div':
            yaml_divert = True
            continue

        if key == 'ignore':
            continue

        if (not line == '') and not got_content:
            got_content = True
            if (key in ['md_heading_top']):
                h = rx_dict['md_heading_top'].sub('', line)
                if metadata['title'] != h:
                    line = line + generate_marginnote_reference(metadata)
                else:
                    line = ''
                    got_content = False
            else:
                m = rx_first_word.search(line)
                if m:
                    line = line[:m.end()] + generate_marginnote_reference(metadata) + line[(m.end()):]
                else:
                    line = line + generate_marginnote_reference(metadata) # probably nasty
        if got_content:
            line = parse_body_chunk(line)
            data.append(line)

    data.append("\label{%s-last}" % str(zettel_id))
    return data

useroptions, theargs = getopt.getopt(sys.argv[1:], 's', [ 'stand-alone' ])

for opt, arg in useroptions:
    if opt in ('-s', '--stand-alone'):
        OPT['book-mode'] = False

d = parse_zettel(theargs[0])

for l in d:
    sys.stdout.write("%s\n" % l)
