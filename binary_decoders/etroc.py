import struct
import argparse
import numpy as np
import pandas as pd
import awkward as ak
import json
import yaml
from yaml import Dumper, Loader
from module_test_sw.tamalero.DataFrame import DataFrame
from tqdm import tqdm
from emoji import emojize
from functools import wraps
import logging
from logger import NoRepeatedLogs

logger = logging.getLogger("conditional_counter")

def merge_words(res):
    empty_frame_mask = np.array(res[0::2]) > (2**8) # masking empty fifo entries
    len_cut = min(len(res[0::2]), len(res[1::2]))   # ensuring equal length of arrays downstream
    if len(res) > 0:
        return list (np.array(res[0::2])[:len_cut][empty_frame_mask[:len_cut]] | (np.array(res[1::2]) << 32)[:len_cut][empty_frame_mask[:len_cut]])
    else:
        return []

@NoRepeatedLogs(logger=logger, num_logged_ifs=34)
def converter(etroc_binary_files:list[str], verbose:bool = False, skip_trigger_check:bool = False, force:bool = False):
    # NOTE find all files (i.e. layers) for the specified input file
    df = DataFrame('ETROC2')
    events_all_rb = []
    missing_l1counter = []
    for irb, f_in in enumerate(etroc_binary_files):
        with open(f_in, 'rb') as f:
            logger.debug(f"Reading from {f_in}")
            bin_data = f.read()
            raw_data = struct.unpack(f'<{int(len(bin_data) / 4)}I', bin_data)
        
        merged_data = merge_words(raw_data)
        unpacked_data = map(df.read, merged_data)

        event       = []
        counter_h   = []  # double check the number of headers
        counter_t   = []  # double check the number of trailers
        l1counter   = []
        row         = []
        col         = []
        tot_code    = []
        toa_code    = []
        cal_code    = []
        elink       = []
        raw         = []
        nhits       = []
        nhits_trail = []
        chipid      = []
        crc         = []
        bcid        = []
        counter_a   = []

        header_counter = 0
        trailer_counter = 0

        headers = []
        trailers = []
        i = 0
        l1a = -1
        bcid_t = 9999
        skip_event = False
        skip_counter = 0
        bad_run = False
        last_missing = False
        elink_report = {}

        uuid = []
        all_raw = []

        t_tmp = None

        for t, d in unpacked_data:
            if d['elink'] not in elink_report:
                logger.info(f"COND: d['elink'] not in elink_report", extra={"cond_num": 1})
                elink_report[d['elink']] = {'nheader':0, 'nhits':0, 'ntrailer':0}
            sus = False
            if d['raw_full'] in all_raw[-50:] and not t in ['trailer', 'filler']:  # trailers often look the same
                logger.info(f"COND: d['raw_full'] in all_raw[-50:] and not t in ['trailer', 'filler']", extra={"cond_num": 2})
                continue
            if t not in ['trailer', 'filler']:
                logger.info(f"COND: t not in ['trailer', 'filler']", extra={"cond_num": 3})
                all_raw.append(d['raw_full'])
            if t == 'header':
                logger.info(f"COND: t==header", extra={"cond_num": 4})
                elink_report[d['elink']]['nheader'] += 1
                hit_counter = 0
                uuid_tmp = d['l1counter'] | d['bcid']<<8
                headers.append(d['raw'])
                header_counter += 1

                if d['bcid'] != bcid_t and last_missing:
                    logger.info(f"COND: t==header and d['bcid'] != bcid_t and last_missing", extra={"cond_num": 5})
                    missing_l1counter[-1].append(d['bcid'])
                    last_missing = False

                if d['l1counter'] == l1a:
                    logger.info(f"COND: t==header and d['l1counter'] == l1a", extra={"cond_num": 6})
                    # this just skips additional headers for the same event
                    counter_h[-1] += 1
                    raw[-1].append(d['raw_full'])
                    if skip_event:
                        logger.info(f"COND: t==header and d['l1counter'] == l1a and skip_event", extra={"cond_num": 7})
                        logger.debug("Skipping event (same l1a counter)", d['l1counter'], d['bcid'], bcid_t)
                        continue
                else:
                    if abs(l1a - d['l1counter']) not in [1,255] and l1a>=0:
                        logger.info(f"COND: t==header and d['l1counter'] != l1a and abs(l1a - d['l1counter']) not in [1,255] and l1a>=0", extra={"cond_num": 8})
                        missed_l1counter_info = [d['l1counter'], d['bcid'], i, d['l1counter'] - l1a] #original by Daniel
                        missing_l1counter.append(missed_l1counter_info)  # this checks if we miss any event according to the counter
                        last_missing = True
                    if uuid_tmp in uuid and abs(i - np.where(np.array(uuid) == uuid_tmp)[0][-1]) < 150:
                        logger.info(f"COND: t==header and d['l1counter'] != l1a and uuid_tmp in uuid and abs(i - np.where(np.array(uuid) == uuid_tmp)[0][-1]) < 150", extra={"cond_num": 9})
                        logger.debug("Skipping duplicate event")
                        skip_counter += 1
                        skip_event = True
                        continue
                    else:
                        logger.info(f"COND: t==header and d['l1counter'] != l1a and NOT(uuid_tmp in uuid and abs(i - np.where(np.array(uuid) == uuid_tmp)[0][-1]) < 150)", extra={"cond_num": 10})
                        uuid.append(d['l1counter'] | d['bcid']<<8)

                    if (((abs(d['bcid']-bcid_t)<150) or (abs(d['bcid']+3564-bcid_t)<50)) and not (d['bcid'] == bcid_t) and not skip_trigger_check):
                        logger.info(f"COND: t==header and d['l1counter'] != l1a and (((abs(d['bcid']-bcid_t)<150) or (abs(d['bcid']+3564-bcid_t)<50)) and not (d['bcid'] == bcid_t) and not skip_trigger_check)", extra={"cond_num": 11})
                        skip_event = True
                        logger.debug("Skipping event", d['l1counter'], d['bcid'], bcid_t)
                        skip_counter += 1
                        continue
                    else:
                        logger.info(f"COND: t==header and d['l1counter'] != l1a and NOT(((abs(d['bcid']-bcid_t)<150) or (abs(d['bcid']+3564-bcid_t)<50)) and not (d['bcid'] == bcid_t) and not skip_trigger_check)", extra={"cond_num": 12})
                        skip_event = False
                    bcid_t = d['bcid']
                    if (abs(l1a - d['l1counter'])>1) and abs(l1a - d['l1counter'])!=255 and verbose:
                        logger.info(f"COND: t==header and d['l1counter'] != l1a and (abs(l1a - d['l1counter'])>1) and abs(l1a - d['l1counter'])!=255 and verbose", extra={"cond_num": 13})
                        sus = True
                    l1a = d['l1counter']
                    event.append(i)
                    counter_h.append(1)
                    counter_t.append(0)
                    l1counter.append(d['l1counter'])
                    row.append([])
                    col.append([])
                    tot_code.append([])
                    toa_code.append([])
                    cal_code.append([])
                    elink.append([])
                    raw.append([d['raw_full']])
                    nhits.append(0)
                    nhits_trail.append([])
                    chipid.append([])
                    crc.append([])
                    bcid.append([d['bcid']])
                    counter_a.append([])
                    i += 1
                    if verbose or sus:
                        logger.info(f"COND: t==header and d['l1counter'] != l1a and verbose or sus", extra={"cond_num": 14})
                        logger.debug("New event:", l1a, i, d['bcid'])
            if t == 'data':
                logger.info(f"COND: t==data", extra={"cond_num": 15})
                elink_report[d['elink']]['nhits'] += 1
            if t == 'trailer':
                logger.info(f"COND: t==trailer", extra={"cond_num": 16})
                elink_report[d['elink']]['ntrailer'] += 1

            if t == 'data' and not skip_event:
                logger.info(f"COND: t==data and NOT skip event", extra={"cond_num": 17})
                hit_counter += 1
                if 'tot' in d:
                    logger.info(f"COND: t==data and NOT skip event and tot in d", extra={"cond_num": 18})
                    tot_code[-1].append(d['tot'])
                    toa_code[-1].append(d['toa'])
                    cal_code[-1].append(d['cal'])
                elif 'counter_a' in d:
                    logger.info(f"COND: t==data and NOT skip_event and counter_a in d", extra={"cond_num": 19})
                    bcid[-1].append(d['bcid'])
                    counter_a[-1].append(d['counter_a'])
                elif 'counter_b' in d:
                    logger.info(f"COND: t==data and NOT skip_event and counter_b in d", extra={"cond_num": 20})
                    pass
                row[-1].append(d['row_id'])
                col[-1].append(d['col_id'])
                elink[-1].append(d['elink'])
                raw[-1].append(d['raw_full'])
                nhits[-1] += 1
                if nhits[-1] > 256:
                    logger.info(f"COND: t==data and NOT skip_event and nhits[-1] > 256", extra={"cond_num": 21})
                    logger.debug("This event already has more than 256 hits. Skipping event.")
                    skip_event = True
                    continue


            if t == 'trailer' and t_tmp != 'trailer':
                logger.info(f"COND: t == 'trailer' and t_tmp != 'trailer'", extra={"cond_num": 22})
                trailers.append(d['raw_full'])
                trailer_counter += 1
                if not skip_event:
                    logger.info(f"COND: t == 'trailer' and t_tmp != 'trailer' and NOT skip_event", extra={"cond_num": 23})
                    try:
                        counter_t[-1] += 1
                        if hit_counter > 0:
                            logger.info(f"COND: t == 'trailer' and t_tmp != 'trailer' and NOT skip_event and hit_counter > 0", extra={"cond_num": 24})
                            chipid[-1] += hit_counter*[d['chipid']]
                        nhits_trail[-1].append(d['hits'])
                        raw[-1].append(d['raw'])
                        crc[-1].append(d['crc'])
                    except IndexError:
                        logger.debug("Data stream started with a trailer, that is weird.")
            t_tmp = t

        if not bad_run or force:
            logger.info(f"COND: not bad_run or force", extra={"cond_num": 25})
            events = ak.Array({
                'event': event,
                'l1counter': l1counter,
                'nheaders': counter_h,
                'ntrailers': counter_t,
                'row': row,
                'col': col,
                'tot_code': tot_code,
                'toa_code': toa_code,
                'cal_code': cal_code,
                'elink': elink,
                'raw': raw,
                'crc': crc,
                'chipid': chipid,
                'bcid': bcid,
                'counter_a': counter_a,
                'nhits': ak.singletons(nhits),
                'nhits_trail': ak.sum(ak.Array(nhits_trail), axis=-1),
            })

            total_events = len(events)

            logger.debug(f"Done with {len(events)} events. " + emojize(":check_mark_button:"))

            if header_counter == trailer_counter:
                logger.info(f"COND: not bad_run or force and header_counter == trailer_counte", extra={"cond_num": 26})
                logger.debug(f" - found same number of headers and trailers!: {header_counter} " + emojize(":check_mark_button:"))
            else:
                logger.info(f"COND: not bad_run or force and NOT(header_counter == trailer_counte)", extra={"cond_num": 27})
                logger.debug(f" - found {header_counter} headers and {trailer_counter} trailers. Please check. " + emojize(":warning:"))

            logger.debug(f" - found {len(missing_l1counter)} missing events (irregular increase of L1counter).")
            if len(missing_l1counter)>0:
                logger.info(f"COND: not bad_run or force and len(missing_l1counter)>0", extra={"cond_num": 28})
                logger.debug("   L1counter, BCID, event number and step size of these events are:")
                # The last element passed the "last_missing" condition so the next bcid could not be appended
                if len(missing_l1counter[-1]) == 4:
                    logger.info(f"COND: not bad_run or force and len(missing_l1counter)>0 and len(missing_l1counter[-1]) == 4", extra={"cond_num": 29})
                    missing_l1counter[-1].append(-9999) #append dummy value
                for ml1, mbcid, mev, mdelta, mbcidt in missing_l1counter:
                    if mbcidt - mbcid<7:
                        logger.info(f"COND: not bad_run or force and len(missing_l1counter)>0 and mbcidt - mbcid<7", extra={"cond_num": 30})
                        logger.debug(f"Expected issue because of missing L1A dead time: {[ml1, mbcid, mev, mdelta, mbcidt]}")
                    else:
                        logger.info(f"COND: not bad_run or force and len(missing_l1counter)>0 and NOT(mbcidt - mbcid<7)", extra={"cond_num": 31})
                        logger.debug(f"missing_l1counter={[ml1, mbcid, mev,mdelta,mbcidt]}")

            logger.debug(f" - Total expected events is {total_events+len(missing_l1counter)}")
            logger.debug(f" - elink report:")
            logger.debug(str(pd.DataFrame(elink_report)))

            events_all_rb.append(events)


    if len(events_all_rb)>1 or True:
        logger.info(f"COND: len(events_all_rb)>1 or True", extra={"cond_num": 32})
        event_number = []
        bcid = []
        nhits = []
        row = []
        col = []
        chipid = []

        sel = ak.flatten(ak.ones_like(events_all_rb[0].nhits, dtype=bool))
        events_with_hits = len(events_all_rb[0][sel])

        for rb, events in enumerate(events_all_rb):
            if rb == 0:
                logger.info(f"COND: len(events_all_rb)>1 or True and rb==0", extra={"cond_num": 33})
                event_number = ak.to_list(events[sel].event)
                l1counter = ak.to_list(events[sel].l1counter)
                bcid = ak.to_list(events[sel].bcid)
                nhits = ak.to_list(events[sel].nhits)
                row = ak.to_list(events[sel].row)
                col = ak.to_list(events[sel].col)
                toa = ak.to_list(events[sel].toa_code)
                tot = ak.to_list(events[sel].tot_code)
                cal = ak.to_list(events[sel].cal_code)
                elink = ak.to_list(events[sel].elink)
                chipid = ak.to_list(events[sel].chipid)
            else:
                logger.info(f"COND: len(events_all_rb)>1 or True and NOT(rb==0)", extra={"cond_num": 34})
                # loop through rb0 events, and find corresponding entries in the other layers
                logger.debug(f"Merging events from RB {rb}")
                with tqdm(total=events_with_hits, bar_format='{l_bar}{bar:20}{r_bar}{bar:-20b}') as pbar:
                    for i, ev in enumerate(event_number):
                        for j, tmp_evt in enumerate(events_all_rb[rb][ak.flatten(events_all_rb[rb].bcid + 1 == events_all_rb[0].bcid[ev])]):
                            if abs(tmp_evt.event - ev)<100:
                                logger.info(f"COND: len(events_all_rb)>1 or True and NOT(rb==0) and abs(tmp_evt.event - ev)<100", extra={"cond_num": 35})
                                nhits[i] += ak.to_list(tmp_evt.nhits)
                                row[i] += ak.to_list(tmp_evt.row)
                                col[i] += ak.to_list(tmp_evt.col)
                                tot[i] += ak.to_list(tmp_evt.tot_code)
                                toa[i] += ak.to_list(tmp_evt.toa_code)
                                cal[i] += ak.to_list(tmp_evt.cal_code)
                                elink[i] += ak.to_list(tmp_evt.elink)
                                chipid[i] += ak.to_list(tmp_evt.chipid)
                                break
                        pbar.update()

        events = ak.Array({
            'event': event_number,
            'l1counter': l1counter,
            'row': row,
            'col': col,
            'tot_code': tot,
            'toa_code': toa,
            'cal_code': cal,
            'elink': elink,
            'chipid': chipid,
            'bcid': bcid,
            'nhits': nhits,
        })
    return events
