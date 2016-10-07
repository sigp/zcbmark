import subprocess
import argparse
import os
import json
import statistics
import pprint

# How many times should the benchmarker repeat the problem
# We are typically using 20 for this value to get a good
# statistical variance.
NUMBER_OF_TIMES_TO_RUN = 20

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

# Creates an average time from the output of zcbenchmark
def average_zcbenchmark_results(zcbenchmark_stdout):
    results = json.loads(zcbenchmark_stdout)
    times = [result['runningtime'] for result in results]
    print('INFO: results {0}'.format(times))
    average = statistics.mean(times)
    print('INFO: mean {0}'.format(average))
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

print(results)

# Start at 1 and test all core counts up to the computers amount of cores
for core_count in range (1, args.cores+1):
    print('INFO: Testing using {0} core(s) with {1} repeats.'.format(core_count, NUMBER_OF_TIMES_TO_RUN))

    # execute the zcash-cli zcbenchmark
    completed_process = subprocess.run(
            [zcash_cli, 'zcbenchmark', 'solveequihash', str(NUMBER_OF_TIMES_TO_RUN), str(core_count)],
            stdout=subprocess.PIPE
    )

    # check for errors from the process
    if completed_process.returncode > 0:
        print('zcbenchmark failed. Is the daemon running? (zcashd --daemon)')
    else:
        # store the stdout from the zcbenchmark utility as a string
        zcbenchmark_output = completed_process.stdout.decode("utf-8")
        # take json stdout and turn it into a dict
        json_output = json.loads(zcbenchmark_output)
        # calculate mean times
        times = [result['runningtime'] for result in json_output]
        print('INFO: {1} core(s) times: {0}'.format(times, core_count))
        average = statistics.mean(times) / core_count   # we divide by core count because testing with 2 cores produces twice as many hashes as testing with 1
        print('INFO: {1} core(s) mean time: {0}'.format(average, core_count))
        # store the results
        results['{0}_cores_times'.format(core_count)] = times
        results['{0}_cores_average'.format(core_count)] = average

print(results)






