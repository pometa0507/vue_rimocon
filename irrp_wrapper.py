#!/usr/bin/env python

"""
A utility to record and then playback IR remote control codes.

To record use

./irrp_wrapper.py -r -g4 -fcodes 1 2 3 4 5 6

where

-r record
-g the GPIO connected to the IR receiver
-f the file to store the codes

and 1 2 3 4 5 6 is a list of codes to record.

To playback use

./irrp_wrapper.py -p -g17 -fcodes 2 3 4

where

-p playback
-g the GPIO connected to the IR transmitter
-f the file storing the codes to transmit

and 2 3 4 is a list of codes to transmit.

OPTIONS

-r record
-p playback
-g GPIO (receiver for record, transmitter for playback)
-f file

id1 id2 id3 list of ids to record or transmit

RECORD

--glitch     ignore edges shorter than glitch microseconds, default 100 us
--post       expect post milliseconds of silence after code, default 15 ms
--pre        expect pre milliseconds of silence before code, default 200 ms
--short      reject codes with less than short pulses, default 10
--tolerance  consider pulses the same if within tolerance percent, default 15
--no-confirm don't require a code to be repeated during record

TRANSMIT

--freq       IR carrier frequency, default 38 kHz
--gap        gap in milliseconds between transmitted codes, default 100 ms
"""

import time
import json
import os
import argparse

import pigpio # http://abyz.co.uk/rpi/pigpio/python.html



