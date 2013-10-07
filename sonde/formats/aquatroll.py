"""
    sonde.formats.aquatroll
    ~~~~~~~~~~~~~~~~~

    This module implements the aquatroll format
    There are two main aquatroll formats 
    the files may be in xlsx or csv
    The module attempts to autodetect the correct format

"""
from __future__ import absolute_import

import csv
import datetime
import os.path
import pkg_resources
import re
from StringIO import StringIO
import warnings
import xlrd

import numpy as np

from .. import sonde
from .. import quantities as sq

from ..timezones import cdt, cst
# from .. 

from sonde import util
# from sonde import quantities as sq
import quantities as pq

# class BadDatafileError(IOError):
#     pass


class AquatrollDataset(sonde.BaseSondeDataset):
    """
    Dataset object that represents the data contained in a Aquatroll
    file. It accepts two optional parameters, `format` overides the
    autodetect algorithm that tries to detect the format automatically
    `tzinfo` is a datetime.tzinfo object that represents the timezone
    of the timestamps in the binary file.
    """

    def __init__(self, data_file, tzinfo=None):
        self.file_format = 'aquatroll'
        self.manufacturer = 'aquatroll'
        self.data_file = data_file
        self.default_tzinfo = tzinfo
        self.data = {}
        self.dates = []
        super(AquatrollDataset, self).__init__(data_file)

    def _read_data(self):
        """
        Read the Aquatroll data file
        """
        param_map = {'Temperature': 'water_temperature',
                     'Specific Conductivity': 'water_specific_conductance', 
                     'Salinity': 'seawater_salinity',
                     'Water Density': 'water_density',
                     'Resistivity': 'water_resistivity',
                     'Total Dissolved Solids': 'water_total_dissolved_salts',
                     'Actual Conductivity': 'water_electrical_conductivity',
                     
                     }

        unit_map = {'deg_C': pq.degC,
                    'Celcius': pq.degC,
                    'Celsius': pq.degC,
                    'deg_F': pq.degF,
                    'deg_K': pq.degK,
                    'ft': sq.ftH2O,
                    'mS/cm': sq.mScm,
                    'mg/l': sq.mgl,
                    'm': sq.mH2O,
                    'Metres': sq.mH2O,
                    'ppm': sq.mgl,
                    'psu': sq.psu,
                    'us/cm': sq.uScm,
                    'uS/cm': sq.uScm,
                    'volts': pq.volt,
                    'Volts': pq.volt,
                    'volt': pq.volt,
                    'xb5S': sq.uScm,
                    'p':sq.mgl, # dbl check.. 
                    '': pq.dimensionless,
#                     'ohm-cm':      #adding to master param list
#                     'kg/m3' //water density
#                    water resistivity
                
                    }

        aquatroll_data = AquatrollReader(self.data_file, self.default_tzinfo)

        # determine parameters provided and in what units
        self.parameters = {}
#         self.data = {}
        for parameter in aquatroll_data.parameters:
            try:
                pcode = param_map[(parameter.name).strip()]
                punit = unit_map[(parameter.unit).strip()]
                #ignore params that have no data
                if not np.all(np.isnan(parameter.data)):
                    self.parameters[pcode] = sonde.master_parameter_list[pcode]
                    self.data[param_map[parameter.name]] = parameter.data * \
                                                           punit
            except KeyError:
                warnings.warn('Un-mapped Parameter/Unit Type:\n'
                              '%s parameter name: "%s"\n'
                              '%s unit name: "%s"' %
                              (self.file_format, parameter.name,
                               self.file_format, parameter.unit),
                              Warning)

        self.format_parameters = {
                'header_lines': aquatroll_data.header_lines,
                }
        if hasattr(aquatroll_data, 'site_name'):
            self.site_name = aquatroll_data.site_name
        if hasattr(aquatroll_data, 'serial_number'):
            self.serial_number = aquatroll_data.serial_number
        if hasattr(aquatroll_data, 'setup_time'):
            self.setup_time = aquatroll_data.setup_time
        if hasattr(aquatroll_data, 'stop_time'):
            self.stop_time = aquatroll_data.stop_time

        self.dates = aquatroll_data.dates


