import numpy as np
import awkward as ak

def get_rising_edge_after_first_fall(nanoseconds: ak.Array, volts_scaled: ak.Array, thresh_low: int, thresh_high: int) -> tuple[ak.Array, ak.Array]:
    """
    INPUTS \n
    nanoseconds: array of arrays of times of the square wave in nanoseconds \n
    volts_scaled: array of arrays of the volts of the square waved scaled between 0 and 1 \n
    thresh_low and thresh_high: between 0 and 1, select the values of where the edges are, chops the bottom and top of the square wave respectively \n
    
    RETURNS \n
    Rising edge times and voltage values \n

    Returns the first rising edge of a square wave \n
    Algorithm STEPS: \n
    1. Make a mask of all falling edges from the square wave and get the indices of the square wave \n
        - edges decided by thresh_low and thresh high, and falling decided by taking the difference between neighboring points of V and checking the sign \n
    2. SELECT all points of the square wave AFTER the FALLING EDGE by checking for discontinuity in index (ex: 1,2,3,4,656 then remove 1,2,3,4) \n
    3. Make a mask of all edges and get the indices of the filtered square wave from step 2
    4. SELECT all points BEFORE the end of the first edge \n
        - which is gaurenteed to be a rising edge and is detected by this index discontinuity method \n
    5. Apply edge mask again to get just the first rising edge! \n
    """
    def edge_mask(V: ak.Array) -> ak.Array:
        return ((thresh_low <= V) & (V <= thresh_high))

    def get_idx_between_edgs(edg_idxs: ak.Array) -> ak.Array:
        #works like np.diff!
        edg_diffs = edg_idxs[:, 1:] - edg_idxs[:, :-1]
        #if there is a diff greater than one in index than we jumped to a new edge!
        return edg_idxs[edg_diffs > 1] + 1
    
    square_wave = ak.zip({
        "t": nanoseconds,
        'V': volts_scaled
    })
    # !!!!!!!!!see docstring for steps!!!!!!!!!
    # -------------[ STEP 1 ]---------------- #
    sw_idxs = ak.local_index(square_wave)
    falling_edg_mask = edge_mask(square_wave.V) & (np.diff(square_wave.V, append=np.inf) < 0)
    # -------------[ STEP 2 ]---------------- #
    #the [...,0] is important, grabs the first index out of each array, 99% of the time there is only one anyway
    falling_transition_idx = get_idx_between_edgs( sw_idxs[falling_edg_mask] )[...,0] 
    past_first_fall = sw_idxs[sw_idxs > falling_transition_idx[:,np.newaxis]]
    sw_pff = square_wave[past_first_fall]    

    # -------------[ STEP 3 ]---------------- #
    sw_pff_idxs = ak.local_index(sw_pff)
    all_edge_mask = edge_mask(sw_pff.V)
    #the [...,0] is important, grabs the first index out of each array, 99% of the time there is only one anyway
    # -------------[ STEP 4 ]---------------- #
    rising_edg_pff = get_idx_between_edgs( sw_pff_idxs[all_edge_mask] )[...,0]
    rising_after_falling = sw_pff_idxs[sw_pff_idxs < rising_edg_pff[:, np.newaxis]]
    sw_rising_pff = sw_pff[rising_after_falling]

    # -------------[ STEP 5 ]---------------- #
    e2mask = edge_mask(sw_rising_pff.V) #need to recut to just get rising edge
    return sw_rising_pff[e2mask].t, sw_rising_pff[e2mask].V

def calc_clock(nanoseconds: ak.Array, volts: ak.Array, thresh_low: float, thresh_high: float, measurement_level: float) -> ak.Array:

    #SCALE the voltage so values are between 0 and 1
    v_mins = ak.min(volts, axis=1, keepdims=True)
    v_maxs = ak.max(volts, axis=1, keepdims=True)
    volts_scaled = (volts - v_mins) / (v_maxs-v_mins)

    rising_times, rising_volts = get_rising_edge_after_first_fall(nanoseconds, volts_scaled, thresh_low, thresh_high)
    fits = ak.linear_fit(rising_times, rising_volts, axis=-1)

    clock_stamp = (measurement_level - fits['intercept'])/fits['slope'] # x = (y-b)/m
    return clock_stamp #nanoseconds