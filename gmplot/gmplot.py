from __future__ import absolute_import

import json
# import math
import os
import requests
import warnings
import datetime

from collections import namedtuple

from gmplot.color_dicts import mpl_color_map, html_color_codes
from gmplot.google_maps_templates import SYMBOLS, CIRCLE


Symbol = namedtuple('Symbol', ['symbol', 'lat', 'long', 'size'])


class InvalidSymbolError(Exception):
    pass


def safe_iter(var):
    try:
        return iter(var)
    except TypeError:
        return [var]


class GoogleMapPlotter(object):

    def __init__(self, center_lat, center_lng, zoom, apikey=''):
        self.center = (float(center_lat), float(center_lng))
        self.zoom = int(zoom)
        self.apikey = str(apikey)
        self.grids = None
        self.paths = []
        self.shapes = []
        self.points = []
        self.circles = []
        self.symbols = []
        self.heatmap_points = []
        self.ground_overlays = []
        self.radpoints = []
        self.gridsetting = None
        self.coloricon = os.path.join(os.path.dirname(__file__), 'markers/%s.png')
        self.color_dict = mpl_color_map
        self.html_color_codes = html_color_codes

    @classmethod
    def from_geocode(cls, location_string, zoom=13):
        lat, lng = cls.geocode(location_string)
        return cls(lat, lng, zoom)

    @classmethod
    def geocode(self, location_string):
        geocode = requests.get(
            'http://maps.googleapis.com/maps/api/geocode/json?address="%s"' % location_string)
        geocode = json.loads(geocode.text)
        latlng_dict = geocode['results'][0]['geometry']['location']
        return latlng_dict['lat'], latlng_dict['lng']

    def grid(self, slat, elat, latin, slng, elng, lngin):
        self.gridsetting = [slat, elat, latin, slng, elng, lngin]

    def marker(self, lat, lng, color='#FF0000', c=None, title="no implementation"):
        if c:
            color = c
        color = self.color_dict.get(color, color)
        color = self.html_color_codes.get(color, color)
        self.points.append((lat, lng, color[1:], title))

    def scatter(self, lats, lngs, color=None, size=None, marker=True, c=None, s=None, symbol='o', **kwargs):
        color = color or c
        size = size or s or 40
        kwargs["color"] = color
        kwargs["size"] = size
        settings = self._process_kwargs(kwargs)
        for lat, lng in zip(lats, lngs):
            if marker:
                self.marker(lat, lng, settings['color'])
            else:
                self._add_symbol(Symbol(symbol, lat, lng, size), **settings)

    def _add_symbol(self, symbol, color=None, c=None, **kwargs):
        color = color or c
        kwargs.setdefault('face_alpha', 0.5)
        kwargs.setdefault('face_color', "#000000")
        kwargs.setdefault("color", color)
        settings = self._process_kwargs(kwargs)
        self.symbols.append((symbol, settings))

    def circle(self, lat, lng, radius, color=None, c=None, **kwargs):
        color = color or c
        kwargs.setdefault('face_alpha', 0.5)
        kwargs.setdefault('face_color', "#000000")
        kwargs.setdefault("color", color)
        settings = self._process_kwargs(kwargs)
        self.circles.append(((lat, lng, radius), settings))

    def _process_kwargs(self, kwargs):
        settings = dict()
        settings["edge_color"] = kwargs.get("color", None) or \
                                 kwargs.get("edge_color", None) or \
                                 kwargs.get("ec", None) or \
                                 "#000000"

        settings["edge_alpha"] = kwargs.get("alpha", None) or \
                                 kwargs.get("edge_alpha", None) or \
                                 kwargs.get("ea", None) or \
                                 1.0
        settings["edge_width"] = kwargs.get("edge_width", None) or \
                                 kwargs.get("ew", None) or \
                                 1.0
        settings["face_alpha"] = kwargs.get("alpha", None) or \
                                 kwargs.get("face_alpha", None) or \
                                 kwargs.get("fa", None) or \
                                 0.3
        settings["face_color"] = kwargs.get("color", None) or \
                                 kwargs.get("face_color", None) or \
                                 kwargs.get("fc", None) or \
                                 "#000000"

        settings["color"] = kwargs.get("color", None) or \
                            kwargs.get("c", None) or \
                            settings["edge_color"] or \
                            settings["face_color"]

        # Need to replace "plum" with "#DDA0DD" and "c" with "#00FFFF" (cyan).
        for key, color in settings.items():
            if 'color' in key:
                color = self.color_dict.get(color, color)
                color = self.html_color_codes.get(color, color)
                settings[key] = color

        settings["closed"] = kwargs.get("closed", None)
        return settings

    def plot(self, lats, lngs, color=None, c=None, **kwargs):
        color = color or c
        kwargs.setdefault("color", color)
        settings = self._process_kwargs(kwargs)
        path = zip(lats, lngs)
        self.paths.append((path, settings))

    def heatmap(self, lats, lngs, weight, threshold=10, radius=10, gradient=None, opacity=0.6, maxIntensity=1, dissipating=True):
        '''
        :param lats: list of latitudes
        :param lngs: list of longitudes
        :param maxIntensity:(int) max frequency to use when plotting. Default (None) uses max value on map domain.
        :param threshold:
        :param radius: The hardest param. Example (string):
        :return:
        '''
        settings = {}
        # Try to give anyone using threshold a heads up.
        if threshold != 10:
            warnings.warn("The 'threshold' kwarg is deprecated, replaced in favor of maxIntensity.")
        settings['threshold'] = threshold
        settings['radius'] = radius
        settings['gradient'] = gradient
        settings['opacity'] = opacity
        settings['maxIntensity'] = maxIntensity
        settings['dissipating'] = dissipating
        settings = self._process_heatmap_kwargs(settings)

        heatmap_points = []
        for lat, lng, weight in zip(lats, lngs, weight):
            heatmap_points.append((lat, lng, weight))
        self.heatmap_points.append((heatmap_points, settings))

    def _process_heatmap_kwargs(self, settings_dict):
        settings_string = ''
        settings_string += "{0}heatmap.set('threshold', {1});\n".format(self.indent(4), settings_dict['threshold'])
        settings_string += "{0}heatmap.set('radius', {1});\n".format(self.indent(4), settings_dict['radius'])
        settings_string += "{0}heatmap.set('maxIntensity', {1});\n".format(self.indent(4), settings_dict['maxIntensity'])
        settings_string += "{0}heatmap.set('opacity', {1});\n".format(self.indent(4), settings_dict['opacity'])

        dissipation_string = 'true' if settings_dict['dissipating'] else 'false'
        settings_string += "{0}heatmap.set('dissipating', {1});\n".format(self.indent(4), dissipation_string)

        gradient = settings_dict['gradient']
        if gradient:
            gradient_string = "var gradient = [\n"
            for r, g, b, a in gradient:
                gradient_string += "\t" + "'rgba(%d, %d, %d, %d)',\n" % (r, g, b, a)
            gradient_string += '];' + '\n'
            gradient_string += "{0}heatmap.set('gradient', gradient);\n".format(self.indent(4))

            settings_string += gradient_string

        return settings_string

    def ground_overlay(self, url, bounds_dict):
        '''
        :param url: Url of image to overlay
        :param bounds_dict: dict of the form  {'north': , 'south': , 'west': , 'east': }
        setting the image container
        :return: None
        Example use:
        import gmplot
        gmap = gmplot.GoogleMapPlotter(37.766956, -122.438481, 13)
        bounds_dict = {'north':37.832285, 'south': 37.637336, 'west': -122.520364, 'east': -122.346922}
        gmap.ground_overlay('http://explore.museumca.org/creeks/images/TopoSFCreeks.jpg', bounds_dict)
        gmap.draw("my_map.html")
        Google Maps API documentation
        https://developers.google.com/maps/documentation/javascript/groundoverlays#introduction
        '''

        bounds_string = self._process_ground_overlay_image_bounds(bounds_dict)
        self.ground_overlays.append((url, bounds_string))

    def _process_ground_overlay_image_bounds(self, bounds_dict):
        bounds_string = 'var imageBounds = {'
        bounds_string += "north:  %.4f,\n" % bounds_dict['north']
        bounds_string += "south:  %.4f,\n" % bounds_dict['south']
        bounds_string += "east:  %.4f,\n" % bounds_dict['east']
        bounds_string += "west:  %.4f};\n" % bounds_dict['west']

        return bounds_string

    def polygon(self, lats, lngs, color=None, c=None, **kwargs):
        color = color or c
        kwargs.setdefault("color", color)
        settings = self._process_kwargs(kwargs)
        shape = zip(lats, lngs)
        self.shapes.append((shape, settings))

    def draw(self, htmlfile):
        """Create the html file which include one google map and all points and paths. If 
        no string is provided, return the raw html.
        """
        f = open(htmlfile, 'w')
        f.write('<html>\n')
        f.write('<head>\n')
        f.write(self.indent()+
            '<meta name="viewport" content="initial-scale=1.0, user-scalable=no" />\n')
        f.write(self.indent()+
            '<meta http-equiv="content-type" content="text/html; charset=UTF-8"/>\n')
        f.write(self.indent()+'<title>Google Maps - gmplot </title>\n')
        f.write(self.indent())

        try:
            if self.data_external is True:
                f.write('{0}<script type="text/javascript" src="data.js"></script>\n'.format(self.indent()))
        except:
            pass
        
        if self.apikey:
            f.write('<script type="text/javascript" src="https://maps.googleapis.com/maps/api/js?libraries=visualization&sensor=true_or_false&key=%s"></script>\n' % self.apikey )
        else:
            f.write('<script type="text/javascript" src="https://maps.googleapis.com/maps/api/js?libraries=visualization&sensor=true_or_false"></script>\n' )
        
        f.write(self.indent()+'<script type="text/javascript">\n')
        # Make global scope variables
        self.write_global_vars(f)
        # Document.onload() function
        f.write(self.indent(2)+'function initialize() {\n')
        self.write_map(f)
        f.write(self.indent(3)+'googleMap = map;\n')    # set global var
        self.write_grids(f)
        self.write_points(f)
        self.write_paths(f)
        self.write_circles(f)
        self.write_symbols(f)
        self.write_shapes(f)
        if isinstance(self.heatmap_points, dict):
            self.write_heatmap_from_dictionary(f)
        else:
            self.write_heatmap(f)
        self.write_ground_overlay(f)
        self.write_final_initialization(f)
        f.write(self.indent(2)+'}\n')
        f.write('{0}</script>\n'.format(self.indent()))
        # specialized script
        self.write_event_handlers(f)
        f.write('</head>\n')
        f.write(
            '<body style="margin:0px; padding:0px;" onload="initialize()">\n')
        self.write_timeline_element(f)
        f.write(
            '\t<div id="map_canvas" style="width: 100%; height: 100%;"></div>\n')
        f.write('</body>\n')
        f.write('</html>\n')
        f.close()
        print("File creation completed!")

    def indent(self, tab_level=1):
        one_tab = ' ' * 4      # 4 spaces = 1 tab
        t = 0
        spaces = ""
        while t < tab_level:
            spaces = spaces + one_tab
            t += 1
        return spaces


    #############################################
    # # # # # # Low level Map Drawing # # # # # #
    #############################################

    def write_grids(self, f):
        if self.gridsetting is None:
            return
        slat = self.gridsetting[0]
        elat = self.gridsetting[1]
        latin = self.gridsetting[2]
        slng = self.gridsetting[3]
        elng = self.gridsetting[4]
        lngin = self.gridsetting[5]
        self.grids = []

        r = [
            slat + float(x) * latin for x in range(0, int((elat - slat) / latin))]
        for lat in r:
            self.grids.append(
                [(lat + latin / 2.0, slng + lngin / 2.0), (lat + latin / 2.0, elng + lngin / 2.0)])

        r = [
            slng + float(x) * lngin for x in range(0, int((elng - slng) / lngin))]
        for lng in r:
            self.grids.append(
                [(slat + latin / 2.0, lng + lngin / 2.0), (elat + latin / 2.0, lng + lngin / 2.0)])

        for line in self.grids:
            settings = self._process_kwargs({"color": "#000000"})
            self.write_polyline(f, line, settings)

    def write_points(self, f):
        for point in self.points:
            self.write_point(f, point[0], point[1], point[2], point[3])

    def write_circles(self, f):
        for circle, settings in self.circles:
            self.write_circle(f, circle[0], circle[1], circle[2], settings)

    def write_symbols(self, f):
        for symbol, settings in self.symbols:
            self.write_symbol(f, symbol, settings)

    def write_paths(self, f):
        for path, settings in self.paths:
            self.write_polyline(f, path, settings)

    def write_shapes(self, f):
        for shape, settings in self.shapes:
            self.write_polygon(f, shape, settings)

    # TODO: Add support for mapTypeId: google.maps.MapTypeId.SATELLITE
    def write_map(self,  f):
        f.write('{0}var centerlatlng = new google.maps.LatLng({1}, {2});\n'.format(
            self.indent(3), self.center[0], self.center[1])
        )
        f.write(self.indent(3)+'var myOptions = {\n')
        f.write('{0}zoom: {1},\n'.format(self.indent(4),self.zoom))
        f.write('{0}center: centerlatlng,\n'.format(self.indent(4)))
        f.write('{0}mapTypeId: google.maps.MapTypeId.ROADMAP\n'.format(self.indent(4)))
        f.write(self.indent(3)+'};\n')
        f.write(
            '{0}var map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);\n'.format(self.indent(3)))

    def write_point(self, f, lat, lon, color, title):
        f.write('\t\tvar latlng = new google.maps.LatLng(%f, %f);\n' %
                (lat, lon))
        f.write('\t\tvar img = new google.maps.MarkerImage(\'%s\');\n' %
                (self.coloricon % color))
        f.write('\t\tvar marker = new google.maps.Marker({\n')
        f.write('\t\ttitle: "%s",\n' % title)
        f.write('\t\ticon: img,\n')
        f.write('\t\tposition: latlng\n')
        f.write('\t\t});\n')
        f.write('\t\tmarker.setMap(map);\n')
        f.write('\n')

    def write_symbol(self, f, symbol, settings):
        strokeColor = settings.get('color') or settings.get('edge_color')
        strokeOpacity = settings.get('edge_alpha')
        strokeWeight = settings.get('edge_width')
        fillColor = settings.get('face_color')
        fillOpacity = settings.get('face_alpha')
        try:
            template = SYMBOLS[symbol.symbol]
        except KeyError:
            raise InvalidSymbolError("Symbol %s is not implemented" % symbol.symbol)

        f.write(template.format(lat=symbol.lat, long=symbol.long, size=symbol.size, strokeColor=strokeColor,
                                strokeOpacity=strokeOpacity, strokeWeight=strokeWeight,
                                fillColor=fillColor, fillOpacity=fillOpacity))

    def write_circle(self, f, lat, long, size, settings):
        strokeColor = settings.get('color') or settings.get('edge_color')
        strokeOpacity = settings.get('edge_alpha')
        strokeWeight = settings.get('edge_width')
        fillColor = settings.get('face_color')
        fillOpacity = settings.get('face_alpha')
        f.write(CIRCLE.format(lat=lat, long=long, size=size, strokeColor=strokeColor,
                              strokeOpacity=strokeOpacity, strokeWeight=strokeWeight,
                              fillColor=fillColor, fillOpacity=fillOpacity))

    def write_polyline(self, f, path, settings):
        clickable = False
        geodesic = True
        strokeColor = settings.get('color') or settings.get('edge_color')
        strokeOpacity = settings.get('edge_alpha')
        strokeWeight = settings.get('edge_width')

        f.write('var PolylineCoordinates = [\n')
        for coordinate in path:
            f.write('new google.maps.LatLng(%f, %f),\n' %
                    (coordinate[0], coordinate[1]))
        f.write('];\n')
        f.write('\n')

        f.write('var Path = new google.maps.Polyline({\n')
        f.write('clickable: %s,\n' % (str(clickable).lower()))
        f.write('geodesic: %s,\n' % (str(geodesic).lower()))
        f.write('path: PolylineCoordinates,\n')
        f.write('strokeColor: "%s",\n' % (strokeColor))
        f.write('strokeOpacity: %f,\n' % (strokeOpacity))
        f.write('strokeWeight: %d\n' % (strokeWeight))
        f.write('});\n')
        f.write('\n')
        f.write('Path.setMap(map);\n')
        f.write('\n\n')

    def write_polygon(self, f, path, settings):
        clickable = False
        geodesic = True
        strokeColor = settings.get('edge_color') or settings.get('color')
        strokeOpacity = settings.get('edge_alpha')
        strokeWeight = settings.get('edge_width')
        fillColor = settings.get('face_color') or settings.get('color')
        fillOpacity= settings.get('face_alpha')
        f.write('var coords = [\n')
        for coordinate in path:
            f.write('new google.maps.LatLng(%f, %f),\n' %
                    (coordinate[0], coordinate[1]))
        f.write('];\n')
        f.write('\n')

        f.write('var polygon = new google.maps.Polygon({\n')
        f.write('clickable: %s,\n' % (str(clickable).lower()))
        f.write('geodesic: %s,\n' % (str(geodesic).lower()))
        f.write('fillColor: "%s",\n' % (fillColor))
        f.write('fillOpacity: %f,\n' % (fillOpacity))
        f.write('paths: coords,\n')
        f.write('strokeColor: "%s",\n' % (strokeColor))
        f.write('strokeOpacity: %f,\n' % (strokeOpacity))
        f.write('strokeWeight: %d\n' % (strokeWeight))
        f.write('});\n')
        f.write('\n')
        f.write('polygon.setMap(map);\n')
        f.write('\n\n')

    def write_heatmap(self, f):
        for heatmap_points, settings_string in self.heatmap_points:
            f.write('var heatmap_points = [\n')
            for heatmap_lat, heatmap_lng, heatmap_weight in heatmap_points:
                f.write('{location: new google.maps.LatLng(%f, %f),weight:%f},\n' %
                        (heatmap_lat, heatmap_lng, heatmap_weight))
            f.write('];\n')
            f.write('\n')
            f.write('var pointArray = new google.maps.MVCArray(heatmap_points);' + '\n')
            f.write('var heatmap;' + '\n')
            f.write('heatmap = new google.maps.visualization.HeatmapLayer({' + '\n')
            f.write('\n')
            f.write('data: pointArray' + '\n')
            f.write('});' + '\n')
            f.write('heatmap.setMap(map);' + '\n')
            f.write(settings_string)

    def write_heatmap_from_dictionary(self, f):
        ''' creates multiple heatmap variables per key provided
            where the value is an array of point dictionaries.
            A point dictionary has 3 keys:
             1. Latitude, 2. Longitude, 3. weight
        '''
        if not isinstance(self.heatmap_points, dict):
            raise TypeError('Heatmap Points is not a dictionary.')
        
        try:
            if self.data_external is not True:
                raise Error('go to exception')
        except:
            f.write('var dataPointsByMonth = '+json.dumps(self.heatmap_points, indent=4)+';\n')

        # Generate Heatmaps with indexing that matches range values, in numerical order
        f.write(self.indent(3)+'var timestamps = Object.keys(dataPointsByMonth).sort((a, b) => Number(a) < Number(b));\n')
        f.write(self.indent(3)+'for (var i = 0; i < timestamps.length; i++) {\n')
        f.write(self.indent(4) + 'var monthData = dataPointsByMonth[timestamps[i]];\n')
        f.write(self.indent(4) + 'var heatmap_points = new Array();\n')
        f.write('\n')
        f.write(self.indent(4) + 'for ( var p in monthData ) {\n')
        f.write(self.indent(5)  +  'var datapt = monthData[p];\n')
        f.write(self.indent(5)  +  'heatmap_points.push({\n')
        f.write(self.indent(6)   +   'location: new google.maps.LatLng(datapt.Latitude, datapt.Longitude),\n')
        f.write(self.indent(6)   +   'weight: datapt.weight\n')
        f.write(self.indent(5)  +  '})\n')
        f.write(self.indent(4) + '}\n')
        f.write('\n')
        f.write(self.indent(4) + 'var heatmap = new google.maps.visualization.HeatmapLayer({\n')
        f.write(self.indent(5)   +   'data: new google.maps.MVCArray(heatmap_points)\n')
        f.write(self.indent(4) + '});\n')
        f.write(self.settings_string if self.settings_string is not None else '\n')
        f.write('\n')
        f.write(self.indent(4) + 'heatmapStorage[i] = { "timestamp": timestamps[i], "kml": heatmap };\n')
        f.write(self.indent(3)+'}\n')

    def write_ground_overlay(self, f):
        for url, bounds_string in self.ground_overlays:
            f.write(bounds_string)
            f.write('var groundOverlay;' + '\n')
            f.write('groundOverlay = new google.maps.GroundOverlay(' + '\n')
            f.write('\n')
            f.write("'" + url + "'," + '\n')
            f.write('imageBounds);' + '\n')
            f.write('groundOverlay.setMap(map);' + '\n')

    def write_global_vars(self, f):
        f.write(self.indent(2)+'var googleMap;\n')
        f.write(self.indent(2)+'var heatmapStorage = [];\n')
        f.write(self.indent(2)+'var currentHeatMap;\n')

    def write_final_initialization(self, f):
        '''
        '''
        # Finally set the initial heatmap visual by automatically calling event propogation
        f.write(self.indent(3)+'var timelineElement = document.getElementById("timeline-date-selector");\n')
        # Set event handler
        f.write(self.indent(3)+'timelineElement.addEventListener("input", onTimelineInputChange);\n')
        # default
        f.write(self.indent(3)+'timelineElement.value = Math.floor(heatmapStorage.length / 2)\n')
        # create input event
        f.write(self.indent(3)+'timelineElement.dispatchEvent(\n')
        f.write(self.indent(4) + 'new Event("input", {\n')
        f.write(self.indent(5)  +  '"bubbles": true,\n')
        f.write(self.indent(5)  +  '"cancelable": true\n')
        f.write(self.indent(4) + '})\n')
        f.write(self.indent(3)+');\n')

    def write_timeline_element(self, f):
        '''
        '''
        if not isinstance(self.heatmap_points, dict):
            return()

        f.write(self.indent(1)+'<div style="text-align: center; padding: 0.5em 1em;">\n')
        f.write(self.indent(2)+'<div style="font-weight: bold;" id="timeline-selected-date">Feb 1, 1980</div>\n')
        f.write(self.indent(2)+'<input id="timeline-date-selector"\n')
        f.write(self.indent(3) + 'type="range"\n')
        f.write(self.indent(3) + 'min="0"\n')
        f.write(self.indent(3) + 'max="{0}"\n'.format(len(self.heatmap_points.keys())-1))
        f.write(self.indent(3) + 'step="1"\n')
        f.write(self.indent(3) + 'list="timelineTickmarks"\n')
        f.write(self.indent(3) + 'style="width:100%; display:block;"\n')
        f.write(self.indent(2)+'/>\n')
        f.write(self.indent(2)+'<datalist id="timelineTickmarks" style="display: inline-flex;">\n')
        t = 0
        while t < len(self.heatmap_points.keys()):
            if t % 120 == 0:
                timestamp = list(self.heatmap_points.keys())[t]
                f.write(self.indent(3)+'<option value="{0}" label="{1}"></option>\n'.format(t, datetime.datetime.fromtimestamp(int(float(timestamp))/1000).strftime('%Y')))
            elif t % 12 == 0:
                f.write(self.indent(3)+'<option value="{0}"></option>\n'.format(t))
            else:
                pass
            t += 1
        
        f.write(self.indent(2)+'</datalist>\n')
        f.write(self.indent()+'</div>\n')

    def write_event_handlers(self, f):
        '''
        '''
        f.write(self.indent()+'<script type="text/javascript">\n')
        f.write(self.indent(2)+'function onTimelineInputChange(e) {\n')
        f.write(self.indent(3) + 'changeHeatMap(e);\n')
        f.write(self.indent(3) + 'updateSelectedDate(e);\n')
        f.write(self.indent(2)+'}\n')
        f.write(self.indent(2)+'function updateSelectedDate(e) {\n')
        f.write(self.indent(3) + 'var dateDisplay = document.getElementById("timeline-selected-date");\n')
        f.write(self.indent(3) + 'var dateObj = new Date(Number(heatmapStorage[Number(e.target.value)].timestamp));\n')
        f.write(self.indent(3) + 'dateDisplay.innerText = dateObj.toDateString().replace(/^[^ ]*[ ]/, "").replace(/^([A-Za-z]* [0-9]+) ([0-9]{4})$/,"$1, $2");\n')
        f.write(self.indent(2)+'}\n')
        f.write(self.indent(2)+'function changeHeatMap(e) {\n')
        f.write(self.indent(3) + 'if (currentHeatMap != null) currentHeatMap.setMap();		    // Reset previous map reference\n')
        f.write(self.indent(3) + 'currentHeatMap = heatmapStorage[Number(e.target.value)].kml;	// Change to new heatmap\n')
        f.write(self.indent(3) + 'currentHeatMap.setMap(googleMap);								// apply to Maps window\n')
        f.write(self.indent(2)+'}\n')
        f.write(self.indent()+'</script>\n')