class AquatrollReader:
    """
    A reader object that opens and reads a aquatroll txt file.

    `data_file` should be either a file path string or a file-like
    object. It accepts one optional parameter, `tzinfo` is a
    datetime.tzinfo object that represents the timezone of the
    timestamps in the txt file.
    """

    def __init__(self, data_file, tzinfo=None):
        self.default_tzinfo = tzinfo
        self.header_lines = []
        self.num_params = 0
        self.parameters = []
        self.data = {}
        self.dates = []
        self.site_name =''
        if type(data_file) == str:
            self.file_name = data_file
        elif type(data_file) == file:
            self.file_name = data_file.name
        self.file_ext = self.file_name.split('.')[-1].lower()
        
        
        temp_file_path = None
        if self.file_ext == 'xlsx':
            #handling xlsx file
            temp_file_path, self.xlrd_datemode = util.xls_to_csv(
                self.file_name)
            file_buf = open(temp_file_path, 'rb')
        else:
            if type(data_file) == str:
                file_buf = open(data_file)
            elif type(data_file) == file:
                file_buf = data_file

        try:
            self.read_aquatroll(file_buf)
        except:
            raise
        finally:
            if type(data_file) == str:
                file_buf.close()
            if temp_file_path:
                os.remove(temp_file_path)

        if tzinfo:
            if hasattr(self, 'setup_time'):
                self.setup_time = self.setup_time.replace(tzinfo=tzinfo)
            if hasattr(self, 'stop_time'):
                self.stop_time = self.stop_time.replace(tzinfo=tzinfo)

            self.dates = [i.replace(tzinfo=tzinfo) for i in self.dates]


    
    def time_convert(self, in_time):
        #convert to YYYYMMSS format 
        pass


    def read_aquatroll(self, data_file):
        """
        Open and read a aquatroll file.
        """
        if type(data_file) == str:
            fid = open(data_file, 'r')
        else:
            fid = data_file

        self.read_data(fid)

    def read_data(self, fid):
        """
        Read header information
        """
        fid.seek(0)
        buf = fid.readline()
#         while buf:
#             if buf[0:21] == 'Date and Time,Seconds':
#                 fields = buf.strip('\r\n').split(',')
#                 params = [p.strip(' ') for p in fields[2:]]
#                 units = []
#                 for u in params:
#                     if u[-1:] == ')':
#                         units.append(u[u.find('(')+1:u.find(')')])
#                     else: 
#                         units.append(u[u.find('(')+1:])
#                 break
        while buf[0:21] != 'Date and Time,Seconds':
            buf = fid.readline()
        fields = buf.strip('\r\n').split(',')
        params = [p.strip(' ') for p in fields[2:]]
        units = []
        for u in params:
            if u[-1:] == ')':
                units.append(u[u.find('(')+1:u.find(')')])
            else: 
                units.append(u[u.find('(')+1:])

        date = []
        time = []
        data = np.genfromtxt(fid, delimiter=',', dtype=None, names=fields)
        for dt in data['Date_and_Time']:
            date.append(dt.split(' ')[0])
            time.append(dt.split(' ')[1])
      
        self.dates = np.array(
                    [datetime.datetime.strptime(d+t, '%m/%d/%Y%H:%M:%S')
                     for d, t in zip(date, time)]
                    )
        for param, unit in zip(params, units):
            self.parameters.append(Parameter(param.strip(), unit.strip()))
            
#         for ii in range(len(self.parameters)):
#                 param = (self.parameters[ii].name).strip(' .').replace(' ', '_')
#                 self.parameters[ii].data = data[param]    
        for ii in range(self.num_params):
                self.parameters[ii].data = data[:, ii]

class Parameter:
    """
    Class that implements the a structure to return a parameters
    name, unit and data
    """

    def __init__(self, param_name, param_unit):
        self.name = param_name
        self.unit = param_unit
        self.data = []
