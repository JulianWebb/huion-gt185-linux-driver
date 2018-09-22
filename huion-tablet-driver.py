#!/usr/bin/env python3

import usb.core, usb.util
import sys
from evdev import UInput, ecodes, AbsInfo
import subprocess as sp
import math, ast
from configparser import ConfigParser, ExtendedInterpolation
from time import gmtime, strftime

MENU = {}


# -----------------------------------------------------------------------------
class main():
    """
    """
    settings = {'pen_device_name':'Tablet Monitor Pen' # must be defined here
                + strftime(" %H%M%S", gmtime())}       # for pressure to work
    dev = None
    endpoint = None
    vpen = None
    current_menu = None

    def run():
        find_usb_device()
        read_config()
        prepare_driver()
        setup_driver()
        calibrate()
        multi_monitor()
        main_loop()


# -----------------------------------------------------------------------------
def find_usb_device():
    """
    """
    sys.stdout.write("Finding USB device. . . ")

    main.dev = usb.core.find(idVendor=0x256c, idProduct=0x006e)

    if not main.dev:
        print("Error, Could not find device, maybe already opened?",
            file=sys.stderr)
        sys.exit(1)
    else:
        print("Done!")

    for cfg in main.dev:
        for i in cfg:
            for e in i:
                if not main.endpoint:
                    main.endpoint = e
            if main.dev.is_kernel_driver_active(i.index):
                main.dev.detach_kernel_driver(i.index)
                usb.util.claim_interface(main.dev, i.index)
                print("grabbed interface %d", i.index)

    main.endpoint = main.dev[0][(0,0)][0]


# -----------------------------------------------------------------------------
def prepare_driver():
    """
    This is necessary for now.
    See https://github.com/benthor/HuionKamvasGT191LinuxDriver/issues/1
    """

    sys.stdout.write("Preparing driver. . . ")

    module_old   = "hid_uclogic"
    module_new   = "uinput"

    module_found = sp.run('lsmod | grep "^{}"'.format(module_old), shell=True)

    if module_found.returncode == 0:
        sp.run('rmmod "{}"'.format(module_old), shell=True)
    elif module_found.returncode == 2:
        print('Grep error 2')
        exit()

    sp.run('modprobe "{}"'.format(module_new), shell=True)

    cmd='"{}/uclogic-probe" "{}" "{}" | "{}/uclogic-decode"'.format(
        main.settings['uclogic_bins'], main.dev.bus, main.dev.address,
        main.settings['uclogic_bins'])
    try:
        uc_str = sp.run(cmd, shell=True, check=True, stdout=sp.PIPE)
    except sp.CalledProcessError as e:
        run_error(e, cmd)

    print("Done!")

    if main.settings['show_uclogic_info']:
        print('-'*80+'\n'+ uc_str.stdout.decode("utf-8") +'-'*80)


# -----------------------------------------------------------------------------
def setup_driver():
    """
    """

    sys.stdout.write("Setting up driver. . . ")

    # pressure sensitive pen tablet area with 2 stylus buttons and no eraser
    cap_pen = {
        ecodes.EV_KEY: [ecodes.BTN_TOUCH, ecodes.BTN_TOOL_PEN,
            ecodes.BTN_STYLUS, ecodes.BTN_STYLUS2],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, AbsInfo(0,0,main.settings['pen_max_x'],0,0,
                main.settings['resolution'])), # value,min,max,fuzz,flat,resolu.
            (ecodes.ABS_Y, AbsInfo(0,0,main.settings['pen_max_y'],0,0,
                main.settings['resolution'])),
            (ecodes.ABS_PRESSURE, AbsInfo(0,0,main.settings['pen_max_z'],0,0,0)),
        ]
    }

    main.vpen = UInput(events=cap_pen, name=main.settings['pen_device_name'],
        version=0x3)

    print("Done!")

    # INFO ---------------------

    print("\tTablet model name     {}".format(main.settings['model_name']))

    if main.settings['enable_buttons'] and main.settings['buttons'] > 0 :
        print("\tButtons               ENABLED ({})".format(
            main.settings['buttons']))
    else:
        print("\tButtons               disabled ({})".format(
            main.settings['buttons']))

    if main.settings['enable_scrollbar'] and main.settings['scrollbar'] > 0 :
        print("\tScrollbar             ENABLED ({})".format(
            main.settings['scrollbar']))
    else:
        print("\tScrollbar             disabled ({})".format(
            main.settings['scrollbar']))

    if main.settings['enable_notifications']:
        print("\tDesktop notifications ENABLED")
    else:
        print("\tDesktop notifications disabled")

    if main.settings['enable_multi_monitor']:
        print("\tMulti Monitor Setup   ENABLED")
    else:
        print("\tMulti Monitor Setup   disabled")


