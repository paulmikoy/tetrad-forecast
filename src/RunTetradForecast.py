# -*- coding: utf-8 -*-
"""
Created on Tue Dec 15 11:48:48 2015

@author: abrasaldo.pmb
"""

import pandas as pd
from subprocess import Popen
import shutil as sh
import numpy as np
import pyTETRAD
import os
import logging
import time

# custom modules
from classes import *
from utils import *

# Instantiate loggers
logger = logging.getLogger('forecast')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('forecast.log')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)

def process_outfile(outfile, write_to_file=False, historyfile='History.xlsx', gridfile='Grid.xlsx'):
    """This function is used to extract data from a TETRAD output file. Replaces History.xlsx"""
    grid=pd.read_excel(gridfile)
    outf = pyTETRAD.TetradOut(outfile)
    historydf=pd.DataFrame(columns=["Time"])
    
    for i, time in enumerate(outf.recur_times):
        dftemp = outf.read_well_table().reset_index()
        dftemp.insert(0,"Time",time)
        historydf = historydf.append(dftemp)
        outf.next()
    
    # Addition of columns for flow calculations
    historydf=historydf.merge(grid, left_on="BLOCK", right_on="Block")
    historydf["Dryness"]=historydf["MASS FLOW STEAM"]/(historydf["MASS FLOW STEAM"]+historydf["MASS FLOW WATER"])
    h_water=historydf["ENERGY FLOW WATER"]/historydf["MASS FLOW WATER"]*1000
    h_steam=historydf["ENERGY FLOW STEAM"]/historydf["MASS FLOW STEAM"]*1000
    historydf["MASS FLOW TOTAL"]=historydf["MASS FLOW WATER"]+historydf["MASS FLOW STEAM"]
    h_water_static = historydf['T'].apply(hL_T)
    h_steam_static = historydf['T'].apply(hV_T)
    historydf["H STATIC"]=h_water_static+historydf["Dryness"]*(h_steam_static-h_water_static)
    historydf.loc[historydf["Dryness"]==1,'H STATIC'] = h_steam_static
    historydf.loc[historydf["Dryness"]==0,'H STATIC'] = h_water_static
    historydf["H"]=h_water+historydf["Dryness"]*(h_steam-h_water)
    historydf.loc[historydf["Dryness"]==1,'H'] = h_steam
    historydf.loc[historydf["Dryness"]==0,'H'] = h_water

    historydf.set_index("Time")
    
    if write_to_file:
        historydf.to_excel(historyfile)
    
    return historydf
    

def CalculateSeparatedSteamFlow(results, control):
    """Calculated the steam flow seaprated per feed zone contribution.
    
    Calculation of steam flow is based on separator pressure per plant.
    
    Input argument(s):
        results -- Pandas dataframe containing the post-processed simulation
                   results
        control -- ForecastControl object representing the forecast parameters
    
    Returns:
        results -- version of the input arguments with additional columns
        
    """
    
    for plant in control.plants:
        wells_in_plant = [w for w in control.prod_wells if w.plant == plant.name]
        for well in wells_in_plant:
            results.loc[results.loc[:,'WELL']==well.name,"PLANT"] = plant.name
            results.loc[results.loc[:,'WELL']==well.name,"SEP PRESSURE"] = plant.separator_pressure
            results.loc[results.loc[:,'WELL']==well.name,"H WATER SEP"] = hL_P(plant.separator_pressure)
            results.loc[results.loc[:,'WELL']==well.name,"H STEAM SEP"] = hV_P(plant.separator_pressure)
    h_feed = results['H']
    dryness_separator = (results['H'] - results["H WATER SEP"])/(results['H STEAM SEP'] - results["H WATER SEP"])
    results["SEPARATED STEAM FLOW"] = results['MASS FLOW TOTAL']*dryness_separator
    results["SEPARATED WATER FLOW"] = results['MASS FLOW TOTAL']*(1-dryness_separator)
        
    return results


def GetCardIndices(input_base):
    """Get the important time cards related to forecasting.
    
    Input argument(s):
        input_base -- a list containing the lines of the base input file
    
    Returns:
        lines -- a dictionary containing the index of the important time cards
                 within the input_base list
    
    """
    line_indices = {}
    lines_time = []
    for line_num, line in enumerate(input_base):
        if "'TIME'" in line:
            lines_time.append(line_num)
        if "'ISREAD'" in line:
            line_indices['ISREAD'] = line_num
        if "'ISWRITE'" in line:
            line_indices['ISWRITE'] = line_num
    line_indices['TIME_START'] = lines_time[0]
    line_indices['TIME_END'] = lines_time[1]
    line_indices['TIME_WRITE'] = lines_time[2]
    
    return line_indices
    

