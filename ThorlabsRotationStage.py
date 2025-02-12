from pylablib.devices import Thorlabs
import pylablib.core.devio
import numpy as np
import pandas as pd
# from pyWLM import WavelengthMeter
# UNCOMMENT IMPORTS IF THEY ARE NEEDED. AS OF 15.05.2023, THEY ARE NOT NEEDED.
import time
# import pyvisa
# import csv

#####################################################################################
# THIS PYTHON SCRIPT IS SOLELY USED TO AUTOMATICALLY SCAN THE ROTATION STAGE WITH THE ASE FILTERS
# WITH THE CORRESPONDING WAVELENGTH OF THE DFB LASER, HENCE NO CODE FOR THE POWER MEASUREMENT OF
# THE LASER IS WRITTEN HERE. TO TERMINATE THE AUTO SCAN, PRESS CTRL + C IN THE TERMINAL WHEN THE
# SCRIPT IS RUNNING.
#####################################################################################

# Some important general functions for the rotation stage

def to_degree(steps) -> float:
    """Converts the internal unit 'steps' to physical unit 'degree'.
    According to Thorlabs, 1 degree equals 136533.33 steps.

    Rounds the angle to 3 decimal places.

    Args:
        steps (float): steps (internal units) of the rotation stage.

    Returns:
        (float): the angle at which the motor is set at.
    """    
    return np.round(steps / 136533.33, decimals=3) 

def to_steps(angle) -> float:
    """Converts the physical unit 'degree' to the internal unit 'steps'.
    According to Thorlabs, 1 degree equals 136533.33 steps.

    Rounds the steps to a full integer.

    Args:
        angle (float): angle of the rotation stage.

    Returns:
        (float): returns the steps of the rotation stage.
    """
    return int(np.round(angle * 136533.33))

def wavelength_to_angle(wavelength: float, data: pd.DataFrame, lowtohi=True) -> float:
    """Calculates the angle the ASE filters have to be in to let
    the desired wavelength pass through.
    The conversion parameters have to be measured and calculated
    outside of this python script.

    Rounds the angle to 3 decimal places.
    lowtohi boolean to switch between wavelength calibration
    modes.

    Args:
        wavelength (float): the wavelength measured by WLM.
        data (pd.DataFrame): Pandas DataFrame object of the .csv data, where
        the calibration parameters are stored.
        lowtohi (bool, optional): sets which calibration function to use.
        "lowtohi": calibration for the angle scan from a lower to higher
        angle will be applied. Defaults to True.
         
    Returns:
        (float): the calibrated angle rounded to 3 decimal places
    """    
    if lowtohi:
        return np.round(wavelength * (data['m'][0]) + data['b'][0], decimals=3)  # Kal 1 (lowtohi)
    else:
        return np.round(wavelength * (data['m'][1]) + data['b'][1], decimals=3)  # Kal 2 (hitolow)

#####################################################################################


