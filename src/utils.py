# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 08:32:05 2015

Utility functions used in the Tetrad Automated Forecasting Runs Scripts

@author: abrasaldo.pmb
"""

from iapws import IAPWS97
import numpy as np
import pandas as pd

def hL_T(temp):
    if not pd.isnull(temp):
        temp = temp + 273.15
        return IAPWS97(T=temp,x=0).h
    else: return np.nan

def hV_T(temp):
    if not pd.isnull(temp):
        temp = temp + 273.15
        return IAPWS97(T=temp,x=1).h
    else: return np.nan
        
def hL_P(p):
    if not pd.isnull(p):
        return IAPWS97(P=p,x=0).h
    else: 
        return np.nan
def hV_P(p):
    if not pd.isnull(p):
        return IAPWS97(P=p,x=1).h
    else: 
        return np.nan