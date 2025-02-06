
import random
import time

sleep_time = random.randint(3,6) # seconds
print(f"I am gonna sleep for {sleep_time} seconds")
time.sleep(sleep_time)

raise Exception("DAQ ERROR")