# -----------------------------------------------------------------------------
def multi_monitor():
    """
    """

    if not main.settings['enable_multi_monitor']:
        return

    sys.stdout.write("Setting up multiple monitors. . . ")

    if not main.settings['screen']:
        print("No tablet screen!")
        return


    if main.settings['enable_xrandr']:
        cmd='xrandr {}'.format(main.settings['xrandr_args'])
        try:
            sp.run(cmd, shell=True, check=True)
        except sp.CalledProcessError as e:
            run_error(e, cmd)

    C0=(main.settings["screen_width"] / main.settings["total_screen_width"])
    C1=(main.settings["tablet_offset_x"] / main.settings["total_screen_width"])
    C2=(main.settings["screen_height"] / main.settings["total_screen_height"])
    C3=(main.settings["tablet_offset_y"] / main.settings["total_screen_height"])

    cmd='xinput set-prop "{}" --type=float "{}" {} 0 {} 0 {} {} 0 0 1'.format(
        main.settings['pen_device_name'], "Coordinate Transformation Matrix",
        C0, C1, C2, C3)
    try:
        sp.run(cmd, shell=True, check=True)
    except sp.CalledProcessError as e:
        run_error(e, cmd)

    print('Done!')

    print('\tMapped tablet area to "{}x{} + {}x{}"'.format(
        main.settings["screen_width"], main.settings["screen_height"],
        main.settings["tablet_offset_x"], main.settings["tablet_offset_y"]))

# -----------------------------------------------------------------------------
def calibrate():

    if not main.settings['enable_calibration']:
        return

    sys.stdout.write("Calibrating. . . ")

    cmd='xinput set-int-prop "{}" "Evdev Axis Calibration" 32 {} {} {} {}'.format(
            main.settings['pen_device_name'],
            main.settings['calibrate_min_x'], main.settings['calibrate_max_x'],
            main.settings['calibrate_min_y'], main.settings['calibrate_max_y'])
    try:
        sp.run(cmd, shell=True, check=True)
    except sp.CalledProcessError as e:
        run_error(e, cmd)

    cmd='xinput set-int-prop "{}" "Evdev Axes Swap" 8 0'.format(
        main.settings['pen_device_name'])
    try:
        sp.run(cmd, shell=True, check=True)
    except sp.CalledProcessError as e:
        run_error(e, cmd)

    print('Done!')


