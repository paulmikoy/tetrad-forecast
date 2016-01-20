# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 08:37:45 2015

Classes used in the Tetrad Automated Forecasting Runs Scripts

@author: abrasaldo.pmb
"""

import pandas as pd

class ProductionWell(object):
    
    def __init__(self, name, rate, is_online, start_year, plant):
        self.name = name
        self.rate = rate
        self.is_online = is_online
        self.start_year = start_year
        self.plant = plant

class Plant(object):
    
    def __init__(self, name, separator_pressure, min_steam_flow, 
                 brine_enthalpy, condensate_enthalpy, condensate_fraction, steam_target):
        self.name = name
        self.separator_pressure = separator_pressure
        self.min_steam_flow = min_steam_flow
        self.brine_enthalpy = brine_enthalpy
        self.condensate_enthalpy = condensate_enthalpy
        self.condensate_fraction = condensate_fraction
        self.steam_target = steam_target
        
class Period(object):
    
    def __init__(self, number, length):
        self.number = number
        self.length = length

class ForecastControl(object):
    
    def __init__(self, filename='ForecastControl.xlsx'):
        self.filename = filename
        self.prod_wells = self.ReadProductionWells()
        self.plants = self.ReadPlants()
        self.periods = self.ReadPeriods()
        
    def ReadProductionWells(self):
        df = pd.read_excel(self.filename, sheetname='Production Wells')
        prod_wells = []
        for row in range(max(df.index)+1):
            rd = df.loc[row]
            prod_wells.append(ProductionWell(rd[0], rd[1], rd[2], rd[3], rd[4]))
        return prod_wells
    
    def ReadPlants(self):
        df = pd.read_excel(self.filename, sheetname='Plants')
        plants = []
        for row in range(max(df.index)+1):  
            rd = df.loc[row]
            plants.append(Plant(rd[0], rd[1], rd[2], rd[3], rd[4], rd[5], rd[6]))
        return plants
    
    def ReadPeriods(self):
        df = pd.read_excel(self.filename, sheetname='Periods')
        periods = []
        for row in range(max(df.index)+1):
            rd = df.loc[row][0:6]
            if rd[0] > 1:
                for i in range(0, int(rd[0])):
                    periods.append(Period(1, rd[1]))
            else:
                periods.append(Period(rd[0], rd[1]))
        return periods

if __name__ == '__main__':
    control = ForecastControl('ForecastControl.xlsx')
    print 'Hello'