''' Python program to generate a graph of the value of every device in the HS3 log file.
    Eric Ryherd (DrZWave) - 15 Dec 2014 - Feely given to the community with no support!
    Eric@ExpressControls.com
    PreRequiresites:
       - gnuplot must already be installed on your system (gnuplot.org)
       - Python 2.7 or later
    Note that I am NOT using GnuPlot.py simply because it requires you to install it and NumPy
        and does not really yield any significant benefit other than the code being slightly cleaner.
    This program will read in the HomeSeer3 log sqlite database and produce a graph for each and
    every entry in the log that has the string "Device:" in it. The graph is the value in Y and 
    Date/Time in X. There has to be at least 3 entries in the log for a graph to be generated.
    The graphs are output in .png files with the name of the device with all spaces removed as the filename.
    An HTML file is also generated with a link to all the graphs and a thumbnail version of them.
    Setup a recurring event to run this program once/hr so the data is up to date. 
    Note that this program does use a lot of CPU power so only run it occasionally and not every time an entry
    is made to the log.
    The expectation is that HomeSeer will build this functionality into HS3 sometime in 2015 which will 
    then obsolete this program.
    Otherwise I would spend more time on it...
'''
import sqlite3  # Builtin for accessing the Homeseer SQlite3 format file
import sys
import re
from subprocess import call
import datetime
import os

