import subprocess
import argparse
import os
import json
import statistics
import pprint
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# How many times should the benchmarker repeat the problem
# We are typically using 20 for this value to get a good
# statistical variance.
NUMBER_OF_TIMES_TO_RUN = 20

# this needs to be a google service account credentials json file
# you can find info on how to get this in the gspread docs
GOOGLE_CREDS_JSON_FILE = 'google-creds.json'

# the id of the google sheet - this can be found in the url of the sheet.
GOOGLE_SHEET_ID_FOR_RESULTS = "1tmgYMJaxUMT-EHWheKSRgQKuQx6sqRbGP_cNT1vvdsU"

# logging file
LOG_FILE = os.path.join('/', 'tmp', 'zcbmark.log') 

#
# Setup argparse to parse our arguments and provide typical command line utilities
#
parser = argparse.ArgumentParser(description='Perform zcash mining benchmarking for Sigma Prime')
parser.add_argument(
        '--cpu-cores',
        type=int,
        dest='cores',
        help='What is the highest cpu core count we should test with? (How many cores does the CPU have)',
        required=True,
)
parser.add_argument(
        '--zcash-dir',
        dest='zcash_dir',
        help='Location of the (compiled) zcash github directory.',
        required=True,
)
parser.add_argument(
        '--notes',
        dest='notes',
        help='Notes to be posted to gsheets. Eg, pauls macbook running arch',
        required=True,
)

def log(message):
    print(message)
    with open(LOG_FILE, "a") as log_file:
        log_file.write(message)

# Creates an average time from the output of zcbenchmark
def average_zcbenchmark_results(zcbenchmark_stdout):
    results = json.loads(zcbenchmark_stdout)
    times = [result['runningtime'] for result in results]
    log('INFO: results {0}'.format(times))
    average = statistics.mean(times)
    log('INFO: mean {0}'.format(average))
    return()

def get_lshw_json():
    proc = subprocess.run(
            ['lshw -quiet -json'],
            stdout=subprocess.PIPE,
            shell=True,
    )
    as_string =  proc.stdout.decode('utf-8')
    as_json = json.loads(as_string)
    return(as_json)

# recursively loop through the lshw results and return
# lshw[return_key] when we find an object that matches
# the find_id
def find_id_in_lshw_dict(lshw_dict, find_id, return_key):
    for k, v in lshw_dict.items():
        if isinstance(v, list):
            for item in v:
                result = find_id_in_lshw_dict(item, find_id, return_key)
                if result:
                    return result
        else:
            if lshw_dict['id'] == find_id:
                if return_key in lshw_dict:
                    return lshw_dict[return_key]

# recursively loop through the lshw dict and return some stuff about parents
def find_memory_in_lshw_dict(lshw_dict, find_class, return_key, parent_id=None):
    results = []
    for k, v in lshw_dict.items():
        if isinstance(v, list):
            for item in v:
                result = find_memory_in_lshw_dict(item, find_class, return_key, lshw_dict['id'])
                if result:
                    results.append(str(result))
        else:
            if lshw_dict['class'] == find_class and parent_id == 'memory':
                if return_key in lshw_dict:
                    return lshw_dict[return_key]
    return '|'.join(results)

# push the results to gsheets    
def push_results_to_gsheets(creds_file, sheet_id, results):
    # not sure what this scope thing is
    scope = ['https://spreadsheets.google.com/feeds']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)

    # authorise with google and create a gspread object
    gc = gspread.authorize(credentials)

    # Open a worksheet from the spreadsheet
    wks = gc.open_by_key(sheet_id).sheet1

    # grab the first row from the spreadsheet and assume it is the header row
    headers = wks.row_values(1)

    # create our row to be pushed to gsheets
    new_row = [0] * len(headers)
    
    # order the results into an array matching the order of the spreadsheets headers
    # this means the keys in results must match to a header row in the spreadsheet
    for k, v in results.items():
        try:
            new_row[headers.index(k)] =  v
        except ValueError:
            log('WARN: spreadsheet has no header: {0}'.format(k))

    wks.append_row(new_row)
    log('INFO: Uploaded to gsheets: {0}'.format(new_row))




#
# Start of Program Execution
#

# Parse arguments from command line
args = parser.parse_args()

# Setup the path to the zcash-cli executable
zcash_cli = os.path.join(args.zcash_dir, 'src', 'zcash-cli')

# initialise an empty dict to store our results
results = dict()

lshw = get_lshw_json()
results['product'] = lshw['product']
results['processor'] = find_id_in_lshw_dict(
        lshw_dict=lshw,
        find_id='cpu',
        return_key='product',
    )
results['processor_bits'] = find_id_in_lshw_dict(
        lshw_dict=lshw,
        find_id='cpu',
        return_key='width',
    )
results['memory_size'] = find_id_in_lshw_dict(
        lshw_dict=lshw,
        find_id='memory',
        return_key='size',
    )
results['memory_descriptions'] = find_memory_in_lshw_dict(
        lshw_dict=lshw,
        find_class='memory',
        return_key='description',
    )
results['memory_clocks'] = find_memory_in_lshw_dict(
        lshw_dict=lshw,
        find_class='memory',
        return_key='clock',
    )
log('INFO: hardware specs: {0}'.format(results))

results['repeats'] = NUMBER_OF_TIMES_TO_RUN
results['core_count'] = args.cores
results['notes'] = args.notes

# track errors in benchmarking
benchmarking_had_errors = False

# Start at 1 and test all core counts up to the computers amount of cores
for core_count in range (1, args.cores+1):
    log('INFO: Testing using {0} core(s) with {1} repeats.'.format(core_count, NUMBER_OF_TIMES_TO_RUN))

    # execute the zcash-cli zcbenchmark
    completed_process = subprocess.run(
            [zcash_cli, 'zcbenchmark', 'solveequihash', str(NUMBER_OF_TIMES_TO_RUN), str(core_count)],
            stdout=subprocess.PIPE
    )

    # check for errors from the process
    if completed_process.returncode > 0:
        log('zcbenchmark failed. Is the daemon running? (zcashd --daemon)')
        benchmarking_had_errors = True
    else:
        # store the stdout from the zcbenchmark utility as a string
        zcbenchmark_output = completed_process.stdout.decode("utf-8")
        # take json stdout and turn it into a dict
        json_output = json.loads(zcbenchmark_output)
        # calculate mean times
        times = [result['runningtime'] for result in json_output]
        log('INFO: {1} core(s) times: {0}'.format(times, core_count))
        average = statistics.mean(times) / core_count   # we divide by core count because testing with 2 cores produces twice as many hashes as testing with 1
        log('INFO: {1} core(s) mean time: {0}'.format(average, core_count))
        # store the results
        results['{0}_cores_times'.format(core_count)] = times
        results['{0}_cores_average_per_core'.format(core_count)] = average

if benchmarking_had_errors:
    log('ERROR: Benchmarking had errors.')

log('INFO: pushing to Google Sheets')
push_results_to_gsheets(GOOGLE_CREDS_JSON_FILE ,GOOGLE_SHEET_ID_FOR_RESULTS,  results)