# -----------------------------------------------------------------------------
def main_loop():
    """
    """

    print('\nHuion Kamvas driver should now be running\n')

    switch_menu(main.current_menu)

    SCROLL_VAL_PREV=0

    while True:
        try:
            data = main.dev.read(main.endpoint.bEndpointAddress,
                main.endpoint.wMaxPacketSize)
            
            is_touch = data[1] == 129
            is_pen_btn1 = data[1] == 130
            is_pen_btn2 = data[1] == 132
            is_scrollbar = data[1] == 240
            is_buttonbar = data[1] == 224

            # Descriptive variables to help future bodgers change it to suit them
            button_item = data[4]
            x_item = data[3]
            y_item = data[5]
            press_item = data[7]

            if is_buttonbar and main.settings['enable_buttons']:
                # get the button value in power of two (1, 2, 4, 16, 32...)
                BUTTON_VAL = button_item

                if BUTTON_VAL > 0: # 0 means release
                    # convert to the exponent (0, 1, 2, 3, 4...)
                    BUTTON_VAL = int(math.log(BUTTON_VAL, 2))
                    do_shortcut("button", MENU[main.current_menu][BUTTON_VAL])
            else:
                # I don't understand bitwise operators, but I do know how to do this
                X = int((x_item / 255) * main.settings['pen_max_x']) + 1000 #left handed tweak
                Y = int((y_item / 141) * main.settings['pen_max_y'])
                PRESS = int((press_item / 7) * main.settings['pen_max_z']) #could also use data[6] but it was too unstable

                main.vpen.write(ecodes.EV_ABS, ecodes.ABS_X, X)
                main.vpen.write(ecodes.EV_ABS, ecodes.ABS_Y, Y)
                main.vpen.write(ecodes.EV_ABS, ecodes.ABS_PRESSURE, PRESS)
                main.vpen.write(ecodes.EV_KEY, ecodes.BTN_TOUCH,
                    is_touch and 1 or 0)
                main.vpen.write(ecodes.EV_KEY, ecodes.BTN_STYLUS,
                    is_pen_btn1 and 1 or 0)
                main.vpen.write(ecodes.EV_KEY, ecodes.BTN_STYLUS2,
                    is_pen_btn2 and 1 or 0)
                main.vpen.syn()

        except usb.core.USBError as e:
            data = None
            if e.args == ('Operation timed out',):
                print(e, file=sys.stderr)
                continue


# -----------------------------------------------------------------------------
def do_shortcut(title, sequence):
    """ Interprets whether the shortcut is a keypress or a menu link
        and triggers the appropiate action in either case.
    """
    # empty shortcut
    if sequence == "":
        pass

    # is a menu link
    elif sequence.startswith('[') and sequence.endswith(']'):
        switch_menu(sequence.strip('[]'))

    # is a keyboard shortcut
    else:
        keypress(title, sequence)


# -----------------------------------------------------------------------------
def keypress(title, sequence):
    """
    """
    if main.settings['enable_notifications']:
        cmd='notify-send "{}" "{}"'.format(title, sequence)
        try:
            sp.run(cmd, shell=True, check=True)
        except sp.CalledProcessError as e:
            run_error(e, cmd)

    cmd="xdotool {}".format(sequence)
    try:
        sp.run(cmd, shell=True, check=True)
    except sp.CalledProcessError as e:
        run_error(e, cmd)


# -----------------------------------------------------------------------------
def switch_menu(new_menu):
    """
    """
    if not main.settings['enable_buttons'] or main.settings['buttons'] == 0:
        return

    main.current_menu = new_menu

    # print the menu
    menu_title = MENU[new_menu]['title']
    menu_text = ""
    for n in range(0, main.settings['buttons']):
        menu_text += "\nbutton {} = {}".format(n, MENU[main.current_menu][n])

    print(menu_title + menu_text)

    if main.settings['enable_notifications']:
        cmd='notify-send "{}" "{}"'.format(menu_title, menu_text)
        try:
            sp.run(cmd, shell=True, check=True)
        except sp.CalledProcessError as e:
            run_error(e, cmd)


# -----------------------------------------------------------------------------
def run_error(error, command, exit=True):
    """
    """
    print("ERROR running the following comand:")
    print("\t{}".format(command))
    print("RETURN CODE: {}".format(error.returncode))
    if exit:
        sys.exit(1)


