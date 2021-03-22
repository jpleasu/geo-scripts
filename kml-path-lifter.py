#!/usr/bin/env python3
'''
The way that Google Earth connects the points of paths can result in "taking
the long way" to avoid crossing the antimeridian.  This script attempts to fix
KML files to prevent this.

setup
-----
pip3 install mpmath lxml


usage
-----

running

    python3 kml-path-lifter input1.kml input2.kml

will result in new files, input1-lifted.kml and input2-lifted.kml


'''

import os
import zipfile
import tempfile
import sys

from lxml import etree
from mpmath import mpf, sign


class Coordinates:
    def __init__(self, longitude: mpf, latitude: mpf, z: mpf):
        self.longitude = longitude
        self.latitude = latitude
        self.z = z

    def tostring(self):
        return '%s,%s,%s' % (self.longitude, self.latitude, self.z)

    @staticmethod
    def fromstring(coords):
        return Coordinates(*[mpf(s) for s in coords.split(',')])


def minn(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def maxn(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def lift(l, m):
    '''
    Google Earth draws arcs between successive points of a path on an unraveled
    (lifted) line rather than a circle.  This function chooses a range (the
    lift) to minimize the length of arcs.


    params:
        l is a list of values
        m is the modulus

    return:
        either the smallest value of the new range or None.

        None is returned when there's nothing to do since all short arcs fit in
        the current range, or a better range can't be found, e.g. because the
        path wraps around.
    '''
    arcs = list(zip(l, l[1:]))

    o0 = None
    o1 = None
    keep = []
    for x, y in arcs:
        if (x - y) % m < (y - x) % m:
            # wants y < x
            if x < y:
                o0 = maxn(o0, x)
                o1 = minn(o1, y)
            else:
                keep.append((y, x))
        else:
            # wants x < y
            if y < x:
                o0 = maxn(o0, y)
                o1 = minn(o1, x)
            else:
                keep.append((x, y))

    if o0 is None or o0 >= o1:
        return None

    for x, y in keep:
        if x <= o0:
            o0 = max(o0, y)

    for x, y in keep:
        if x > o0:
            o1 = min(o1, x)

    if o0 >= o1:
        return None

    return o0 + (o1 - o0) / 2


def process_kml(fobj):
    '''
    process a file-like object, return a string
    '''
    parser = etree.XMLParser(strip_cdata=False)
    xml_document = etree.parse(fobj, parser=parser)
    for xml_coordinates in xml_document.xpath(
            '//*[local-name()="coordinates"]'):
        l = [Coordinates.fromstring(coords) for coords in
             xml_coordinates.text.strip().split(' ') if len(coords) > 0]

        changed = False
        o = lift([c.longitude for c in l], 360)
        if o is not None:
            for c in l:
                if c.longitude < o:
                    c.longitude += 360
            changed = True

        o = lift([c.latitude for c in l], 180)
        if o is not None:
            for c in l:
                if c.latitude < o:
                    c.latitude += 180
            changed = True

        if changed:
            xml_coordinates.text = ' '.join(c.tostring() for c in l)

    return etree.tostring(xml_document).decode('utf8')


if __name__ == '__main__':
    for infilename in sys.argv[1:]:
        print(f'Processing {infilename}...')
        if infilename.endswith('.kmz'):
            outfilename = infilename[:-4] + '-lifted.kml'
            with zipfile.ZipFile(infilename, 'r') as zin:
                outkml = process_kml(zin.open('doc.kml'))
        elif infilename.endswith('.kml'):
            outfilename = infilename[:-4] + '-lifted.kml'
            outkml = process_kml(open(infilename))

        print(f'  writing {outfilename}...')
        with open(outfilename, 'w') as out:
            out.write(outkml)
