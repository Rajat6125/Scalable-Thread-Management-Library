import time
while True:
    count = 0
    while 300_000_000:
        _ = 12345 ** 2
        count += 1
    time.sleep(2)
    print("working..")
        

