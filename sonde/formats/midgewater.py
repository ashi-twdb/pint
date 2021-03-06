"""
    sonde.formats.midgewater
    ~~~~~~~~~~~~~~~~~

    This module implements a midgewater format.
    The files are in .txt format and must conform to the
    following guidelines
    comments and metadata at top of file in the format:
      # name: value
    a timezone field: (UTC-?, the data must all be in one UTC offset)
      # timezone: UTC-6 ?
    a fill_value field:
      # fill_value = -9.99
    the last two comment/header lines should be the following
    parameter header prepended by single #:
      #yyyy,mm,dd,HH,MM,temperature,ph,conductivity,salinity, etc
      (datetime must be 5 field and in format yyyy mm dd HH MM)
      (parameter names must be from master_param_list
    unit header prepended by single #:
      yyyy mm dd HH MM, C,nd, mmho, ppt, etc
      (units must be from supported_units_list)

    space separated data

    special columns or header items:
        original_data_file_name, instrument_manufacturer,
          instrument_serial_number
        if these exist they will overide self.manufacturer,
        self.data_file and self.serial_number

"""
from __future__ import absolute_import

import csv
import datetime
import pkg_resources
import re
from StringIO import StringIO
import warnings
import xlrd

import numpy as np
import quantities as pq


from .. import sonde
from .. import quantities as sq
from ..timezones import UTCStaticOffset

import pdb


class MidgewaterDataset(sonde.BaseSondeDataset):
    """
    Dataset object that represents the data contained in 'midgewater' txt
    file.
    """
    def __init__(self, data_file, tzinfo=None):
        self.manufacturer = 'na'
        self.file_format = 'midgewater'
        self.data_file = data_file
        self.default_tzinfo = tzinfo
        super(MidgewaterDataset, self).__init__(data_file)

    def _read_data(self):
        """
        Read the sonde data file
        """
        param_map = {'Temperature': 'water_temperature',
             'pH': 'water_ph',
             'Conductivity': 'water_electrical_conductivity',
             'Salinity': 'seawater_salinity',
             'DO': 'water_dissolved_oxygen_concentration',
             'WaterLevel': 'water_depth_non_vented',
             'Turbidity': 'water_turbidity',
             'DOSat': 'water_dissolved_oxygen_percent_saturation',
             'Battery': 'instrument_battery_voltage',
             }

        unit_map = {'C': pq.degC,
                    'mmho': sq.mScm,
                    '%': pq.percent,
                    'mg/l': sq.mgl,
                    'nd': pq.dimensionless,
                    'm': sq.mH2O,
                    'volts': pq.volt,
                    'ppt': sq.psu,
                    'ntu': sq.ntu
                    }

        midgewater_data = MidgewaterDataReader(
            self.data_file, tzinfo=self.default_tzinfo)
        self.parameters = dict()
        self.data = dict()
        metadata = dict()

        for parameter in midgewater_data.parameters:
            try:
                pcode = param_map[(parameter.name).strip()]
                punit = unit_map[(parameter.unit).strip()]
                # quick and dirty nan check: if all data values are
                # nans, then we can exclude them
                if not np.isnan(np.nansum(parameter.data)):
                    self.parameters[pcode] = sonde.master_parameter_list[pcode]
                    self.data[param_map[parameter.name]] = parameter.data * punit

            except KeyError:
                warnings.warn('Un-mapped Parameter/Unit Type:\n'
                              '%s parameter name: "%s"\n'
                              '%s unit name: "%s"' %
                              (self.file_format, parameter.name,
                               self.file_format, parameter.unit),
                              Warning)
            else:
                metadata[parameter.name.lower()] = parameter.data

        try:
            self.site_name = midgewater_data.site_name
        except AttributeError:
            pass

        #overide default metadata if present in file
        names = ['manufacturer', 'data_file', 'serial_number']
        kwds = ['instrument_manufacturer', 'original_data_file',
                'instrument_serial_number']
        for name, kwd in zip(names, kwds):
            #check format_parameters
            idx = [i for i
                   in self.format_parameters.keys() if i.lower() == kwd]
            if idx != []:
                exec('self.' + name + '=self.format_parameters[idx[0]]')
            idx = [i for i in metadata.keys() if i.lower() == kwd]
            if idx != []:
                exec('self.' + name + ' = metadata[idx[0]]')

        self.dates = midgewater_data.dates


class MidgewaterDataReader:
    """
    A reader object that opens and reads wq files processed with older script.

    `data_file` should be either a file path string or a file-like
    object. It accepts one optional parameter, `tzinfo` is a
    datetime.tzinfo object that represents the timezone of the
    timestamps in the txt file.
    """
    def __init__(self, data_file, tzinfo=None):
        self.num_params = 0
        self.parameters = []
        self.format_parameters = {}
        self.default_tzinfo = tzinfo
        self.read_midgewater(data_file)

    def read_midgewater(self, data_file):
        """
        Open and read a MW file.
        """
        if type(data_file) == str:
            fid = open(data_file, 'r')

        else:
            fid = data_file

        buf = fid.readline()
        while buf.find('#') == 0:
            if '# Station Name' in buf:
                self.site_name = buf.lstrip('# Station Name:').strip()

            if '# NODATA Value =' in buf:
                no_data_value = buf.lstrip('# NODATA Value = ').strip()

            buf = fid.readline()

        fid.seek(0)

        params = ['Temperature', 'pH', 'Conductivity', 'Salinity', 'DO',
                  'WaterLevel', 'Turbidity','DOSat','Battery']
        units = ['C', 'nd', 'mmho', 'ppt', 'mg/l', 'm', 'ntu', '%', 'volts']
        dtype = [('year', '<i4'), ('month', '<i4'), ('day','<i4'),
                 ('hour', '<i4'), ('minute', '<i4'), (params[0],'<f8'),
                 (params[1],'<f8'), (params[2],'<f8'),(params[3], '<f8'),
                 (params[4], '<f8'), (params[5], '<f8'), (params[6], '<f8'),
                 (params[7], '<f8'), (params[8], '<f8')]

        null_handler = lambda v: float(v) if v != no_data_value else None
        converter_dict = dict([(i, null_handler) for i in range(14)])
        data = np.genfromtxt(fid, dtype=dtype, comments='#',
                             usecols=range(14),
                             converters=converter_dict)

        self.dates = np.array([datetime.datetime(year=y, month=m, day=d,
                                                 hour=hh, minute=mm,
                                                 tzinfo=self.default_tzinfo)
                               for y, m, d, hh, mm
                               in zip(data['year'], data['month'],
                                      data['day'], data['hour'],
                                      data['minute'])])

        #assign param & unit names
        for param, unit in zip(params, units):
            self.num_params += 1
            self.parameters.append(Parameter(param.strip(), unit.strip()))

        for ii in range(self.num_params):
            param = self.parameters[ii].name
            self.parameters[ii].data = data[param]


class Parameter:
    """
    Class that implements the a structure to return a parameters
    name, unit and data
    """
    def __init__(self, param_name, param_unit):
        self.name = param_name
        self.unit = param_unit
        self.data = []