class HSGraphLog():
    def __init__(self):
        try:
            os.mkdir(os.path.join(os.getcwd(),"html","graphs")) # need this directory for the .PNG files
        except OSError:
            pass    # OSError is expected if the directory already exists which is OK

    def run(self):
        dirname=os.getcwd()
        logfilename = os.path.join(dirname,'Logs','HomeSeerLog.hsd') # This is the default location and filename for the log file
        try:
            log=sqlite3.connect(logfilename)
        except:
            print "failed to open file {}".format(logfilename)
            sys.exit()
        devdict = {} # dictionary of devices in the log. The device name is the key and a list of tuples is appended with the date/value
        cur=log.cursor()
        cur.execute("SELECT Log_DateTime,Log_Entry from Log where Log_Entry like 'Device:%'") # this selects ONLY the Device state updates from the log file - all other entries are ignored
        entry = cur.fetchone() # pick out 1 entry from the log file
        # unfortunately HST is just puts the entry into a single big string so we have to parse it out and clean it
        while entry is not None:
            dtime=str(entry[0])
            device=str(entry[1])
            value=str(entry[1])
	    #print "device before={}".format(device)	# debug
            #print device.parse('Device: %s') # this gives an AttributeError but I can't find ANYTHING that says why! So I'll parse it myself using REs
            device=re.sub('^.*Device: ','',device) # chop off the beginning
            device=re.sub(' to .*$','',device) # chop off the end
            device=re.sub(' Set$','',device) # some lines also have 'Set' in them which must be removed
            device=device.replace(' ','') # remove the spaces in the device name to make cleaner filenames
            device=re.sub('<.font>','',device) # remove the font strings which appeared in a later release of HS3
            device=re.sub('<fontcolor=.#.......>','',device) # remove the font strings which appeared in a later release of HS3
	    #print "value before={}".format(value)	# debug
            value=re.sub('^.* to ','',value) # get just the value
            value=re.sub('<font color=.#....... >','',value) # remove the font strings which appeared in a later release of HS3
            value=re.sub('<.font>','',value) # remove the font strings which appeared in a later release of HS3
            value=value.replace('(F)','') # Temperatures have the scale
            value=value.replace('Dim','') # Dimmers have 'Dim xx%
            value=value.replace('%','')
            value=value.replace('(','')
            value=value.replace(')','')
            value=value.replace('Operating State','') # thermostats report this and an integer of their state so use that
            valnum=-999    # flag that the conversion has failed
            try:    # convert the value to a number - usually a float
                valnum=float(value)
            except ValueError: # then it's probably On/OFF or something
                if 'OFF' in value.upper():
                    valnum=0
                elif 'ON' in value.upper():
                    valnum=1
                elif 'NO MOTION' in value.upper():  # the challenge is that motion sensors send both No Motion and Motion so this has to be in an ELIF before MOTION
                    valnum=0
                elif 'MOTION' in value.upper():
                    valnum=0
                elif 'UNLOCKED' in value.upper(): # again this must be priority encoded
                    valnum=1
                elif 'LOCKED' in value.upper():
                    valnum=0
                elif 'HEAT' in value.upper(): # Thermostat operating mode
                    valnum=1
                else:   # check if any field in the string is number and simply use the 1st one
                    valsplit=value.split()
                    for valsplit_each in valsplit:
                        try:
                            valnum=float(valsplit_each)
                            break
                        except ValueError:
                            pass
            if valnum==-999: # if we can't match it above then we need to do something special...
                print entry
                print "{0}|{1}|{2}={3}".format(dtime,device,value,valnum)
                #return          # Uncomment this line to debug the device string that is not being handled properly
            #print "{0}|{1}|{2}={3}".format(dtime,device,value,valnum) # uncomment for debug
            valpair = [dtime,valnum]
            try:
                devdict[device].append(valpair)
            except KeyError:
                devdict[device] = [valpair]
            entry = cur.fetchone() # pick out 1 entry from the log file
        #print len(devdict.keys())
        listofkeys=devdict.keys()
        for eachkey in listofkeys:
            valpairsforthiskey=devdict[eachkey]
            if (len(valpairsforthiskey)>3): # don't make graphs for anything with less than 3 datapoints
                HSGraphLog.PlotPNG(self,eachkey,valpairsforthiskey)
        # now create a small HTML file with links to all the graphs so they can be easily browsed to
        try:
            htmlfile=open(os.path.join(dirname,'html','HSGraphLog.htm'),'w+')
        except:
            print "unable to open {0}".format(os.path.join(dirname,'html','HSGraphlog.htm'))
            sys.exit()
        htmlfile.write("<html><title>HomeSeer Graphs generatated at {}</title>".format(str(datetime.datetime.now())))
        htmlfile.write('<body><font face="arial">')
        htmlfile.write("<p>HomeSeer Device Graphs generatated at {}</p>".format(str(datetime.datetime.now())))
        for eachkey in sorted(listofkeys):
            htmlfile.write('<br><a href="graphs/{0}.png">{0}</a>'.format(eachkey))
        htmlfile.write('</body></html>')
        htmlfile.close()

    def PlotPNG(self,name,values):
        ''' Runs gnuplot (via the OS directly) to create a name.png file that is a plot of the values'''
        # first create the command file that sets the format for each plot
        try:
            pltfile=open('tempPlotCmd.plt','w+')
        except:
            print "unable to open file tempPlotCmd.plt"
            sys.exit()
        pltfile.write('set terminal png size 800,600\r\n') # this sets the size - change these to your desired values
        pltfile.write('cd "html"\r\n')
        pltfile.write('cd "graphs"\r\n')
        pltfile.write('set xdata time\r\n')
        pltfile.write('set timefmt "%Y-%m-%d %H:%M:%S"\r\n')
        pltfile.write('set grid\r\n')
        #pltfile.write('set xlabel "Date/Time"\r\n')
        pltfile.write('set datafile separator ","\r\n')
        pltfile.write('set output graphname\r\n')
        pltfile.write(r'plot "../../tempPlot.dat" using 1:2 index 0 title "" with histeps lt rgb "#0080A0"')
        pltfile.close()
        # now write the data into a temporary file in the format needed by gnuplot
        try:
            datfile=open('tempPlot.dat','w+')
        except:
            print "unable to open file tempPlot.dat"
            sys.exit()
        for i in values:
            datfile.write('{0},{1}\n'.format(i[0],i[1]))
        datfile.close()
        print(r'gnuplot -e "set title \"{0}\"; graphname=\"{0}.png\"" tempPlotCmd.plt'.format(name))
        call(r'gnuplot -e "set title \"{0}\"; graphname=\"{0}.png\"" tempPlotCmd.plt'.format(name))

if __name__ == "__main__":
    graphs = HSGraphLog()
    HSGraphLog.run(graphs)
