import subprocess
import uproot
import os
import awkward as ak
import numpy as np

SIGNAL_SATURATION_LEVEL = -0.54 #saturates at -0.55 but add -0.54 for cushion

class MCPSignalScaler:
    """
    Only works for negative mcp peaks
    """
    @staticmethod
    def _calc_mcp_peaks(seconds: np.ndarray, volts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        For an array of MCP signal waveforms; where each waveform is the time and voltage of the signal. 
        This grabs the 3 smallest values (so the peak) then does a PARABOLIC INTERPOLATION to estimate the peak

        Works only if you have enough points close to the signal peak. This function does the following,

        Lets say you have 3 points (x1,y1), (x2,y2), (x3,y3) you can create 3 equations,
        A*x1^2+B*x1+C=y1
        A*x2^2+B*x2+C=y2
        A*x3^2+B*x3+C=y3

        And then this is a matrix eq of form M*c = b,
        [x1^2 x1 1] [A]   [y1]
        |x2^2 x2 1| |B| = |y2|
        [x3^2 x3 1] [C]   [y3]

        To solve for A, B, C you can solve by doing c = M^-1 * b

        This function does this columnary for n waveforms where each waveform needs to have an interpolated peak.
        """
        
        # 1. Put indexes corresponding to 3 smallest values from each waveform (usually 5000 waveforms for 5000 events) first in the array
        data_peak_idxs = np.argpartition(volts, 3, axis=1)

        # 2. Grab x and y values along these indexes -> np.take_along_axis AND only want the first 3 elements from each waveform -> [:,:3]
        peak_xs = np.take_along_axis(seconds, data_peak_idxs, axis=1)[:,:3]
        peak_ys = np.take_along_axis(volts, data_peak_idxs, axis=1)[:,:3]

        # 3. Quadratic Interpolation of the peak using first 3 points
        # this creates an array of 3x3 equation matrices
        equation_matrix = np.stack(
            np.array([peak_xs**2, peak_xs, np.ones_like(peak_xs)]),
            axis=-1
        )
        inv_matrix = np.linalg.inv(equation_matrix)
        quadratic_coeff = np.einsum('ijk,ik->ij', inv_matrix, peak_ys) #thx gpt, does the matrix multiplication c = M^-1 * b

        # for Ax^2 + Bx + C
        A, B, C = quadratic_coeff[:, 0], quadratic_coeff[:, 1], quadratic_coeff[:, 2]        
        return -B/(2*A), C - B**2/(4*A) #-> x_interpolated_peak, y_interpolated_peak

    @staticmethod
    def _calc_baselines(seconds: np.ndarray, volts: np.ndarray, peak_times: np.ndarray, peak_volts: np.ndarray, pulse_window_estimate: float = 5) -> np.ndarray:
        """
        Calculate the baseline by performing a linear fit on data points excluding those around the SPECIFIED MCP peak.

        Parameters:
        - peak_times (np.ndarray): Array containing the times associated with the voltage peaks. One peak for each waveform.
        - peak_volts (np.ndarray): Array containing the voltage values at the peaks. One peak for each waveform.
        - pulse_window_estimate (float, optional): Duration around the peak to exclude from the fit, default is 3ns.

        Excludes points within the specified window around the peak, then fits a linear line to the remaining data.
        """
        if peak_times.shape != peak_volts.shape:
            raise ValueError(f"Time and voltage arrays should have the same shape, instead they have {peak_times.shape}, {peak_volts.shape} respectively.")

        if peak_times.ndim != 1:
            raise ValueError(f"Peak times and peak volts need to be a flat array, each integer corresponds to the peak of the mcp for that waveform.")
        
        x_peaks_expanded = peak_times[:, np.newaxis]
        # window_mask = (
        #     (seconds < (x_peaks_expanded - pulse_window_estimate)) | (seconds > (x_peaks_expanded + pulse_window_estimate))
        # )
        window_mask = seconds < (x_peaks_expanded - pulse_window_estimate)
        
        base_x = ak.drop_none(ak.mask(seconds, window_mask))
        base_y = ak.drop_none(ak.mask(volts, window_mask))

        # NOTE: 1e9 is important, the awkward linear fit function was having troubles with small numbers floating error? 
        fit = ak.linear_fit(base_x, base_y, axis=1) 

        return fit.intercept.to_numpy() # I guess numpy is smarter so we put it back
        #return np.mean(base_x, axis=1)

    @classmethod
    def normalize(cls, seconds: np.ndarray, volts: np.ndarray, signal_saturation_level:float=-0.52) -> tuple[np.ndarray, np.ndarray]:
        """
        Normalize signal to be between 0 and 1 by calculating the baseline and peak maximum!
        It also removes any saturated signals by setting the arrays to np.NaN
        """
        # Gaurd Conditions
        if seconds.shape != volts.shape:
            raise ValueError(f"Time and voltage arrays should have the same shape, instead they have {seconds.shape}, {volts.shape} respectively.")
        
        if seconds.ndim == 1: #only need to check seconds since shape check above :)
            # if you just give one waveform it will work too :)
            seconds = np.array([seconds])
            volts = np.array([volts])

        # REMOVE SATURATED SIGNALS
        # using np.where to preserve array length and np.min because the signal is negative \/
        # have to do [:,np.newaxis], just takes the array and wraps arrays around the inner values (float)
        volts   = np.where(np.min(volts, axis=1)[:,np.newaxis] > signal_saturation_level, volts, np.NaN)
        seconds = np.where(np.min(volts, axis=1)[:,np.newaxis] > signal_saturation_level, seconds, np.NaN)
        #-----------------------------------------------------------------------------#

        peak_times, peak_volts = cls._calc_mcp_peaks(seconds, volts)
        baselines = cls._calc_baselines(seconds, volts, peak_times, peak_volts)

        v_mins = baselines[:,np.newaxis]
        v_maxs = peak_volts[:,np.newaxis] 
        volts_scaled = (volts - v_mins) / (v_maxs-v_mins)

        return seconds, volts_scaled