def UpdateWellRateCards(input_base, control):
    """Updates the production rate of prduction wells in base file.
    
    Production rates in the base file are replaced by values declared in the
    forecast control file. 
    
    Input argument(s):
        input_base -- a list containing the lines of the base input file
        control    -- ForecastControl object representing the forecast
                      parameters
    
    Returns:
        input_base -- version of the input argument with updated rates
    
    """
    
    # Look for the start of the production rate declarations
    line_start = input_base.index("'COMMENT' 'PRODUCTION RATES'\n") + 1
    
    # Loops over the production rate declarations and replaces each line based
    # on data from forecast control
    for line_num, line in enumerate(input_base[line_start:line_start+len(control.prod_wells)]):
        if "'P'" or "'C'" in line:
            line_data = line.split()
            for well in control.prod_wells:
                if well.name == line_data[1].strip("'"):
                    if well.is_online:
                        rate = line_data[4].split(',')
                        rate[0] = str(well.rate)
                        line_data[4] = ','.join(rate)
                        line_data[0] = "'P'"
                    else:
                        rate = line_data[4].split(',')
                        rate[0] = str(0.0)
                        line_data[4] = ','.join(rate)
                        line_data[0] = "'C'"
                    input_base[line_start+line_num] = (' '*5).join(line_data) + '\n'
    
    return input_base

def UpdateTimeCards(start_year, end_year, input_base, line_indices):
    """Updates the start, end, and write time cards of the base file.
    
    Input argument(s):
        start_year   -- year that the simulation will start
        end_year     -- year that the simulation will end
        input_base   -- a list containing the lines of the base input file
        line_indices -- a dictionary containing the index of the important 
                        time cards within the input_base list
    
    Returns:
        input_base   -- version of the input argument with updated time cards
    
    """
    
    # Update start year
    line_data = input_base[line_indices['TIME_START']].split()
    line_data[1] = str(start_year)
    input_base[line_indices['TIME_START']] = (' '*5).join(line_data) + '\n'
    
    # Update end year
    line_data = input_base[line_indices['TIME_END']].split()
    line_data[1] = str(end_year)
    input_base[line_indices['TIME_END']] = (' '*5).join(line_data) + '\n'
    
    # Update time after write of intersim file
    line = input_base[line_indices['TIME_WRITE']].split()
    line[1] = str(float(end_year) + 0.01)
    line[2] = '0.0'
    input_base[line_indices['TIME_WRITE']] = (' '*5).join(line) + '\n'
    
    return input_base

def UpdateISCards(alias, input_base, line_indices):
    """Updates the ISREAD and ISWRITE cards of the base file.
    
    Input argument(s):
        alias        -- an alias for the current model run
        input_base   -- a list containing the lines of the base input file
        line_indices -- a dictionary containing the index of the important 
                        time cards within the input_base list
    
    Returns:
        input_base   -- version of the input argument with updated IS cards
    
    """
    # Update ISREAD card
    line_data = input_base[line_indices['ISREAD']].split()
    line_data[2] = "'"+alias+".IS'\n"
    input_base[line_indices['ISREAD']] = (' '*5).join(line_data)

    # Update ISWRITE card    
    line_data = input_base[line_indices['ISWRITE']].split()
    line_data[2] = "'"+alias+"_o.IS'\n"
    input_base[line_indices['ISWRITE']] = (' '*5).join(line_data)
    
    return input_base

def UpdateRunAllBatchFile(alias):
    """Update the runAll.bat file for a new model run.
    
    Input argument(s):
        alias -- an alias for the current model run
    
    Returns:
        None
    
    """
    
    # Open and store lines of the existing batch file
    with open('runAll.bat','r') as f:
        runall_base = f.readlines()
    
    # Update batch file lines with new model alias
    runall_base[2] = 'SET DATFILE=' + alias + '\n'
    svrwkdir = runall_base[9].split('SET SVRWKDIR=')
    svrwkdir = svrwkdir[1].strip()
    svrwkdir = svrwkdir.split('"')[1]
    runall_base[-1] = ' '.join(['xcopy',svrwkdir+alias+'_o.IS','.\\ /Y\n'])
    runall_base[-2] = ' '.join(['xcopy',svrwkdir+alias+'.OUT','.\\ /Y\n'])
    
    # Re-write changes to batch file
    with open('runAll.bat','w') as f:
        f.writelines(runall_base)
    