# -----------------------------------------------------------------------------
def read_config():
    """
    """

    sys.stdout.write("Reading configuration. . . ")

    config = ConfigParser(interpolation=ExtendedInterpolation())

    config.read('config.ini') # TODO manage errors

    # tablet info

    current_tablet = config.get('config',
        'current_tablet').split("#",1)[0].strip('[]').strip()
    main.settings['model_name'] = config.get(current_tablet, 'model_name')
    main.settings['pen_max_x'] = ast.literal_eval(config.get(current_tablet,
        'pen_max_x'))
    main.settings['pen_max_y'] = ast.literal_eval(config.get(current_tablet,
        'pen_max_y'))
    main.settings['pen_max_z'] = ast.literal_eval(config.get(current_tablet,
        'pen_max_z'))
    main.settings['resolution'] = ast.literal_eval(config.get(current_tablet,
        'resolution'))
    main.settings['buttons'] = ast.literal_eval(config.get(current_tablet,
        'buttons'))
    main.settings['scrollbar'] = ast.literal_eval(config.get(current_tablet,
        'scrollbar'))
    main.settings['screen_width'] = ast.literal_eval(config.get(current_tablet,
        'screen_width'))
    main.settings['screen_height'] = ast.literal_eval(config.get(current_tablet,
        'screen_height'))
    main.settings['screen'] = config.getboolean(current_tablet, 'screen')

    main.settings['enable_buttons'] = config.getboolean('config',
        'enable_buttons')
    main.settings['enable_scrollbar'] = config.getboolean('config',
        'enable_scrollbar')

    # multi-monitor setup

    main.settings['enable_multi_monitor'] = config.getboolean('config',
        'enable_multi_monitor')
    main.settings['enable_xrandr'] = config.getboolean('config', 'enable_xrandr')

    current_monitor_setup = config.get('config',
        'current_monitor_setup').split("#",1)[0].strip('[]').strip()
    main.settings['total_screen_width'] = ast.literal_eval(config.get(current_monitor_setup,
        'total_screen_width').split("#",1)[0].strip())
    main.settings['total_screen_height'] = ast.literal_eval(config.get(current_monitor_setup,
        'total_screen_height').split("#",1)[0].strip())
    main.settings['tablet_offset_x'] = ast.literal_eval(config.get(current_monitor_setup,
        'tablet_offset_x').split("#",1)[0].strip())
    main.settings['tablet_offset_y'] = ast.literal_eval(config.get(current_monitor_setup,
        'tablet_offset_y').split("#",1)[0].strip())

    main.settings['xrandr_args'] = config.get(current_monitor_setup,
        'xrandr_args').split("#",1)[0].strip()

    # tablet calibration

    main.settings['enable_calibration'] = config.getboolean('config',
        'enable_calibration')
    main.settings['calibrate_min_x'] = ast.literal_eval(config.get('config',
        'calibrate_min_x').split("#",1)[0].strip())
    main.settings['calibrate_max_x'] = ast.literal_eval(config.get('config',
        'calibrate_max_x').split("#",1)[0].strip())
    main.settings['calibrate_min_y'] = ast.literal_eval(config.get('config',
        'calibrate_min_y').split("#",1)[0].strip())
    main.settings['calibrate_max_y'] = config.get('config',
        'calibrate_max_y').split("#",1)[0].strip()

    # miscellaneus

    main.settings['uclogic_bins'] = config.get('config', 'uclogic_bins')
    main.settings['show_uclogic_info'] = config.getboolean('config',
        'show_uclogic_info')
    main.settings['enable_notifications'] = config.getboolean('config',
        'enable_notifications')
    main.settings['start_menu'] = config.get('config', 'start_menu').strip('[]')

    for section in config.sections():
        if section.startswith('menu_'):
            MENU[section] = {}

            # pretty title
            if config.has_option(section, 'title'):
                MENU[section]['title'] = config.get(section, 'title')
            else:
                MENU[section]['title'] = "[{}]".format(section)

            # buttons
            for n in range(0, main.settings['buttons']):
                btn = 'b' + str(n)
                if config.has_option(section, btn):
                    MENU[section][n] = config.get(
                        section, btn).strip()
                else:
                    MENU[section][n] = ""

            # scrollbar
            if main.settings['scrollbar']:
                MENU[section]['scroll_up'] = config.get(
                    section, 'su').strip()
                MENU[section]['scroll_down'] = config.get(
                    section, 'sd').strip()

    main.current_menu = main.settings['start_menu']

    print("Done!")


# -----------------------------------------------------------------------------
if __name__ == '__main__':
    main.run()
