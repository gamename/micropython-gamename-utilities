import os
import sys
import time

import uio
import utime
from machine import Pin, reset


def current_time_to_string():
    """
    Convert the current time to a human-readable string

    :return: timestamp string
    :rtype: str
    """
    current_time = utime.localtime()
    year, month, day_of_month, hour, minute, second, *_ = current_time
    return f'{year}-{month}-{day_of_month}-{hour}-{minute}-{second}'


def log_traceback(exception):
    """
    Keep a log of the latest traceback

    :param exception: An exception intercepted in a try/except statement
    :type exception: exception
    :return: Nothing
    """
    traceback_stream = uio.StringIO()
    sys.print_exception(exception, traceback_stream)
    traceback_file = current_time_to_string() + '-' + 'traceback.log'
    with open(traceback_file, 'w') as f:
        f.write(traceback_stream.getvalue())


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
    print("WIFI: Attempting network connection")
    wlan.active(True)
    time.sleep(sleep_seconds_interval)
    counter = 0
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        print(f'WIFI: Attempt: {counter}')
        time.sleep(sleep_seconds_interval)
        counter += 1
        if counter > connection_attempts:
            print("WIFI: Network connection attempts exceeded. Restarting")
            time.sleep(1)
            reset()
    led.on()
    print("WIFI: Successfully connected to network")


def door_recheck_delay(reed_switch, delay_minutes):
    """
    Deal with the situation where the mailbox door has been opened, but may
    not have been closed. The dilemma is you want to know if the door is left
    open, but you don't want lots of texts about it. This routine slows down
    the rate of notifications.

    :param reed_switch: A reed switch handle
    :param delay_minutes: how long to delay before we return
    :return: Nothing
    """
    print(f'DSTATE: Delay {delay_minutes} minutes before rechecking door status')
    state_counter = 0
    while state_counter < delay_minutes:
        state_counter += 1
        time.sleep(60)
        if reed_switch.value():
            print("DSTATE: Door CLOSED")
            break


def max_reset_attempts_exceeded(max_exception_resets=3):
    """
    Determine when to stop trying to reset the system when exceptions are
    encountered. Each exception will create a traceback log file.  When there
    are too many logs, we give up trying to reset the system.  Prevents an
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


def ota_update_interval_exceeded(timer, interval=600):
    """
    Determine of we have waited long enough to check for OTA
    file updates.

    :param timer: The ota timer that tells us how long we have been waiting
    :type timer: timer
    :param interval: What is the max wait time? Defaults to 600 seconds (10 min)
    :type interval: int
    :return: True or False
    :rtype: bool
    """
    exceeded = False
    ota_elapsed = int(time.time() - timer)
    if ota_elapsed > interval:
        exceeded = True
    return exceeded