def RunModel(alias, start_year, end_year, input_base, control, line_indices):
    """Run a single TETRAD model.
    
    Input argument(s):
        alias        -- an alias for the current model run
        start_year   -- year that the simulation will start
        end_year     -- year that the simulation will end
        input_base   -- a list containing the lines of the base input file
        control      -- ForecastControl object representing the forecast
                        parameters
        line_indices -- a dictionary containing the index of the important 
                        time cards within the input_base list

    Returns:
        results      -- Pandas dataframe containing the post-processed 
                        simulation results
    
    """
    
    # Update well rates
    input_base = UpdateWellRateCards(input_base, control)

    # Update time cards
    input_base = UpdateTimeCards(start_year, end_year, input_base, line_indices)
    
    # Update IS read and write cards
    input_base = UpdateISCards(alias, input_base, line_indices)
    
    # Write new input file for the make-up run check
    with open(alias+'.DAT', 'w') as f:
        f.writelines(input_base)
    
    # Rewrite runAll.bat to use current period input file
    UpdateRunAllBatchFile(alias)
    
    # Run single TETRAD model
    run_log = open(alias+'.log','w')
    p = Popen('runAll.bat', stdout=run_log)
#    p = Popen('runAll.bat')
    stdout, stderr = p.communicate()
    run_log.close()
    
    # Post-process results and save into data frame
    results = process_outfile(alias+'.OUT')
    
    return results


def CalculatePlantFlow(results):
    """Calculate steam flow per plant.
    
    Input argument(s):
        results  -- Pandas dataframe containing the post-processed simulation
                     results
    
    Returns:
        model_sf -- List containing number of plant steam flows
    
    """
    grouped_results = results.groupby(['Time','PLANT']).sum()
    plants = grouped_results.index.values
    plants = list(set([i[1] for i in plants]))
    bySF = grouped_results['SEPARATED STEAM FLOW']
    bySF = bySF.loc[bySF.index[len(plants)][0],:]
    plants = list(bySF.index.get_level_values('PLANT'))
    model_sf = list(bySF.values)
    model_sf = [abs(x) for x in model_sf]
    byWF = grouped_results['SEPARATED WATER FLOW']
    byWF = byWF.loc[byWF.index[len(plants)][0],:]
    model_wf = list(byWF.values)
    model_wf = [abs(x) for x in model_wf]
    
    return plants, model_sf, model_wf
    

def CheckMakeUpWellRequirements(model_sf, plants, current_run, start_year, input_base, control, is_file):
    # Alias or name of the current model run
    alias = 'MAKEUPCHECK'            
    
    # Get important line indices from base input file
    line_indices = GetCardIndices(input_base)

    # Initialize control variable for the while loop
    steam_flow_enough= [False] * len(control.plants)
    
    # Copy current run initial conditions
    sh.copyfile(current_run+'.IS', alias+'.IS')    
    
    count = 0   # DEBUG: count number of loops needed to get enough steam flow
    
    # Loops endlessly until model produces enough steam flow for each plant
    # or when plant runs out of M&R wells    
    cut_in_wells = []
    while(False in steam_flow_enough):        
        logger.info('\tmodel_sf: %s' % model_sf)
        if model_sf is None:            
            # Run model for 10 days only
            end_year = start_year + 10/365.25
            
            # Run TETRAD model
            results = RunModel(alias, start_year, end_year, input_base, control, line_indices)
            
            # Calculate total separated steam flow per plant
            results = CalculateSeparatedSteamFlow(results, control)
            plants, model_sf, model_wf = CalculatePlantFlow(results)
        
        # DEBUG: uncomment to print dataframe with separated steam flow
#        results.to_excel('Results_extended'+str(count)+'.xlsx')
#        count = count + 1
#        break
        
        # Compare with model steam flow with per plant limit
        plant_sf = [p.steam_target for p in control.plants]
        steam_flow_enough = [m_sf > p_sf for m_sf, p_sf in zip(model_sf, plant_sf)]
        for plant_index, p in enumerate(plants):
            plant = [pl for pl in control.plants if pl.name == p][0]
            steam_flow_enough[plant_index] = np.around(model_sf[plant_index],1) >= plant.steam_target
            available_wells = len([well for well in control.prod_wells if not well.is_online and well.plant == plant.name])
            if not steam_flow_enough[plant_index] and available_wells > 0:
                logger.info('\t\tModel SF %s < Target SF %s for Plant %s' % (model_sf[plant_index], plant.steam_target, plant.name))
                # activate M&R Well
                for well_index, well in enumerate(control.prod_wells):
                    if well.plant == plant.name and not well.is_online:
                        control.prod_wells[well_index].is_online = True
                        cut_in_wells.append(well.name)
                        break
            else:
                steam_flow_enough[plant_index] = True
                if available_wells < 1:
                    logger.info('\t\tModel SF %s :: Target SF %s for Plant %s' % (model_sf[plant_index], plant.steam_target, plant.name))
                    logger.info('\t\tNo more M&R wells available for plant %s' % plant.name)
                else:
                    logger.info('\t\tModel SF %s > Target SF %s for Plant %s' % (model_sf[plant_index], plant.steam_target, plant.name))
        model_sf = None
    
    return control, cut_in_wells
        

