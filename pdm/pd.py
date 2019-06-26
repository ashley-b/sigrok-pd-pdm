##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2019 Ashley Brighthope <ashley.b@reddegrees.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

'''
PDM PD.
'''

import sigrokdecode as srd
import scipy.signal
import struct

class State:

    def __init__(self, order, decimate):
        self.filterOrder = order
        self.samples = []
        self.decimate = decimate
        self.startSampleNum = None
        self.out = 0.0

    def push(self, sampleNum, x):
        if (len(self.samples) == 0):
            self.startSampleNum = sampleNum
        
        self.samples.append(x)
        if (len(self.samples) != self.decimate):
            return False
        
        self.out = scipy.signal.decimate(self.samples, self.decimate, self.filterOrder, 'fir')
        self.samples.clear()
        
        return True

    def get(self):
        return self.out
    
    def getStartSampleNum(self):
        return self.startSampleNum

class Decoder(srd.Decoder):
    api_version = 3
    id = 'pdm'
    name = 'PDM'
    longname = 'Pulse-density modulation'
    desc = 'Demodulated Pulse-density modulation'
    license = 'gplv2+'

    inputs = ['logic']
    outputs = []
    channels = (
        {'id': 'clk', 'name': 'Clock', 'desc': 'Clock line'},
        {'id': 'dat', 'name': 'Data',  'desc': 'Data line'},
    )
    options = (
        { 'id': 'order',    'desc': 'Filter Order', 'default': 'Default', 'values': tuple(['Default'] + ["%i" % x for x in range(2, 201*20) ]) },
        { 'id': 'decimate', 'desc': 'Decimate',     'default': 10, 'values': tuple(range(2, 201)) },
    )
    annotations = (
        ('left_bit',    'L Bit'),
        ('left_value',  'L Amplitude'),
        ('right_bit',   'R Bit'),
        ('right_value', 'R Amplitude'),
    )
    annotation_rows = tuple((u,v,(i,)) for i,(u,v) in enumerate(annotations))
    
    binary = (
        ('left_bit',    'L Bit'),
        ('left_value',  'L Amplitude'),
        ('right_bit',   'R Bit'),
        ('right_value', 'R Amplitude'),
    )

    def __init__(self):
        pass
        self.samplerate = None # None -> no timing output

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def reset(self):
        self.samplenum = -1

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.out_binary = self.register(srd.OUTPUT_BINARY)
#        self.out_meta = self.register(srd.OUTPUT_META)

        filterOrder = None if self.options['order']=='Default' else int(self.options['order'])
        self.state = [ State(filterOrder, self.options['decimate']) for i in range(2) ]

    def decode(self):
        # We want all CLK changes.
        wait_cond = [{0: 'e'}]
        lastSampleNum = [-1]*2
        lastDataBit = [False]*2
        lastDecimateValue = [False]*2
        while True:
            (clk, data) = self.wait(wait_cond)
            
            if lastDecimateValue[clk]:
                offset = 2 * clk
                startSampleNum = self.state[clk].getStartSampleNum()
                out = self.state[clk].get()
                self.put( startSampleNum, self.samplenum, self.out_ann, [offset+1, ['%0.3f' % out ] ])
                self.put( startSampleNum, self.samplenum, self.out_binary, [offset+1, struct.pack('<f', out)] )
            
            offset = 2 * clk
            if lastSampleNum[clk] >= 0:
                self.put( lastSampleNum[clk], self.samplenum, self.out_ann, [offset, [ '1' if lastDataBit[clk] else '0' ] ])
                self.put( lastSampleNum[clk], self.samplenum, self.out_binary, [offset, struct.pack('<b', 1 if lastDataBit[clk] else -1)] )
            
            lastDecimateValue[clk] = self.state[clk].push(self.samplenum, 1.0 if data else -1.0)
            
            lastSampleNum[clk] = self.samplenum
            lastDataBit[clk] = data