# KinesisMotor is a class under the Thorlabs module
class Stage(Thorlabs.KinesisMotor):
    """Stage class for the rotation stage. It inherits from KinesisMotor class.
    """
    def __init__(self, serial_nr='55001373', backlash=0) -> None:
        # Creates an object of KinesisMotor
        Thorlabs.KinesisMotor.__init__(self, serial_nr)
        self.serial_nr = serial_nr
        self.backlash = backlash
        self.setup_gen_move(backlash_distance=(136533*self.backlash))  # sets up the given backlash distance

    def to_degree(self, steps) -> float:
        """Converts the internal unit 'steps' to physical unit 'degree'.
        According to Thorlabs, 1 degree equals 136533.33 steps.

        Rounds the angle to 3 decimal places.

        Args:
            steps (float): steps (internal units) of the rotation stage.

        Returns:
            (float): the angle at which the motor is set at.
        """
        return np.round(steps / 136533.33, decimals=3)

    def to_steps(self, angle) -> float:
        """Converts the physical unit 'degree' to the internal unit 'steps'.
        According to Thorlabs, 1 degree equals 136533.33 steps.

        Rounds the steps to a full integer.

        Args:
            angle (float): angle of the rotation stage.

        Returns:
            (float): returns the steps of the rotation stage.
        """
        return int(np.round(angle * 136533.33))

    def wavelength_to_angle(self, wavelength: float, data: pd.DataFrame, lowtohi=True) -> float:
        """Calculates the angle the ASE filters have to be in to let
        the desired wavelength pass through.
        The conversion parameters have to be measured and calculated
        outside of this python script.

        Rounds the angle to 3 decimal places.
        lowtohi boolean to switch between wavelength calibration
        modes.

        Args:
            wavelength (float): the wavelength measured by WLM.
            data (pd.DataFrame): Pandas DataFrame object of the .csv data, where
            the calibration parameters are stored.
            lowtohi (bool, optional): sets which calibration function to use.
            "lowtohi": calibration for the angle scan from a lower to higher
            angle will be applied. Defaults to True.

        Returns:
            (float): the calibrated angle rounded to 3 decimal places
        """
        if lowtohi:
            return np.round(wavelength * (data['m'][0]) + data['b'][0], decimals=3)  # Kal 1 (lowtohi)
        else:
            return np.round(wavelength * (data['m'][1]) + data['b'][1], decimals=3)  # Kal 2 (hitolow)

    def scan_to_angle(self, position: float, speed: float) -> None:
        # TODO: add return to start position option for this class method?
        """Moves motor to given angle at the given velocity.

        Args:
            position (float): the position the rotation stage should move to.
            speed (float): the rotation speed at which the rotation stage should rotate at.
        """
        self.setup_velocity(max_velocity=self.to_steps(speed))
        self.move_to(self.to_steps(position))

    def change_angle(self, wavelength: float, bool: bool, df: pd.DataFrame) -> bool:
        """Changes the angle of the rotation stage according
        to the input wavelength.
        If the wavelength is outside the range of 1028-1032 nm
        or if the old angle matches the new calculated angle to
        2 decimal places, the function does not change the angle.

        Args:
            wavelength (float): measured wavelength of WLM.
            bool (bool): True if Kal 1 is active.
            df (pd.DataFrame): Pandas DataFrame of the calibration parameters.

        Returns:
            bool (bool): True if Kal 1 is used, False if calibration has been switched to Kal 2.
        """
        old_pos = self.to_degree(self.get_position())
        new_pos = wavelength_to_angle(wavelength, df, bool)
        if (wavelength > 1027 and wavelength < 1032
        and np.round(old_pos, decimals = 2) != np.round(new_pos, decimals=2)):
            if old_pos > new_pos:
                new_pos = wavelength_to_angle(wavelength, df, False)
                bool = False # goes to Kal2
                # print("Kal2")
            elif old_pos < new_pos:
                new_pos = wavelength_to_angle(wavelength, df, True)
                bool = True # goes to Kal1
                # print("Kal1")
            self.move_to(self.to_steps(new_pos))
            # print(f"Old position: {old_pos}")
            # print(f"Change to: {new_pos}")
        return bool
    # un-comment print lines if you wish to position of the motor in the terminal.


#####################################################################################
# TEST to_degree
def to_degree2(steps) -> float:
    """Converts the internal unit 'steps' to physical unit 'degree'.
    According to Thorlabs, 1 degree equals 136533.33 steps.

    Rounds the angle to 3 decimal places.

    Args:
        steps (float): steps (internal units) of the rotation stage.

    Returns:
        (float): the angle at which the motor is set at.
    """    
    return np.round(steps / 136533.33, decimals=3) % 360


def to_steps2(angle) -> float:
    """Converts the physical unit 'degree' to the internal unit 'steps'.
    According to Thorlabs, 1 degree equals 136533.33 steps.

    Rounds the steps to a full integer.

    Args:
        angle (float): angle of the rotation stage.

    Returns:
        (float): returns the steps of the rotation stage.
    """
    return int(np.round(angle * 136533.33)) % (49152000)

# 202° ^= 27579733

# print(to_degree2(27570000))
# print(to_degree2(-27570000))
# print(to_steps2(201.929))
# print(to_steps2(-201.929))

# print(to_steps2(-201.929))
# print(to_steps2(-158.071))
# print(to_degree2(to_steps2(201.929)))
# print(to_degree2(to_steps2(-201.929)))