if __name__ == '__main__':
    
    # DEBUG: TIME START
    exec_start_time = time.clock()
    logger.debug('time started: %s' % exec_start_time)
    
    # Read forecast control file
    logger.info('reading forecast control spreadsheet...')
    control = ForecastControl()
    logger.info('reading forecast control spreadsheet...success!')

    # Read base input file
    logger.info('reading base input file...')
    with open('BASE.DAT', 'r') as f:
        # read a list of lines into data
        input_base = f.readlines()
    logger.info('reading base input file...success!')
    logger.debug(input_base)
    
    # Get important line indices from base input file
    logger.info('getting indices ...')
    line_indices = GetCardIndices(input_base)
    logger.info('getting indices ...success!')
    logger.debug(line_indices)

    # Iterate over periods and store post-processed data in dataframe
    results = None
    DECLINE_RATE = 2.5 / 100.
    start_year = 2014.8
    model_sf = None
    plants = None
    for period_index, period in enumerate(control.periods):
        # End year for current period
        end_year = start_year + period.length/365.25
        
        logger.info('Starting run for period: %s' % period_index)
        logger.info('\tPeriod start time: %s' % start_year)
        logger.info('\tPeriod end time: %s' % end_year)
        
        alias = 'RUN'+str(period_index)
        logger.debug('\tRun alias: %s' % alias)
        
        # Run for short period to check if SF limit is breached
        logger.info('\tChecking for steam and make-up well requirements...')
        m_and_r = []
        control, m_and_r = CheckMakeUpWellRequirements(model_sf, plants, alias, start_year, input_base, control, alias+'.IS')        
        logger.info('\tCheking for steam and make-up well requirements...success!')
        if m_and_r:
            logger.info('\tM&R wells cut in: %s' % ' '.join(m_and_r))
        else:
            logger.info('\tM&R wells cut in: %s' % 'None')
        
        # Run TETRAD model
        logger.info('\tRunning single model...')
        current_results = RunModel(alias, start_year, end_year, input_base, control, line_indices)
        logger.info('\tRunning single model...success!')
        
        # Post-process results and save into data frame
        logger.info('\tConsolidating results of last run...')
        if results is None:
            logger.info('\tCreating main output dataframe for first run...')
            results = current_results.copy()
            logger.info('\tCreating main output dataframe for first run...success!')
        else:
            logger.info('\tAppending results of last run to main dataframe...')
            results = results.append(current_results.copy(), ignore_index=True)
            logger.info('\tAppending results of last run to main dataframe...success')
        
        # Copy output IS file as input IS file for next run
        logger.info('\tCopying of output IS file as input IS file for next run...')
        sh.copyfile(alias+'_o.IS', 'RUN'+str(period_index+1)+'.IS')
        logger.info('\tCopying of output IS file as input IS file for next run...success!')
        
        # Calculate plan steam flow at end of run        
        logger.info('\tCalculating plant steam flows at end of run...')
        current_results = CalculateSeparatedSteamFlow(current_results, control)
        plants, model_sf, model_wf = CalculatePlantFlow(current_results)
        logger.info('\tCalculating plant steam flows at end of run...success!')
        for p, sf, wf in zip(plants, model_sf, model_wf):
            logger.info('\tPlant flows: %s SF %s WF %s kkg/s' % (p,sf, wf))
        
        # Apply decline rate on rates
        logger.info('\tApplying decline rate for all online wells...')
        for well_index, well in enumerate(control.prod_wells):
            if well.is_online:
                rate = well.rate
                rate = rate - rate * (end_year-start_year) * DECLINE_RATE
#                rate = rate * (1.0 - DECLINE_RATE)
                logger.debug('\t\tWell %s: before %s after %s' % (well.name, well.rate, rate))
                control.prod_wells[well_index].rate = rate
        logger.info('\tApplying decline rate for all online wells...sucess!')
    
        # Increment time
        start_year = end_year
        
    
    logger.info('Completed all model runs!')    
    
    # Calculate total separated steam flow per plant
    logger.info('Calculating separated steam flow per feed over time...')
    results = CalculateSeparatedSteamFlow(results, control)
    logger.info('Calculating separated steam flow per feed over time...success!')
        
    # Write compiled results to excel file
    logger.info('Writing results to excel...')
    results = results.sort(['WELL', 'Time', 'Block'], ascending=[1,1,1])
    results.index = range(1,len(results)+1)
    results.to_excel('Results.xlsx')
    logger.info('Writing results to excel...success!')
    
    logger.info('Everything done!')
    
    # DEBUG: TIME END
    exec_end_time = time.clock()
    logger.debug('time ended: %s' % exec_end_time)
    logger.info('Time elapsed: %s seconds', exec_end_time - exec_start_time)
        
        
        
        
        
        
        
        
        
        
        
        