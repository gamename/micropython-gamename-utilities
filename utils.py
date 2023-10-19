import os
import sys
import time

import ntptime
import uio
from machine import Pin, reset, RTC

#
# print debug messages
DEBUG = False

#
# Offset from UTC for CST (US Central Standard Time)
CST_OFFSET_SECONDS = -6 * 3600  # UTC-6

#
# Offset from UTC for CDT (US Central Daylight Time)
CDT_OFFSET_SECONDS = -5 * 3600  # UTC-5

#
# Max amount of time we will keep a tracelog
TRACE_LOG_MAX_KEEP_TIME = 48  # hours

# Crash loop detector. If we crash more than 3 times,
# give up restarting the system
MAX_EXCEPTION_RESETS_ALLOWED = 3

#
# How often should we check for OTA updates?
OTA_CHECK_TIMER = 28800  # seconds (8 hrs)


def get_now():
    """
    Get the local time now

    :return: timestamp
    :rtype: time
    """
    current_offset_seconds = CDT_OFFSET_SECONDS if on_us_dst() else CST_OFFSET_SECONDS
    return time.gmtime(time.time() + current_offset_seconds)


def tprint(message):
    """
    Print with a pre-pended timestamp

    :param message: The message to print
    :type message: string
    :return: Nothing
    :rtype: None
    """
    current_time = get_now()
    timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        current_time[0], current_time[1], current_time[2],
        current_time[3], current_time[4], current_time[5]
    )
    print("[{}] {}".format(timestamp, message))


def get_file_age(filename):
    """
    Get the age of a file in days

    :return: The age in days or 0
    :rtype: int
    """
    file_stat = os.stat(filename)
    # Extract the modification timestamp (in seconds since the epoch)
    modification_time = file_stat[8]
    current_time = time.time()
    age_seconds = current_time - modification_time
    age_hours = (age_seconds % 86400) // 3600  # Number of seconds in an hour
    debug_print(f"FAGE: The file {filename} is {age_hours} hours old")
    return int(age_hours)


def purge_old_log_files(max_age=TRACE_LOG_MAX_KEEP_TIME):
    """
    Get rid of old traceback files based on their age

    :param max_age: The longest we will keep them
    :type max_age: int
    :return: Nothing
    :rtype: None
    """
    deletions = False
    del_count = 0
    found_count = 0
    files = os.listdir()
    tprint(f"PURG: Purging trace logs over {max_age} hours old")
    for file in files:
        age = get_file_age(file)
        if file.endswith('.log'):
            found_count += 1
            if age > max_age:
                tprint(f"PURG: Trace log file {file} is {age} hours old. Deleting")
                os.remove(file)
                del_count += 1
                if not deletions:
                    deletions = True
    if deletions:
        tprint(f"PURG: Found {found_count} logs . Deleted {del_count}")
    else:
        tprint(f"PURG: Found {found_count} logs. None deleted")


def debug_print(msg):
    """
    A wrapper to print when debug is enabled

    :param msg: The message to print
    :type msg: str
    :return: Nothing
    :rtype: None
    """
    if DEBUG:
        tprint(msg)


def current_local_time_to_string():
    """
    Convert the current time to a human-readable string

    :return: timestamp string
    :rtype: str
    """
    current_time = get_now()
    year, month, day_of_month, hour, minute, second, *_ = current_time
    return f'{year}-{month}-{day_of_month}-{hour}-{minute}-{second}'


def log_traceback(exception):
    """
    Keep a log of the latest traceback

    :param exception: An exception intercepted in a try/except statement
    :type exception: exception
    :return:  formatted string
    """
    traceback_stream = uio.StringIO()
    sys.print_exception(exception, traceback_stream)
    traceback_file = current_local_time_to_string() + '-' + 'traceback.log'
    output = traceback_stream.getvalue()
    print(output)
    time.sleep(0.5)
    with open(traceback_file, 'w') as f:
        f.write(output)
    return output


def flash_led(count=100, interval=0.25):
    """
    Flash on-board LED

    :param: How many times to flash
    :param: Interval between flashes
    :return: Nothing
    """
    led = Pin("LED", Pin.OUT)
    for _ in range(count):
        led.toggle()
        time.sleep(interval)
    led.off()