class irrp:
   def __init__(self, verbose=False):

      self.VERBOSE = verbose
      self.last_tick = 0
      self.in_code = False
      self.code = []
      self.fetching_code = False


   def record(self, gpio, filepath, id_list, glitch=100, post=15, pre=200, tolerance=15, short=10, no_confirm=False):

      def backup(f):
         """
         f -> f.bak -> f.bak1 -> f.bak2
         """
         try:
            os.rename(os.path.realpath(f)+".bak1", os.path.realpath(f)+".bak2")
         except:
            pass

         try:
            os.rename(os.path.realpath(f)+".bak", os.path.realpath(f)+".bak1")
         except:
            pass

         try:
            os.rename(os.path.realpath(f), os.path.realpath(f)+".bak")
         except:
            pass

      def normalise(c):
         """
         Typically a code will be made up of two or three distinct
         marks (carrier) and spaces (no carrier) of different lengths.

         Because of transmission and reception errors those pulses
         which should all be x micros long will have a variance around x.

         This function identifies the distinct pulses and takes the
         average of the lengths making up each distinct pulse.  Marks
         and spaces are processed separately.

         This makes the eventual generation of waves much more efficient.

         Input

         M    S   M   S   M   S   M    S   M    S   M
         9000 4500 600 540 620 560 590 1660 620 1690 615

         Distinct marks

         9000                average 9000
         600 620 590 620 615 average  609

         Distinct spaces

         4500                average 4500
         540 560             average  550
         1660 1690           average 1675

         Output

         M    S   M   S   M   S   M    S   M    S   M
         9000 4500 609 550 609 550 609 1675 609 1675 609
         """
         if self.VERBOSE:
            print("before normalise", c)
         entries = len(c)
         p = [0]*entries # Set all entries not processed.
         for i in range(entries):
            if not p[i]: # Not processed?
               v = c[i]
               tot = v
               similar = 1.0

               # Find all pulses with similar lengths to the start pulse.
               for j in range(i+2, entries, 2):
                  if not p[j]: # Unprocessed.
                     if (c[j]*TOLER_MIN) < v < (c[j]*TOLER_MAX): # Similar.
                        tot = tot + c[j]
                        similar += 1.0

               # Calculate the average pulse length.
               newv = round(tot / similar, 2)
               c[i] = newv

               # Set all similar pulses to the average value.
               for j in range(i+2, entries, 2):
                  if not p[j]: # Unprocessed.
                     if (c[j]*TOLER_MIN) < v < (c[j]*TOLER_MAX): # Similar.
                        c[j] = newv
                        p[j] = 1

         if self.VERBOSE:
            print("after normalise", c)

      def compare(p1, p2):
         """
         Check that both recodings correspond in pulse length to within
         TOLERANCE%.  If they do average the two recordings pulse lengths.

         Input

            M    S   M   S   M   S   M    S   M    S   M
         1: 9000 4500 600 560 600 560 600 1700 600 1700 600
         2: 9020 4570 590 550 590 550 590 1640 590 1640 590

         Output

         A: 9010 4535 595 555 595 555 595 1670 595 1670 595
         """
         if len(p1) != len(p2):
            return False

         for i in range(len(p1)):
            v = p1[i] / p2[i]
            if (v < TOLER_MIN) or (v > TOLER_MAX):
               return False

         for i in range(len(p1)):
            p1[i] = int(round((p1[i]+p2[i])/2.0))

         if self.VERBOSE:
            print("after compare", p1)

         return True

      def tidy_mark_space(records, base):

         ms = {}

         # Find all the unique marks (base=0) or spaces (base=1)
         # and count the number of times they appear,

         for rec in records:
            rl = len(records[rec])
            for i in range(base, rl, 2):
               if records[rec][i] in ms:
                  ms[records[rec][i]] += 1
               else:
                  ms[records[rec][i]] = 1

         if self.VERBOSE:
            print("t_m_s A", ms)

         v = None

         print("--------------------------")
         print("titidy_mark_space ms:", ms)
         print("--------------------------")

         for plen in sorted(ms):

            # Now go through in order, shortest first, and collapse
            # pulses which are the same within a tolerance to the
            # same value.  The value is the weighted average of the
            # occurences.
            #
            # E.g. 500x20 550x30 600x30  1000x10 1100x10  1700x5 1750x5
            #
            # becomes 556(x80) 1050(x20) 1725(x10)
            #       
            if v == None:
               e = [plen]
               v = plen
               tot = plen * ms[plen]
               similar = ms[plen]

            elif plen < (v*TOLER_MAX):
               e.append(plen)
               tot += (plen * ms[plen])
               similar += ms[plen]

            else:
               v = int(round(tot/float(similar)))
               # set all previous to v
               for i in e:
                  ms[i] = v
               e = [plen]
               v = plen
               tot = plen * ms[plen]
               similar = ms[plen]

            v = int(round(tot/float(similar)))
            # set all previous to v
            for i in e:
               ms[i] = v

            if self.VERBOSE:
               print("t_m_s B", ms)

            for rec in records:
               rl = len(records[rec])
               for i in range(base, rl, 2):
                  records[rec][i] = ms[records[rec][i]]

         

      def tidy(records):
         tidy_mark_space(records, 0) # Marks.
         tidy_mark_space(records, 1) # Spaces.
         return records

      def end_of_code():
         #global code, fetching_code
         if len(self.code) > SHORT:
            normalise(self.code)
            self.fetching_code = False
         else:
            self.code = []
            print("Short code, probably a repeat, try again")



      def cbf(gpio, level, tick):

         #global last_tick, in_code, code, fetching_code

         if level != pigpio.TIMEOUT:

            edge = pigpio.tickDiff(self.last_tick, tick)
            self.last_tick = tick

            if self.fetching_code:

               if (edge > PRE_US) and (not self.in_code): # Start of a code.
                  self.in_code = True
                  pi.set_watchdog(gpio, POST_MS) # Start watchdog.

               elif (edge > POST_US) and self.in_code: # End of a code.
                  self.in_code = False
                  pi.set_watchdog(gpio, 0) # Cancel watchdog.
                  end_of_code()

               elif self.in_code:
                  self.code.append(edge)

         else:
            pi.set_watchdog(gpio, 0) # Cancel watchdog.
            if self.in_code:
               self.in_code = False
               end_of_code()


      PRE_MS = pre
      POST_MS = post
      POST_US = POST_MS * 1000
      PRE_US  = PRE_MS  * 1000
      CONFIRM = not no_confirm
      TOLERANCE = tolerance
      TOLER_MIN =  (100 - TOLERANCE) / 100.0
      TOLER_MAX =  (100 + TOLERANCE) / 100.0
      SHORT = short

      
      pi = pigpio.pi() # Connect to Pi.

      if not pi.connected:
         exit(0)

      try:
         FILE = filepath
         f = open(FILE, "r")
         records = json.load(f)
         f.close()
      except:
         records = {}

      pi.set_mode(gpio, pigpio.INPUT) # IR RX connected to this GPIO.

      pi.set_glitch_filter(gpio, glitch) # Ignore glitches.

      cb = pi.callback(gpio, pigpio.EITHER_EDGE, cbf)

      # Process each id

      print("Recording")
      #for arg in args.id:
      for arg in id_list:
         print("Press key for '{}'".format(arg))
         self.code = []
         self.fetching_code = True
         while self.fetching_code:
            time.sleep(0.1)
         print("Okay")
         time.sleep(0.5)

         if CONFIRM:
            press_1 = self.code[:]
            done = False

            tries = 0
            while not done:
               print("Press key for '{}' to confirm".format(arg))
               self.code = []
               self.fetching_code = True
               while self.fetching_code:
                  time.sleep(0.1)
               press_2 = self.code[:]
               the_same = compare(press_1, press_2)
               if the_same:
                  done = True
                  records[arg] = press_1[:]
                  print("Okay")
                  time.sleep(0.5)
               else:
                  tries += 1
                  if tries <= 3:
                     print("No match")
                  else:
                     print("Giving up on key '{}'".format(arg))
                     done = True
                  time.sleep(0.5)
         else: # No confirm.
            records[arg] = self.code[:]

      pi.set_glitch_filter(gpio, 0) # Cancel glitch filter.
      pi.set_watchdog(gpio, 0) # Cancel watchdog.

      ##records = tidy(records)  # TODO: Fix Error.

      backup(FILE)

      f = open(FILE, "w")
      f.write(json.dumps(records, sort_keys=True).replace("],", "],\n")+"\n")
      f.close()


   def play(self, gpio, filepath, id_list, freq=38.0, gap=100):


      def carrier(gpio, frequency, micros):
         """
         Generate carrier square wave.
         """
         wf = []
         cycle = 1000.0 / frequency
         cycles = int(round(micros/cycle))
         on = int(round(cycle / 2.0))
         sofar = 0
         for c in range(cycles):
            target = int(round((c+1)*cycle))
            sofar += on
            off = target - sofar
            sofar += off
            wf.append(pigpio.pulse(1<<gpio, 0, on))
            wf.append(pigpio.pulse(0, 1<<gpio, off))
         return wf

      GAP_MS = gap
      GAP_S = GAP_MS/1000.0

      pi = pigpio.pi() # Connect to Pi.

      if not pi.connected:
         exit(0)
      
      try:
         FILE = filepath
         f = open(FILE, "r")
      except:
         print("Can't open: {}".format(FILE))
         exit(0)

      records = json.load(f)

      f.close()

      pi.set_mode(gpio, pigpio.OUTPUT) # IR TX connected to this GPIO.

      pi.wave_add_new()

      emit_time = time.time()

      if self.VERBOSE:
         print("Playing")

      #for arg in args.id:
      for arg in id_list:
         if arg in records:

            code = records[arg]

            # Create wave

            marks_wid = {}
            spaces_wid = {}

            wave = [0]*len(code)

            for i in range(0, len(code)):
               ci = code[i]
               if i & 1: # Space
                  if ci not in spaces_wid:
                     pi.wave_add_generic([pigpio.pulse(0, 0, ci)])
                     spaces_wid[ci] = pi.wave_create()
                  wave[i] = spaces_wid[ci]
               else: # Mark
                  if ci not in marks_wid:
                     wf = carrier(gpio, freq, ci)
                     pi.wave_add_generic(wf)
                     marks_wid[ci] = pi.wave_create()
                  wave[i] = marks_wid[ci]

            delay = emit_time - time.time()

            if delay > 0.0:
               time.sleep(delay)

            pi.wave_chain(wave)

            if self.VERBOSE:
               print("key " + arg)

            while pi.wave_tx_busy():
               time.sleep(0.002)

            emit_time = time.time() + GAP_S

            for i in marks_wid:
               pi.wave_delete(marks_wid[i])

            marks_wid = {}

            for i in spaces_wid:
               pi.wave_delete(spaces_wid[i])

            spaces_wid = {}

         else:
            print("Id {} not found".format(arg))

      pi.stop() # Disconnect from Pi.