if __name__ == "__main__":

    mymap = GoogleMapPlotter(37.428, -122.145, 16)
    # mymap = GoogleMapPlotter.from_geocode("Stanford University")

    mymap.grid(37.42, 37.43, 0.001, -122.15, -122.14, 0.001)
    mymap.marker(37.427, -122.145, "yellow")
    mymap.marker(37.428, -122.146, "cornflowerblue")
    mymap.marker(37.429, -122.144, "k")
    lat, lng = mymap.geocode("Stanford University")
    mymap.marker(lat, lng, "red")
    mymap.circle(37.429, -122.145, 100, "#FF0000", ew=2)
    path = [(37.429, 37.428, 37.427, 37.427, 37.427),
             (-122.145, -122.145, -122.145, -122.146, -122.146)]
    path2 = [[i+.01 for i in path[0]], [i+.02 for i in path[1]]]
    path3 = [(37.433302 , 37.431257 , 37.427644 , 37.430303), (-122.14488, -122.133121, -122.137799, -122.148743)]
    path4 = [(37.423074, 37.422700, 37.422410, 37.422188, 37.422274, 37.422495, 37.422962, 37.423552, 37.424387, 37.425920, 37.425937),
         (-122.150288, -122.149794, -122.148936, -122.148142, -122.146747, -122.14561, -122.144773, -122.143936, -122.142992, -122.147863, -122.145953)]
    mymap.plot(path[0], path[1], "plum", edge_width=10)
    mymap.plot(path2[0], path2[1], "red")
    mymap.polygon(path3[0], path3[1], edge_color="cyan", edge_width=5, face_color="blue", face_alpha=0.1)
    mymap.heatmap(path4[0], path4[1], threshold=10, radius=40)
    mymap.heatmap(path3[0], path3[1], threshold=10, radius=40, dissipating=False, gradient=[(30,30,30,0), (30,30,30,1), (50, 50, 50, 1)])
    mymap.scatter(path4[0], path4[1], c='r', marker=True)
    mymap.scatter(path4[0], path4[1], s=90, marker=False, alpha=0.9, symbol='x', c='red', edge_width=4)
    # Get more points with:
    # http://www.findlatitudeandlongitude.com/click-lat-lng-list/
    scatter_path = ([37.424435, 37.424417, 37.424417, 37.424554, 37.424775, 37.425099, 37.425235, 37.425082, 37.424656, 37.423957, 37.422952, 37.421759, 37.420447, 37.419135, 37.417822, 37.417209],
                    [-122.142048, -122.141275, -122.140503, -122.139688, -122.138872, -122.138078, -122.137241, -122.136405, -122.135568, -122.134731, -122.133894, -122.133057, -122.13222, -122.131383, -122.130557, -122.129999])
    mymap.scatter(scatter_path[0], scatter_path[1], c='r', marker=True)
    mymap.draw('./mymap.html')