def wifi_connect(wlan, ssid, password, connection_attempts=10, sleep_seconds_interval=3):
    """
    Start a Wi-Fi connection

    :param wlan: A network handle
    :type wlan: network.WLAN
    :param ssid: Wi-Fi SSID
    :type ssid: str
    :param password: Wi-Fi password
    :type password: str
    :param connection_attempts: How many times should we attempt to connect?
    :type connection_attempts: int
    :param sleep_seconds_interval: Sleep time between attempts
    :type sleep_seconds_interval: int
    :return: Nothing
    :rtype: None
    """
    led = Pin("LED", Pin.OUT)
    led.off()
    debug_print("WIFI: Attempting network connection")
    wlan.active(True)
    time.sleep(sleep_seconds_interval)
    counter = 1
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        debug_print(f'WIFI: Attempt {counter} of {connection_attempts}')
        time.sleep(sleep_seconds_interval)
        counter += 1
        if counter > connection_attempts:
            print("WIFI: Max connection attempts exceeded. Resetting microcontroller")
            time.sleep(0.5)
            reset()
    led.on()
    print("WIFI: Successfully connected to network")


def max_reset_attempts_exceeded(max_exception_resets=MAX_EXCEPTION_RESETS_ALLOWED):
    """
    Determine when to stop trying to reset the system when exceptions are
    encountered. Each exception will create a traceback log file.  When there
    are too many logs, we give up trying to reset the system.  This prevents an
    infinite crash-reset-crash loop.

    :param max_exception_resets: How many times do we crash before we give up?
    :type max_exception_resets: int
    :return: True if we should stop resetting, False otherwise
    :rtype: bool
    """
    log_file_count = 0
    files = os.listdir()
    for file in files:
        if file.endswith(".log"):
            log_file_count += 1
    return bool(log_file_count > max_exception_resets)


def ota_update_interval_exceeded(ota_timer, interval=OTA_CHECK_TIMER):
    """
    Determine if we have waited long enough to check for OTA
    file updates.


    :param ota_timer: Timestamp to compare against
    :type ota_timer: int
    :param interval: What is the max wait time? Defaults to 600 seconds (10 min)
    :type interval: int
    :return: True or False
    :rtype: bool
    """
    exceeded = False
    ota_elapsed = int(time.time() - ota_timer)
    if ota_elapsed > interval:
        exceeded = True
    return exceeded


def on_us_dst():
    """
    Are we on US Daylight Savings Time (DST)?

    :return: True/False
    :rtype: bool
    """
    on_dst = False
    # Get the current month and day
    current_month = RTC().datetime()[1]  # 1-based month
    current_day = RTC().datetime()[2]

    # DST usually starts in March (month 3) and ends in November (month 11)
    if 3 < current_month < 11:
        on_dst = True
    elif current_month == 3:
        # DST starts on the second Sunday of March
        second_sunday = 14 - (RTC().datetime()[6] + 1 - current_day) % 7
        if current_day > second_sunday:
            on_dst = True
    elif current_month == 11:
        # DST ends on the first Sunday of November
        first_sunday = 7 - (RTC().datetime()[6] + 1 - current_day) % 7
        if current_day <= first_sunday:
            on_dst = True

    return on_dst


def time_sync():
    """
    Sync system with NTP time

    :return: Nothing
    :rtype: None
    """
    print("SYNC: Sync system time with NTP")
    try:
        ntptime.settime()
        debug_print("SYNC: System time set successfully.")
    except Exception as e:
        print(f"SYNC: Error setting system time: {e}")
        time.sleep(0.5)
        reset()


def ota_check(updater):
    """
    Check to see if we have Over-The-Air (OTA) updates.

    :param updater: An updater object
    :type updater: object
    :return: Nothing
    :rtype: None
    """
    tprint("UCHK: Checking for OTA updates")
    if updater.updated():
        tprint("UCHK: OTA updates added. Resetting system.")
        time.sleep(1)
        reset()
    else:
        tprint("UCHK: No OTA updates.")