if __name__ == '__main__':


   p = argparse.ArgumentParser()

   g = p.add_mutually_exclusive_group(required=True)  # 相互排他
   g.add_argument("-p", "--play",   help="play keys",   action="store_true")
   g.add_argument("-r", "--record", help="record keys", action="store_true")

   p.add_argument("-g", "--gpio", help="GPIO for RX/TX", required=True, type=int)
   p.add_argument("-f", "--file", help="Filename",       required=True)

   p.add_argument('id', nargs='+', type=str, help='IR codes')

   p.add_argument("--freq",      help="frequency kHz",   type=float, default=38.0)

   p.add_argument("--gap",       help="key gap ms",        type=int, default=100)
   p.add_argument("--glitch",    help="glitch us",         type=int, default=100)
   p.add_argument("--post",      help="postamble ms",      type=int, default=15)
   p.add_argument("--pre",       help="preamble ms",       type=int, default=200)
   p.add_argument("--short",     help="short code length", type=int, default=10)
   p.add_argument("--tolerance", help="tolerance percent", type=int, default=15)

   p.add_argument("-v", "--verbose", help="Be verbose",     action="store_true")
   p.add_argument("--no-confirm", help="No confirm needed", action="store_true")

   args = p.parse_args()


   ir = irrp(verbose=args.verbose)

   if args.record: # Record.
      ir.record(gpio=args.gpio, 
                filepath=args.file, 
                id_list=args.id,
                glitch=args.glitch, 
                post=args.post,
                pre=args.pre,
                tolerance=args.tolerance, 
                short=args.short, 
                no_confirm=args.no_confirm
                )
   
   else: # play
      ir.play(gpio=args.gpio, 
              filepath=args.file, 
              id_list=args.id,
              freq=args.freq,
              gap=args.gap
              )
